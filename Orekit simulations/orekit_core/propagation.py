"""
The Orekit port of the paper's propagator.

Everything below is assembled from stock Orekit components:

  gravity   NumericalPropagator's own Newtonian attraction (mu = paper's value)
            + J2OnlyPerturbation(mu, R_e, J2, EME2000)
  drag      DragForce(US1976Atmosphere, BoxAndSolarArraySpacecraft | IsotropicDrag)
  SRP       RadiationPressureModel(CylindricallyShadowedLightFluxModel,
                                   BoxAndSolarArraySpacecraft)
  attitude  FrameAlignedProvider (inertially frozen sail normal)
  integrator ClassicalRungeKuttaIntegrator (fixed step, matches the paper) or
             DormandPrince853 (Orekit's own recommended practice)

`CylindricallyShadowedLightFluxModel` deserves a note: it is a *binary*
cylindrical umbra with no penumbra, which is precisely the shadow model the
paper specifies. Orekit's more common `SolarRadiationPressure` uses a conical
model with penumbra; using the cylindrical one removes an avoidable modelling
difference from the comparison. Setting its occulting radius to zero disables
eclipse entirely, which is how the Fig.-3 "eclipse off" branch is realised.

Mean elements are recovered by stroboscopic sampling of the osculating state at
ascending-node crossings, using the same detection rule as the paper's
propagator (sign change of z between consecutive fixed steps), so the two mean
series are directly comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .orekit_setup import boot

boot()

from jpype import JImplements, JOverride  # noqa: E402
from org.hipparchus.geometry.euclidean.threed import Vector3D  # noqa: E402
from org.hipparchus.ode.nonstiff import (  # noqa: E402
    ClassicalRungeKuttaIntegrator, DormandPrince853Integrator,
)
from org.orekit.attitudes import FrameAlignedProvider  # noqa: E402
from org.orekit.bodies import CelestialBodyFactory, OneAxisEllipsoid  # noqa: E402
from org.orekit.forces.drag import DragForce  # noqa: E402
from org.orekit.forces.gravity import J2OnlyPerturbation  # noqa: E402
from org.orekit.forces.radiation import (  # noqa: E402
    RadiationPressureModel, CylindricallyShadowedLightFluxModel,
)
from org.orekit.frames import FramesFactory  # noqa: E402
from org.orekit.orbits import KeplerianOrbit, OrbitType, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402
from org.orekit.propagation.numerical import NumericalPropagator  # noqa: E402
from org.orekit.time import AbsoluteDate, TimeScalesFactory  # noqa: E402
from org.orekit.utils import IERSConventions, Constants  # noqa: E402

from .atmosphere import US1976Atmosphere  # noqa: E402
from .attitude import raan_for_ltdn, sail_normal_eci, fixed_inertial_attitude  # noqa: E402
from .constants import (  # noqa: E402
    MU_EARTH, R_EARTH, J2, K_REF, SAIL_AREA, SAIL_MASS, CD,
    ABSORPTION, SPECULAR, ECC, EPOCH, inclination_for,
)
from .spacecraft import drag_plate, srp_plate, spherical_drag  # noqa: E402

EME2000 = FramesFactory.getEME2000()
UTC = TimeScalesFactory.getUTC()
T0 = AbsoluteDate(int(EPOCH[0]), int(EPOCH[1]), int(EPOCH[2]),
                  int(EPOCH[3]), int(EPOCH[4]), float(EPOCH[5]), UTC)
SUN = CelestialBodyFactory.getSun()


# ---------------------------------------------------------------------------
# Case definition -- mirrors core.offline_propagator.SailCase field for field
# ---------------------------------------------------------------------------
@dataclass
class OrekitCase:
    altitude_km: float = 700.0
    inc_deg: float | None = None       # None -> paper value for the altitude
    raan_deg: float = 285.5
    pitch_deg: float = 24.8
    roll_deg: float = 0.0
    ecc: float = ECC
    area_m2: float = SAIL_AREA
    mass_kg: float = SAIL_MASS
    cd: float = CD
    absorption: float = ABSORPTION
    specular: float = SPECULAR
    density_scale: float = 1.0         # Fig.-7 density sweep
    use_srp: bool = True
    use_drag: bool = True
    disable_eclipse: bool = False      # Fig.-3 eclipse-off branch
    drag_mode: str = "nplate"          # "nplate" (A|cos theta|) or "spherical"
    corotating_atmosphere: bool = False
    altitude_mode: str = "geocentric"  # or "geodetic" (WGS-84 ellipsoid height)
    #: "de440" is Orekit's own ephemeris; "paper" substitutes the reduced
    #: model's analytic Sun at a fixed 1 AU, so that a propagated SRP
    #: comparison against the open-source propagator is not confounded by the
    #: ephemeris. See orekit_core/sun.py.
    sun_model: str = "de440"
    integrator: str = "rk4"            # "rk4" (fixed, paper-like) or "dp853"
    dt: float = 30.0                   # fixed step / sampling step [s]
    #: Target position error per step for the adaptive integrator, in METRES.
    #: This is what Orekit's `NumericalPropagator.tolerances(dP, ...)` expects --
    #: not a dimensionless relative tolerance. 1 mm is already far tighter than
    #: anything this study resolves; asking for nanometres drives the step below
    #: the integrator's floor on long propagations and aborts the run.
    #: 1e-4 m is converged for this problem: the 14-day gain at the reproduced
    #: 800 km geometry moves by 6 m between dP = 1e-3 and dP = 1e-4, and is
    #: unchanged thereafter.
    pos_tol_m: float = 1e-4

    @property
    def inclination(self) -> float:
        return inclination_for(self.altitude_km) if self.inc_deg is None else self.inc_deg

    @property
    def sma_m(self) -> float:
        return R_EARTH + self.altitude_km * 1e3

    def normal_eci(self):
        return sail_normal_eci(self.raan_deg, self.inclination,
                               self.pitch_deg, self.roll_deg)

    @classmethod
    def from_ltdn(cls, altitude_km, ltdn_hours, pitch_deg, **kw):
        return cls(altitude_km=altitude_km, raan_deg=raan_for_ltdn(ltdn_hours),
                   pitch_deg=pitch_deg, **kw)


# ---------------------------------------------------------------------------
# Fixed-step recorder
# ---------------------------------------------------------------------------
@JImplements("org.orekit.propagation.sampling.OrekitFixedStepHandler")
class _Recorder:
    """Records the raw Cartesian state at a fixed cadence.

    JPype proxies do not inherit Java default interface methods, so `init` and
    `finish` are implemented explicitly even though Orekit supplies defaults;
    omitting them raises NoSuchMethodError the moment Orekit calls them.
    """

    def __init__(self, frame, diagnostics=None):
        self.frame = frame
        self.t, self.x, self.y, self.z = [], [], [], []
        self.vx, self.vy, self.vz = [], [], []
        self._diag = diagnostics          # (srp_force, params) or None
        self.p_srp, self.lit = [], []

    @JOverride
    def init(self, s0, t, step):
        pass

    @JOverride
    def finish(self, final_state):
        pass

    @JOverride
    def handleStep(self, state):
        pv = state.getPVCoordinates(self.frame)
        p, v = pv.getPosition(), pv.getVelocity()
        self.t.append(state.getDate().durationFrom(T0))
        self.x.append(p.getX()); self.y.append(p.getY()); self.z.append(p.getZ())
        self.vx.append(v.getX()); self.vy.append(v.getY()); self.vz.append(v.getZ())
        if self._diag is not None:
            srp_force, params, flux = self._diag
            a = srp_force.acceleration(state, params)
            self.p_srp.append(a.getX()*v.getX() + a.getY()*v.getY() + a.getZ()*v.getZ())
            self.lit.append(float(flux.getLightingRatio(state)))


# ---------------------------------------------------------------------------
# Force-model assembly
# ---------------------------------------------------------------------------
def build_forces(case: OrekitCase):
    """Return (force_models, srp_force_or_None, flux_model_or_None)."""
    forces = []
    # J2 only, degree 2 order 0, with the paper's constants.
    forces.append(J2OnlyPerturbation(MU_EARTH, R_EARTH, J2, EME2000))

    if case.use_drag:
        itrf = FramesFactory.getITRF(IERSConventions.IERS_2010, True)
        frame = itrf if case.corotating_atmosphere else EME2000
        ellipsoid = None
        if case.altitude_mode == "geodetic":
            ellipsoid = OneAxisEllipsoid(Constants.WGS84_EARTH_EQUATORIAL_RADIUS,
                                         Constants.WGS84_EARTH_FLATTENING, itrf)
        atm = US1976Atmosphere(frame, scaling=case.density_scale,
                               corotating=case.corotating_atmosphere,
                               altitude_mode=case.altitude_mode,
                               ellipsoid=ellipsoid)
        if case.drag_mode == "spherical":
            sensitive = spherical_drag(case.area_m2, case.cd)
        else:
            sensitive = drag_plate(case.area_m2, case.cd,
                                   case.absorption, case.specular)
        forces.append(DragForce(atm, sensitive))

    srp_force = flux = None
    if case.use_srp:
        # occulting radius 0 => nothing ever eclipsed (Fig.-3 "eclipse off")
        occulting_r = 0.0 if case.disable_eclipse else R_EARTH
        if case.sun_model == "paper":
            from .sun import AnalyticSun
            sun = AnalyticSun()
        else:
            sun = SUN
        flux = CylindricallyShadowedLightFluxModel(float(K_REF), sun, float(occulting_r))
        srp_force = RadiationPressureModel(
            flux, srp_plate(case.area_m2, case.cd, case.absorption, case.specular))
        forces.append(srp_force)
    return forces, srp_force, flux


def build_propagator(case: OrekitCase, want_diagnostics: bool = False):
    """Configured NumericalPropagator plus the recorder attached to it."""
    inc = math.radians(case.inclination)
    raan = math.radians(case.raan_deg)
    orbit = KeplerianOrbit(case.sma_m, case.ecc, inc, 0.0, raan, 0.0,
                           PositionAngleType.TRUE, EME2000, T0, MU_EARTH)

    n = case.normal_eci()
    attitude = fixed_inertial_attitude(n, EME2000)
    state0 = SpacecraftState(orbit, attitude.getAttitude(orbit, T0, EME2000)) \
        .withMass(case.mass_kg)

    if case.integrator == "rk4":
        integrator = ClassicalRungeKuttaIntegrator(float(case.dt))
    else:
        tols = NumericalPropagator.tolerances(case.pos_tol_m, orbit, OrbitType.CARTESIAN)
        integrator = DormandPrince853Integrator(1e-4, 300.0, tols[0], tols[1])

    prop = NumericalPropagator(integrator)
    # Integrate in Cartesian coordinates, as the paper's propagator does.
    prop.setOrbitType(OrbitType.CARTESIAN)
    prop.setAttitudeProvider(attitude)
    prop.setInitialState(state0)

    forces, srp_force, flux = build_forces(case)
    for f in forces:
        prop.addForceModel(f)

    diag = None
    if want_diagnostics and srp_force is not None:
        diag = (srp_force, srp_force.getParameters(T0), flux)
    rec = _Recorder(EME2000, diagnostics=diag)
    prop.getMultiplexer().add(float(case.dt), rec)
    return prop, rec, state0, n


# ---------------------------------------------------------------------------
# Element extraction
# ---------------------------------------------------------------------------
def osculating_elements(x, y, z, vx, vy, vz):
    """Vectorised osculating a [km], e, apogee/perigee altitude [km]."""
    r = np.stack([x, y, z], axis=-1)
    v = np.stack([vx, vy, vz], axis=-1)
    rn = np.linalg.norm(r, axis=-1)
    vn2 = np.einsum("ij,ij->i", v, v)
    a = -MU_EARTH / (2.0 * (vn2 / 2.0 - MU_EARTH / rn))
    h = np.cross(r, v)
    evec = np.cross(v, h) / MU_EARTH - r / rn[:, None]
    e = np.linalg.norm(evec, axis=-1)
    ha = a * (1 + e) - R_EARTH
    hp = a * (1 - e) - R_EARTH
    return a / 1000.0, e, ha / 1000.0, hp / 1000.0


def node_sample(t, z, *series):
    """Stroboscopic sampling at ascending-node crossings (z: - -> +).

    Same rule as core/offline_propagator.py: take the first sample at or after
    the sign change, without interpolation, so the two tools quantise the mean
    element series identically.
    """
    z = np.asarray(z)
    idx = np.where((z[:-1] < 0.0) & (z[1:] >= 0.0))[0] + 1
    return (np.asarray(t)[idx],) + tuple(np.asarray(s)[idx] for s in series)


def orbit_average(t, a, period):
    """Centred moving average over one orbital period (energy-based mean SMA).

    Identical to the averaging used for STK in
    "STK simulations"/validation/validate_vs_stk.py, so the STK, Orekit and
    open-source mean series are all defined the same way.
    """
    t = np.asarray(t); a = np.asarray(a)
    dt = t[1] - t[0]
    w = max(1, int(round(period / dt)))
    if w >= len(a):
        return t, a
    am = np.convolve(a, np.ones(w) / w, mode="valid")
    tt = t[(w - 1) // 2: (w - 1) // 2 + len(am)]
    return tt, am


def keplerian_period(sma_m: float) -> float:
    return 2.0 * math.pi * math.sqrt(sma_m ** 3 / MU_EARTH)


# ---------------------------------------------------------------------------
# Top-level driver
# ---------------------------------------------------------------------------
#: Two ways a decaying sail ends a propagation. The first is Orekit refusing to
#: evaluate an atmosphere below its validity floor. The second is the adaptive
#: integrator's step collapsing: deep in the atmosphere the density scale height
#: is short and the drag derivative stiff, so the step-size controller drives the
#: step under its own floor. For A/m = 10 m^2 kg^-1 both are the same physical
#: outcome -- the sail has reentered -- rather than numerical failures.
_DECAY_MARKERS = ("below the 100,000 m allowed threshold", "minimal step size")

#: A step-size collapse is only accepted as reentry if the orbit really was low
#: when it happened; otherwise it is a genuine numerical problem and must surface.
_DECAY_PERIGEE_CEILING_KM = 250.0


def propagate(case: OrekitCase, days: float, want_diagnostics: bool = False,
              tolerate_reentry: bool = True) -> dict:
    """Propagate `days` and return node-sampled mean elements (+ diagnostics).

    If the sail decays out of the integrable regime and `tolerate_reentry` is
    set, whatever was integrated before that point is returned with
    ``reentered=True`` rather than raising.
    """
    prop, rec, state0, n = build_propagator(case, want_diagnostics)
    reentered = False
    try:
        prop.propagate(T0, T0.shiftedBy(float(days) * 86400.0))
    except Exception as exc:
        if not (tolerate_reentry and any(m in str(exc) for m in _DECAY_MARKERS)):
            raise
        # Confirm the orbit was actually decaying before writing this off as
        # reentry -- a step collapse at altitude would be a real bug. Use the
        # lowest altitude reached anywhere in the run rather than the last
        # sample, since the failure can occur between two recorder ticks.
        if not rec.x:
            raise
        alt_min_km = min(
            math.sqrt(x * x + y * y + z * z) - R_EARTH
            for x, y, z in zip(rec.x, rec.y, rec.z)
        ) / 1e3
        if alt_min_km > _DECAY_PERIGEE_CEILING_KM:
            raise
        reentered = True

    t = np.asarray(rec.t)
    x, y, z = map(np.asarray, (rec.x, rec.y, rec.z))
    vx, vy, vz = map(np.asarray, (rec.vx, rec.vy, rec.vz))
    a, e, ha, hp = osculating_elements(x, y, z, vx, vy, vz)

    nt, na, ne, nha, nhp = node_sample(t, z, a, e, ha, hp)

    out = dict(sail_normal=n, t=t, osc_a=a, osc_e=e, z=z, reentered=reentered,
               span_days=float(t[-1] / 86400.0) if len(t) else 0.0,
               node_t=nt, node_a=na, node_e=ne, node_ha=nha, node_hp=nhp)
    if len(na):
        a0 = float(na[0])
        out.update(a0=a0,
                   da_max=float(np.max(na) - a0),
                   t_at_max_d=float(nt[int(np.argmax(na))] / 86400.0),
                   da_final=float(na[-1] - a0))
    if want_diagnostics and rec.p_srp:
        out["p_srp"] = np.asarray(rec.p_srp)
        out["lit"] = np.asarray(rec.lit)
    return out
