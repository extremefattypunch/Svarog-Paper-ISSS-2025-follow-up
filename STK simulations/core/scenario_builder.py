"""
Build an STK scenario + satellite + HPOP force model + plugins for the
flat-plate solar-sail problem.

This module imports `agi.stk13` lazily so it can be inspected on machines
without STK installed; importing the module is harmless, but calling
`build_satellite` requires STK and a valid scenario.

Design points:
- Gravity: central + J2 only (degree 2, order 0). EGM96 file under the hood.
- Drag: built-in spherical drag DISABLED, replaced by the FlatPlateDrag plugin.
- SRP: built-in SRP DISABLED (EnableShadowing=False then Use=False), replaced
       by the FlatPlateSRP plugin which computes its own umbra.
- Third-body: not added (paper omits).
- Attitude: inertially fixed quaternion that maps body +Z to the desired
            sail normal in ECI.

If a particular STK 13 build does not expose the expected SRP plugin enum,
this module raises a clear RuntimeError pointing at docs/plugin_design.md
for the workaround.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Project paths (resolved at import for predictable plugin-path passing)
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent          # STK simulations/
PLUGIN_DIR = PROJECT_ROOT / "plugins"
SRP_PLUGIN_PATH = PLUGIN_DIR / "flatplate_srp_hpop.py"
DRAG_PLUGIN_PATH = PLUGIN_DIR / "flatplate_drag_hpop.py"


@dataclass
class SailParams:
    sail_area_m2: float = 100.0
    mass_kg: float = 10.0
    cr: float = 1.7
    cd: float = 2.2
    # Body inertia (placeholder square plate, side L=10m, m=10 kg).
    # I = (1/12) m L^2 for a thin square plate about an in-plane axis;
    # I_normal = (1/6) m L^2 about the plate normal.
    @property
    def Ixx(self) -> float:
        L = math.sqrt(self.sail_area_m2)
        return (1.0 / 12.0) * self.mass_kg * L * L

    @property
    def Iyy(self) -> float:
        return self.Ixx

    @property
    def Izz(self) -> float:
        L = math.sqrt(self.sail_area_m2)
        return (1.0 / 6.0) * self.mass_kg * L * L


@dataclass
class RunCase:
    """One propagation case."""
    name: str
    altitude_km: float
    inc_deg: float
    raan_deg: float
    sma_km: float
    ecc: float = 1e-4
    aop_deg: float = 0.0
    ta_deg: float = 0.0
    sail_normal_eci: tuple = (1.0, 0.0, 0.0)
    epoch_iso: str = "1 Jan 2026 12:00:00.000"
    duration_sec: float = 14 * 86400
    step_sec: float = 60.0
    sail: SailParams = None
    density_scaling_factor: float = 1.0
    disable_eclipse: bool = False
    sidecar_dir: Optional[Path] = None  # if set, plugins write per-step CSVs here

    def __post_init__(self):
        if self.sail is None:
            self.sail = SailParams()


def _stk_objects():
    """Lazy import of stkobjects so module loads w/o STK."""
    from agi.stk13 import stkobjects as o  # noqa: F401
    return o


def _add_seconds_to_iso(iso: str, seconds: float) -> str:
    """Add `seconds` to STK ISO time and return STK-formatted ISO string."""
    from datetime import datetime, timedelta
    # Common STK formats
    fmts = ("%d %b %Y %H:%M:%S.%f", "%d %b %Y %H:%M:%S")
    for fmt in fmts:
        try:
            dt = datetime.strptime(iso, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Unrecognised ISO time {iso!r}")
    new_dt = dt + timedelta(seconds=float(seconds))
    return new_dt.strftime("%d %b %Y %H:%M:%S.") + f"{new_dt.microsecond // 1000:03d}"


def build_satellite(scenario_root, case: RunCase, sat_name: str = "Sat"):
    """
    Build (or replace) a satellite in the scenario per the case spec.
    Returns the STK Satellite COM object.
    """
    o = _stk_objects()
    scenario = scenario_root.CurrentScenario
    if scenario is None:
        raise RuntimeError("No scenario active. Call root.NewScenario(...) first.")

    # Compute absolute stop ISO (STK does not accept "+N sec" in SetExplicitInterval)
    stop_iso = _add_seconds_to_iso(case.epoch_iso, case.duration_sec)

    # Set scenario time interval
    scenario.SetTimePeriod(case.epoch_iso, stop_iso)

    # Remove existing satellite of the same name if present
    try:
        scenario.Children.Unload(o.AgESTKObjectType.eSatellite, sat_name)
    except Exception:
        pass

    sat = scenario.Children.New(o.AgESTKObjectType.eSatellite, sat_name)

    # Mass / inertia
    mp = sat.MassProperties
    mp.Mass = case.sail.mass_kg
    mp.Inertia.Ixx = case.sail.Ixx
    mp.Inertia.Iyy = case.sail.Iyy
    mp.Inertia.Izz = case.sail.Izz
    mp.Inertia.Ixy = 0.0
    mp.Inertia.Ixz = 0.0
    mp.Inertia.Iyz = 0.0

    # Propagator -> HPOP
    sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorHPOP)
    prop = sat.Propagator
    prop.Step = case.step_sec
    prop.EphemerisInterval.SetExplicitInterval(case.epoch_iso, stop_iso)
    prop.InitialState.OrbitEpoch.SetExplicitTime(case.epoch_iso)
    prop.InitialState.Representation.AssignClassical(
        o.AgECoordinateSystem.eCoordinateSystemICRF,
        case.sma_km,
        case.ecc,
        case.inc_deg,
        case.aop_deg,
        case.raan_deg,
        case.ta_deg,
    )

    # Force model
    fm = prop.ForceModel
    fm.CentralBodyGravity.SetMaximumDegreeAndOrder(2, 0)  # J2 only

    # ---- DRAG: replace spherical with our flat-plate plugin ----------------
    fm.Drag.Use = True
    try:
        fm.Drag.SetDragModelType(o.AgEDragModel.eDragModelPlugin)
        dplug = fm.Drag.DragModel
        dplug.PluginName = "FlatPlateDrag"
        dps = dplug.PluginSettings
        dps.SetProperty("Filename", str(DRAG_PLUGIN_PATH))
        dps.SetProperty("sail_area_m2", str(case.sail.sail_area_m2))
        dps.SetProperty("mass_kg", str(case.sail.mass_kg))
        dps.SetProperty("cd", str(case.sail.cd))
        dps.SetProperty("sail_normal_eci_x", str(case.sail_normal_eci[0]))
        dps.SetProperty("sail_normal_eci_y", str(case.sail_normal_eci[1]))
        dps.SetProperty("sail_normal_eci_z", str(case.sail_normal_eci[2]))
        dps.SetProperty("density_scaling_factor", str(case.density_scaling_factor))
        if case.sidecar_dir is not None:
            dps.SetProperty("sidecar_log_path",
                            str(case.sidecar_dir / f"{case.name}_drag.csv"))
    except Exception as exc:
        raise RuntimeError(
            "Drag plugin wiring failed; verify AgEDragModel.eDragModelPlugin "
            f"in this STK build. See docs/plugin_design.md §4.2. Original error: {exc!r}"
        )

    # ---- SRP: replace spherical with our flat-plate plugin -----------------
    # Try the SRP plugin enum; fall back to a clear error if not present.
    fm.SolarRadiationPressure.Use = True
    fm.SolarRadiationPressure.EnableShadowing = False  # plugin computes umbra itself
    srp_plugin_attached = False
    for enum_name in ("eSRPModelPlugin", "eSolarRadiationModelPlugin",
                      "eSRPPlugin"):
        if not hasattr(o, "AgESRPModel"):
            continue
        enum_val = getattr(o.AgESRPModel, enum_name, None)
        if enum_val is None:
            continue
        try:
            fm.SolarRadiationPressure.SetSRPModelType(enum_val)
            splug = fm.SolarRadiationPressure.SRPModel
            splug.PluginName = "FlatPlateSRP"
            sps = splug.PluginSettings
            sps.SetProperty("Filename", str(SRP_PLUGIN_PATH))
            sps.SetProperty("sail_area_m2", str(case.sail.sail_area_m2))
            sps.SetProperty("mass_kg", str(case.sail.mass_kg))
            sps.SetProperty("cr", str(case.sail.cr))
            sps.SetProperty("sail_normal_eci_x", str(case.sail_normal_eci[0]))
            sps.SetProperty("sail_normal_eci_y", str(case.sail_normal_eci[1]))
            sps.SetProperty("sail_normal_eci_z", str(case.sail_normal_eci[2]))
            sps.SetProperty("disable_eclipse", "true" if case.disable_eclipse else "false")
            if case.sidecar_dir is not None:
                sps.SetProperty("sidecar_log_path",
                                str(case.sidecar_dir / f"{case.name}_srp.csv"))
            srp_plugin_attached = True
            break
        except Exception:
            continue

    if not srp_plugin_attached:
        raise RuntimeError(
            "Could not attach the SRP plugin: this STK 13 build does not expose "
            "an SRP plugin enum on AgESRPModel. See docs/plugin_design.md §4.2 "
            "for the External Force Model fallback. Falling back to spherical "
            "would silently break the cos^2 alpha mechanism — refusing to proceed."
        )

    # Attitude: inertially-fixed quaternion mapping body +Z to sail normal
    sat.SetAttitudeType(o.AgEVeAttitude.eAttitudeStandard)
    basic = sat.Attitude.Basic
    basic.SetProfileType(o.AgEVeProfile.eProfileFixedInAxes)
    prof = basic.Profile
    # Reference axes: Earth Inertial (J2000 / ICRF for this study)
    prof.ReferenceAxes = "CentralBody/Earth ICRF"
    from .attitude import normal_to_quaternion_eci
    qw, qx, qy, qz = normal_to_quaternion_eci(case.sail_normal_eci, body_axis=(0, 0, 1))
    prof.Orientation.AssignQuaternion(qw, qx, qy, qz)

    return sat


def propagate(sat):
    """Run the propagator. Wraps any STK exception with a clear message."""
    try:
        sat.Propagator.Propagate()
    except Exception as exc:
        raise RuntimeError(
            f"HPOP propagation failed. Common causes: plugin file path wrong, "
            f"plugin class name mismatch, plugin syntax error. Original: {exc!r}"
        )
