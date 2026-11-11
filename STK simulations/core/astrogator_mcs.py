"""
Build an STK Astrogator satellite with the paper's force model realised through
built-in models (NO custom plugin):

- Gravity : central + J2 only (Gravitational Force, degree 2, order 0)
- Drag    : US Standard Atmosphere (1976) + N-Plate area model (opposed +/-Z plates)
- SRP     : N-Plate SRP (single body +Z plate, specular 0.70 -> C_r,eff = 1.7),
            binary Cylindrical shadow (or None for the eclipse-off branch)
- No third bodies, no albedo.
- Attitude: inertially-fixed quaternion (body +Z -> sail normal in ECI).

API names verified against the live STK build; see docs/astrogator_design.md.
"""

from __future__ import annotations

from pathlib import Path

from .nplate_files import write_srp_nplate_file, write_drag_nplate_file
from .attitude import normal_to_quaternion_eci
from .scenario_builder import RunCase, _add_seconds_to_iso  # reuse dataclasses/helpers

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
NPLATE_DIR = PROJECT_ROOT / "results" / "_nplate"


def _stk():
    from agi.stk13 import stkobjects as o
    return o


def _astro():
    from agi.stk13.stkobjects import astrogator as a
    return a


def set_unit_prefs(root):
    """km / deg / UTCG so element and epoch assignments are unambiguous."""
    up = root.UnitPreferences
    for dim, unit in (("DateFormat", "UTCG"), ("Distance", "km"), ("Angle", "deg")):
        try:
            up.Item(dim).SetCurrentUnit(unit)
        except Exception:
            pass


# ---- Keplerian element setter (robust to attribute-name variants) ----------
_KEP_FIELDS = {
    "sma": ("SemiMajorAxis", "SemimajorAxis", "SMA"),
    "ecc": ("Eccentricity", "Ecc"),
    "inc": ("Inclination", "Inc"),
    "raan": ("RAAN", "Raan", "RightAscension", "RAOfAscendingNode"),
    "aop": ("ArgOfPeriapsis", "ArgumentOfPeriapsis", "ArgOfPerigee", "AoP"),
    "ta": ("TrueAnomaly", "TrueAnom", "TA"),
}


def _set_one(el, candidates, value, required_key):
    for name in candidates:
        if hasattr(el, name):
            setattr(el, name, value)
            return name
    raise RuntimeError(
        f"AgVAElementKeplerian has none of {candidates} for '{required_key}'. "
        f"Available: {[m for m in dir(el) if not m.startswith('_')]}"
    )


def _set_keplerian(el, case: RunCase):
    used = {}
    used["sma"] = _set_one(el, _KEP_FIELDS["sma"], case.sma_km, "sma")
    used["ecc"] = _set_one(el, _KEP_FIELDS["ecc"], case.ecc, "ecc")
    used["inc"] = _set_one(el, _KEP_FIELDS["inc"], case.inc_deg, "inc")
    used["aop"] = _set_one(el, _KEP_FIELDS["aop"], case.aop_deg, "aop")
    used["raan"] = _set_one(el, _KEP_FIELDS["raan"], case.raan_deg, "raan")
    used["ta"] = _set_one(el, _KEP_FIELDS["ta"], case.ta_deg, "ta")
    return used


def _get_func(pf, name):
    try:
        return pf.GetItemByName(name)
    except Exception:
        for i in range(pf.Count):
            it = pf.Item(i)
            if getattr(it, "Name", None) == name:
                return it
    raise RuntimeError(f"propagator function '{name}' not found after Add")


def build_propagator(root, prop_name, case: RunCase, srp_file, drag_file,
                     use_drag=True, use_srp=True, drag_model="nplate"):
    """
    Create/replace an owned numerical propagator with J2 + (US1976 N-plate drag)
    + (N-plate SRP). Returns the propagator component.
    """
    o = _stk(); astro = _astro()
    cd = root.CurrentScenario.ComponentDirectory
    props = cd.GetComponents(2).GetFolder("Propagators")  # eComponentAstrogator=2
    try:
        props.Remove(prop_name)
    except Exception:
        pass
    props.DuplicateComponent("Earth Point Mass", prop_name)
    prop = props.Item(prop_name)
    pf = prop.PropagatorFunctions
    try:
        pf.RemoveAll()
    except Exception:
        # remove one-by-one if RemoveAll unavailable
        for i in reversed(range(pf.Count)):
            try:
                pf.Remove(pf.Item(i).Name)
            except Exception:
                pass

    # --- gravity: central + J2 ---
    pf.Add("Gravitational Force")
    grav = _get_func(pf, "Gravitational Force")
    grav.Degree = 2
    grav.Order = 0
    for attr, val in (("UseOceanTides", False), ("UseSecularVariations", False),
                      ("IncludeTimeDependentSolidTides", False)):
        try:
            setattr(grav, attr, val)
        except Exception:
            pass

    # --- drag: US Standard Atmosphere (1976), N-plate or spherical area model ---
    if use_drag:
        pf.Add("US Standard Atmosphere")
        drag = _get_func(pf, "US Standard Atmosphere")
        if drag_model == "spherical":
            drag.DragModelType = astro.AgEVADragModelType.eVADragModelTypeSpherical
        else:
            drag.DragModelType = astro.AgEVADragModelType.eVADragModelTypeNPlate
            drag.NPlateDefinitionFile = str(drag_file)
        try:
            drag.UseApproximateAltitude = False
        except Exception:
            pass

    # --- SRP: N-plate ---
    if use_srp:
        pf.Add("NPlate SRP")
        srp = _get_func(pf, "NPlate SRP")
        srp.NPlateDefinitionFile = str(srp_file)
        shadow = (astro.AgEVAShadowModel.eVAShadowModelNone if case.disable_eclipse
                  else astro.AgEVAShadowModel.eVAShadowModelCylindrical)
        try:
            srp.ShadowModel = shadow
        except Exception:
            pass
        # same irradiance as the open-source plate: P_1AU = 4.5605e-6 N/m^2 x c = 1367.2 W/m^2
        for attr in ("MeanFlux",):
            try:
                setattr(srp, attr, 4.5605e-6 * 299792458.0)
            except Exception:
                pass

    return prop


def build_satellite(root, case: RunCase, sat_name="Sat",
                    use_drag=True, use_srp=True, nplate_dir=None, drag_model="nplate",
                    zero_fuel=True):
    """
    Full Astrogator build for one case. Returns (sat, driver).
    Writes per-case .nplate files (SRP one-sided; drag opposed +/-Z with cd_scale).
    """
    o = _stk(); astro = _astro()
    set_unit_prefs(root)
    scen = root.CurrentScenario
    if scen is None:
        raise RuntimeError("No active scenario.")

    stop_iso = _add_seconds_to_iso(case.epoch_iso, case.duration_sec)
    scen.SetTimePeriod(case.epoch_iso, stop_iso)

    # .nplate files (per case; area/Cd/scaling baked in)
    nd = Path(nplate_dir) if nplate_dir else NPLATE_DIR
    srp_file = write_srp_nplate_file(nd / f"{case.name}_srp.nplate", case.sail.sail_area_m2)
    drag_file = write_drag_nplate_file(nd / f"{case.name}_drag.nplate",
                                       case.sail.sail_area_m2, case.sail.cd,
                                       cd_scale=case.density_scaling_factor)

    try:
        scen.Children.Unload(o.AgESTKObjectType.eSatellite, sat_name)
    except Exception:
        pass
    sat = scen.Children.New(o.AgESTKObjectType.eSatellite, sat_name)

    # mass (both the classic MassProperties and the Astrogator SpacecraftParameters)
    try:
        sat.MassProperties.Mass = case.sail.mass_kg
    except Exception:
        pass

    sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorAstrogator)
    driver = sat.Propagator
    mcs = driver.MainSequence

    prop_name = f"SailProp_{sat_name}"
    build_propagator(root, prop_name, case, srp_file, drag_file,
                     use_drag=use_drag, use_srp=use_srp, drag_model=drag_model)

    init = mcs.Item("Initial State")
    propseg = mcs.Item("Propagate")
    propseg.PropagatorName = prop_name

    # initial state: Keplerian in Earth inertial
    init.SetElementType(astro.AgEVAElementType.eVAElementTypeKeplerian)
    init.OrbitEpoch = case.epoch_iso
    for cs in ("CentralBody/Earth ICRF", "CentralBody/Earth Inertial"):
        try:
            init.CoordSystemName = cs
            break
        except Exception:
            continue
    _set_keplerian(init.Element, case)

    sp = init.SpacecraftParameters
    for attr, val in (("DryMass", case.sail.mass_kg), ("Cr", case.sail.cr),
                      ("Cd", case.sail.cd), ("DragArea", case.sail.sail_area_m2),
                      ("SolarRadiationPressureArea", case.sail.sail_area_m2),
                      ("RadiationPressureArea", case.sail.sail_area_m2)):
        try:
            setattr(sp, attr, val)
        except Exception:
            pass

    # The Initial State segment's fuel tank defaults to 50 kg of fuel, which
    # Astrogator adds to DryMass when it evaluates drag and SRP. The original
    # (submitted) build left it in place, so the propagated mass was 60 kg and the
    # ballistic coefficient 6x too small (found by read-back, validation/rev_stk_probe.py).
    if zero_fuel:
        try:
            tank = init.FuelTank
            tank.FuelMass = 0.0
            tank.MaximumFuelMass = 0.0
        except Exception:
            pass

    # attitude: inertially fixed body +Z -> sail normal
    sat.SetAttitudeType(o.AgEVeAttitude.eAttitudeStandard)
    basic = sat.Attitude.Basic
    basic.SetProfileType(o.AgEVeProfile.eProfileFixedInAxes)
    prof = basic.Profile
    for ax in ("CentralBody/Earth ICRF", "CentralBody/Earth Inertial"):
        try:
            prof.ReferenceAxes = ax
            break
        except Exception:
            continue
    # IAgOrientationQuaternion.AssignQuaternion takes (qx, qy, qz, qs): scalar LAST.
    # The submitted build passed the scalar first, which mis-oriented the plate
    # (effective SRP area 16 m^2 instead of A cos(alpha) = 83 m^2; rev_stk_probe.py).
    qw, qx, qy, qz = normal_to_quaternion_eci(case.sail_normal_eci, body_axis=(0, 0, 1))
    prof.Orientation.AssignQuaternion(qx, qy, qz, qw)

    # stopping condition: Duration
    stop = propseg.StoppingConditions.Item("Duration").Properties
    stop.Trip = float(case.duration_sec)
    # allow long propagations to exceed the default max-time cap
    try:
        if case.duration_sec > propseg.MaxPropagationTime:
            propseg.OverrideMaxPropagationTime = True
            propseg.MaxPropagationTime = float(case.duration_sec) * 1.05
    except Exception:
        pass

    return sat, driver


def run_mcs(driver):
    driver.RunMCS()
