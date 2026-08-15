"""
V6 -- what actually drives the inter-tool drag spread?

The manuscript could only speculate about the origin of the order-of-magnitude
difference between STK's and the open-source propagator's 14-day drag decay,
listing three candidates: the atmosphere-relative velocity (co-rotation)
treatment, the geodetic-versus-geocentric altitude used for the density lookup,
and the definition of the secular element itself.

Orekit lets each of those be switched independently while everything else is
held fixed, so the speculation can be replaced with measured numbers. We also
add the modelling choice the manuscript identifies as the dominant uncertainty
but never varies: the atmosphere model itself.

Configurations, all J2 + drag, no SRP, spherical reference area, 14 days:

  baseline        paper convention: US-1976, geocentric altitude, no co-rotation
  co-rotating     atmosphere rigidly rotating with the ITRF
  geodetic        density looked up at WGS-84 ellipsoid height
  both            co-rotating and geodetic
  Harris-Priester Orekit's own built-in model
  NRLMSISE-00     Orekit's own built-in model, driven by the CSSI space-weather
                  file shipped in the Orekit data archive

Mean semi-major axis is reported under both definitions used in the study
(node-sampled and orbit-averaged) so the element-definition contribution is
visible too.

Writes results/v6_drag_decomposition.json and
reproduced_figures/orekit_drag_decomposition.png.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orekit_core.orekit_setup import boot, ROOT  # noqa: E402

boot()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from org.orekit.bodies import CelestialBodyFactory, OneAxisEllipsoid  # noqa: E402
from org.orekit.forces.drag import DragForce  # noqa: E402
from org.orekit.forces.gravity import J2OnlyPerturbation  # noqa: E402
from org.orekit.frames import FramesFactory  # noqa: E402
from org.orekit.models.earth.atmosphere import (  # noqa: E402
    HarrisPriester, NRLMSISE00,
)
from org.orekit.models.earth.atmosphere.data import CssiSpaceWeatherData  # noqa: E402
from org.orekit.orbits import KeplerianOrbit, OrbitType, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402
from org.orekit.propagation.numerical import NumericalPropagator  # noqa: E402
from org.orekit.utils import Constants, IERSConventions  # noqa: E402
from org.hipparchus.ode.nonstiff import ClassicalRungeKuttaIntegrator  # noqa: E402

import math  # noqa: E402

from orekit_core.attitude import fixed_inertial_attitude, raan_for_ltdn, sail_normal_eci  # noqa: E402
from orekit_core.atmosphere import US1976Atmosphere  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    MU_EARTH, R_EARTH, J2, SAIL_AREA, SAIL_MASS, CD, REPRO_PITCH_DEG, inclination_for,
)
from orekit_core.propagation import (  # noqa: E402
    EME2000, T0, OrekitCase, propagate, orbit_average, keplerian_period,
    osculating_elements, node_sample, _Recorder,
)
from orekit_core.spacecraft import spherical_drag  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "reproduced_figures")

DAYS = 14.0
DT = 30.0
LTDN = 14.0
RAAN = raan_for_ltdn(LTDN)
PITCH = REPRO_PITCH_DEG

BASELINE = "baseline (US-1976, geocentric, no co-rotation)"
GEODETIC_BASELINE = "geodetic altitude"
#: These take altitude above the WGS-84 ellipsoid, so they are compared against
#: the geodetic US-1976 baseline rather than the paper's geocentric one.
MODEL_CONFIGS = ("Harris-Priester (Orekit built-in)", "NRLMSISE-00 (Orekit built-in)")

ITRF = FramesFactory.getITRF(IERSConventions.IERS_2010, True)
WGS84 = OneAxisEllipsoid(Constants.WGS84_EARTH_EQUATORIAL_RADIUS,
                         Constants.WGS84_EARTH_FLATTENING, ITRF)
SUN_BODY = CelestialBodyFactory.getSun()


def run_with_atmosphere(alt_km, atmosphere, label):
    """Propagate the validation configuration with an arbitrary Orekit atmosphere."""
    inc = inclination_for(alt_km)
    n = sail_normal_eci(RAAN, inc, PITCH)
    orbit = KeplerianOrbit(R_EARTH + alt_km * 1e3, 1e-4, math.radians(inc), 0.0,
                           math.radians(RAAN), 0.0, PositionAngleType.TRUE,
                           EME2000, T0, MU_EARTH)
    att = fixed_inertial_attitude(n, EME2000)
    st0 = SpacecraftState(orbit, att.getAttitude(orbit, T0, EME2000)).withMass(SAIL_MASS)

    prop = NumericalPropagator(ClassicalRungeKuttaIntegrator(DT))
    prop.setOrbitType(OrbitType.CARTESIAN)
    prop.setAttitudeProvider(att)
    prop.setInitialState(st0)
    prop.addForceModel(J2OnlyPerturbation(MU_EARTH, R_EARTH, J2, EME2000))
    prop.addForceModel(DragForce(atmosphere, spherical_drag(SAIL_AREA, CD)))

    rec = _Recorder(EME2000)
    prop.getMultiplexer().add(DT, rec)

    reentered = False
    try:
        prop.propagate(T0, T0.shiftedBy(DAYS * 86400.0))
    except Exception as exc:
        # For A/m = 10 m^2 kg^-1 some atmosphere models drive the sail below
        # Orekit's 100 km validity floor inside the window. That is a physical
        # outcome, not a failure: keep what was integrated and flag it.
        if "below the 100,000 m allowed threshold" not in str(exc):
            raise
        reentered = True

    t = np.asarray(rec.t)
    x, y, z = map(np.asarray, (rec.x, rec.y, rec.z))
    vx, vy, vz = map(np.asarray, (rec.vx, rec.vy, rec.vz))
    a, e, ha, hp = osculating_elements(x, y, z, vx, vy, vz)
    nt, na = node_sample(t, z, a)
    period = keplerian_period(R_EARTH + alt_km * 1e3)
    at, aa = orbit_average(t, a, period)
    return dict(label=label, altitude_km=alt_km,
                node_t=nt, node_a=na,
                reentered=reentered,
                span_days=float(t[-1] / 86400.0),
                da_node_km=float(na[-1] - na[0]),
                da_orbitavg_km=float(aa[-1] - aa[0]))


def main():
    # Orekit's built-in atmospheres take altitude as height above the WGS-84
    # ellipsoid, so comparing them against the geocentric US-1976 baseline would
    # bundle in the altitude-convention switch that this script measures
    # separately. A second, geodetic US-1976 baseline is therefore included, and
    # the atmosphere-model factors are quoted against *that*.
    configs = []
    for alt in (700.0, 800.0):
        configs.append((alt, BASELINE,
                        US1976Atmosphere(EME2000, corotating=False)))
        configs.append((alt, "co-rotating atmosphere",
                        US1976Atmosphere(ITRF, corotating=True)))
        configs.append((alt, GEODETIC_BASELINE,
                        US1976Atmosphere(EME2000, corotating=False,
                                         altitude_mode="geodetic", ellipsoid=WGS84)))
        configs.append((alt, "co-rotating + geodetic",
                        US1976Atmosphere(ITRF, corotating=True,
                                         altitude_mode="geodetic", ellipsoid=WGS84)))
        configs.append((alt, "Harris-Priester (Orekit built-in)",
                        HarrisPriester(SUN_BODY, WGS84)))
        try:
            sw = CssiSpaceWeatherData("SpaceWeather-All-v1.2.txt")
            configs.append((alt, "NRLMSISE-00 (Orekit built-in)",
                            NRLMSISE00(sw, SUN_BODY, WGS84)))
        except Exception as exc:  # pragma: no cover - depends on data archive
            print(f"  (NRLMSISE-00 unavailable: {type(exc).__name__}: {exc})")

    rows, series = [], {}
    for alt, label, atm in configs:
        r = run_with_atmosphere(alt, atm, label)
        rows.append(dict(altitude_km=alt, config=label,
                         da_node_km=r["da_node_km"],
                         da_orbitavg_km=r["da_orbitavg_km"],
                         reentered=r["reentered"], span_days=r["span_days"]))
        series[(alt, label)] = r
        tail = (f"  [REENTRY at day {r['span_days']:.2f}]" if r["reentered"] else "")
        print(f"[{alt:.0f} km] {label:42s} "
              f"Delta a(14 d) = {r['da_node_km']:+9.3f} km (node)   "
              f"{r['da_orbitavg_km']:+9.3f} km (orbit-avg){tail}")

    # ---- ratios, each against the appropriate baseline ----------------------
    # Conventions are compared against the paper's own convention. Atmosphere
    # models are compared against the geodetic US-1976 baseline, because they
    # are themselves geodetic. Rows truncated by reentry are compared over the
    # window they actually completed, so the ratio is like for like.
    print("\nchange relative to the appropriate baseline:")
    for alt in (700.0, 800.0):
        base = next(r for r in rows if r["altitude_km"] == alt and r["config"] == BASELINE)
        geo = next(r for r in rows if r["altitude_km"] == alt and r["config"] == GEODETIC_BASELINE)
        for r in rows:
            if r["altitude_km"] != alt or r["config"] == BASELINE:
                continue
            is_model = r["config"] in MODEL_CONFIGS
            ref = geo if is_model else base
            r["baseline_used"] = ref["config"]

            if r["reentered"]:
                # same-window comparison: how far had the reference decayed by
                # the time this run stopped?
                s = series[(alt, ref["config"])]
                da_ref = float(np.interp(r["span_days"] * 86400.0,
                                         s["node_t"], s["node_a"] - s["node_a"][0]))
                r["baseline_da_same_window_km"] = da_ref
                ratio = r["da_node_km"] / da_ref if da_ref else float("nan")
                note = f"  (over its {r['span_days']:.1f}-day window)"
            else:
                ratio = (r["da_node_km"] / ref["da_node_km"]
                         if ref["da_node_km"] else float("nan"))
                note = ""
            r["ratio_to_baseline"] = float(ratio)
            print(f"  [{alt:.0f} km] {r['config']:42s} x{ratio:6.3f}  "
                  f"vs {'geodetic US-1976' if is_model else 'paper convention'}{note}")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), sharey=False)
    for ax, alt in zip(axes, (700.0, 800.0)):
        for (a_km, label), r in series.items():
            if a_km != alt:
                continue
            ax.plot(r["node_t"] / 86400, r["node_a"] - r["node_a"][0], lw=1.5, label=label)
        if alt == 700.0:
            ax.axhline(-7.0, color="k", ls="--", lw=1.2,
                       label="STK 14-day endpoint (reported)")
        ax.set_xlabel("time [days]")
        ax.set_ylabel(r"$\Delta a$ (mean) [km]")
        ax.set_title(f"{int(alt)} km", fontsize=10)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=6.5, loc="lower left")
    fig.suptitle("Drag modelling choices, isolated one at a time in Orekit", fontsize=10)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    out = os.path.join(FIGS, "orekit_drag_decomposition.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"\nwrote {out}")

    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, "v6_drag_decomposition.json")
    with open(p, "w") as f:
        json.dump(dict(days=DAYS, dt_s=DT, ltdn_h=LTDN, pitch_deg=PITCH, rows=rows),
                  f, indent=2)
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
