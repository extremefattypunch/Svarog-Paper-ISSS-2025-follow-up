"""
V10 -- thermospheric variability (Reviewer 1, major point 4).

The manuscript's US-1976 profile has no solar-activity dependence.  Here the
full force model (J2 + N-plate drag + eclipse-gated N-plate SRP, inertially
fixed normal, DP853 with eclipse events) is propagated with NRLMSISE-00 driven
by CONSTANT space-weather inputs at three activity levels, plus the CSSI
historical/predicted file for the actual epoch, and compared with the US-1976
baseline.  Reported: 14-day Delta a_max and Delta a(14 d) at the gain anchor,
and the drag-only 14-day decay, at 800 km and 700 km.

  level      F10.7 daily  F10.7 81-day mean   Ap
  low            70            70              4
  moderate      140           140             15
  high          200           200             40

Writes results/v10_space_weather.json and reproduced_figures/orekit_space_weather.png.
"""
from __future__ import annotations
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orekit_core.orekit_setup import boot, ROOT  # noqa: E402
boot()
import numpy as np  # noqa: E402
import jpype  # noqa: E402
from jpype import JImplements, JOverride  # noqa: E402
from org.hipparchus.ode.nonstiff import DormandPrince853Integrator  # noqa: E402
from org.orekit.bodies import CelestialBodyFactory, OneAxisEllipsoid  # noqa: E402
from org.orekit.forces.drag import DragForce  # noqa: E402
from org.orekit.forces.gravity import J2OnlyPerturbation  # noqa: E402
from org.orekit.forces.radiation import RadiationPressureModel, CylindricallyShadowedLightFluxModel  # noqa: E402
from org.orekit.frames import FramesFactory  # noqa: E402
from org.orekit.models.earth.atmosphere import NRLMSISE00  # noqa: E402
from org.orekit.models.earth.atmosphere.data import CssiSpaceWeatherData  # noqa: E402
from org.orekit.orbits import KeplerianOrbit, OrbitType, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402
from org.orekit.propagation.numerical import NumericalPropagator  # noqa: E402
from org.orekit.time import AbsoluteDate  # noqa: E402
from org.orekit.utils import Constants, IERSConventions  # noqa: E402

from orekit_core.atmosphere import US1976Atmosphere  # noqa: E402
from orekit_core.attitude import fixed_inertial_attitude, raan_for_ltdn, sail_normal_eci  # noqa: E402
from orekit_core.constants import MU_EARTH, R_EARTH, J2, K_REF, SAIL_AREA, SAIL_MASS, CD, ABSORPTION, SPECULAR, inclination_for  # noqa: E402
from orekit_core.propagation import EME2000, T0, _Recorder, osculating_elements, node_sample, _DECAY_MARKERS  # noqa: E402
from orekit_core.spacecraft import drag_plate, srp_plate  # noqa: E402

RESULTS = os.path.join(ROOT, "results"); FIGS = os.path.join(ROOT, "reproduced_figures")
DAYS = 14.0; DT_SAMPLE = 30.0
ITRF = FramesFactory.getITRF(IERSConventions.IERS_2010, True)
WGS84 = OneAxisEllipsoid(Constants.WGS84_EARTH_EQUATORIAL_RADIUS, Constants.WGS84_EARTH_FLATTENING, ITRF)
SUN = CelestialBodyFactory.getSun()

LEVELS = {"low (F10.7=70, Ap=4)": (70.0, 70.0, 4.0),
          "moderate (F10.7=140, Ap=15)": (140.0, 140.0, 15.0),
          "high (F10.7=200, Ap=40)": (200.0, 200.0, 40.0)}


def anchor_geometry():
    """Gain anchor from the open-source revision results if available."""
    p = os.path.join(os.path.dirname(ROOT), "STK simulations", "results", "revision", "cases.json")
    if os.path.exists(p):
        g = json.load(open(p))["cases"]["gain"]
        return float(g["ltan_h"]), float(g["pitch_deg"])
    return 14.0, 34.0


@JImplements("org.orekit.models.earth.atmosphere.NRLMSISE00InputParameters")
class ConstantSpaceWeather:
    def __init__(self, f107, f107a, ap):
        self.f107, self.f107a, self.ap = float(f107), float(f107a), float(ap)

    @JOverride
    def getMinDate(self):
        return AbsoluteDate.PAST_INFINITY

    @JOverride
    def getMaxDate(self):
        return AbsoluteDate.FUTURE_INFINITY

    @JOverride
    def getDailyFlux(self, date):
        return self.f107

    @JOverride
    def getAverageFlux(self, date):
        return self.f107a

    @JOverride
    def getAp(self, date):
        arr = jpype.JArray(jpype.JDouble)(7)
        for i in range(7):
            arr[i] = self.ap
        return arr


def run(alt_km, atm, ltan, pitch, use_srp=True, label=""):
    inc = inclination_for(alt_km); raan = raan_for_ltdn(ltan)
    n = sail_normal_eci(raan, inc, pitch)
    orbit = KeplerianOrbit(R_EARTH + alt_km * 1e3, 1e-4, math.radians(inc), 0.0, math.radians(raan), 0.0,
                           PositionAngleType.TRUE, EME2000, T0, MU_EARTH)
    att = fixed_inertial_attitude(n, EME2000)
    st0 = SpacecraftState(orbit, att.getAttitude(orbit, T0, EME2000)).withMass(SAIL_MASS)
    tols = NumericalPropagator.tolerances(1e-4, orbit, OrbitType.CARTESIAN)
    prop = NumericalPropagator(DormandPrince853Integrator(1e-4, 300.0, tols[0], tols[1]))
    prop.setOrbitType(OrbitType.CARTESIAN); prop.setAttitudeProvider(att); prop.setInitialState(st0)
    prop.addForceModel(J2OnlyPerturbation(MU_EARTH, R_EARTH, J2, EME2000))
    prop.addForceModel(DragForce(atm, drag_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR)))
    if use_srp:
        flux = CylindricallyShadowedLightFluxModel(float(K_REF), SUN, float(R_EARTH))
        prop.addForceModel(RadiationPressureModel(flux, srp_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR)))
    rec = _Recorder(EME2000); prop.getMultiplexer().add(DT_SAMPLE, rec)
    reentered = False
    try:
        prop.propagate(T0, T0.shiftedBy(DAYS * 86400.0))
    except Exception as exc:
        if not any(m in str(exc) for m in _DECAY_MARKERS):
            raise
        reentered = True
    t = np.asarray(rec.t); x, y, z = map(np.asarray, (rec.x, rec.y, rec.z)); vx, vy, vz = map(np.asarray, (rec.vx, rec.vy, rec.vz))
    a, e, ha, hp = osculating_elements(x, y, z, vx, vy, vz)
    nt, na = node_sample(t, z, a)
    da = na - na[0]
    out = dict(label=label, altitude_km=alt_km, use_srp=use_srp, reentered=reentered, span_days=float(t[-1] / 86400.0),
               da_max_km=float(da.max()), da_final_km=float(da[-1]), t_at_max_d=float(nt[int(np.argmax(da))] / 86400.0))
    print(f"[{alt_km:.0f} km] {label:34s} srp={use_srp!s:5s} da_max={out['da_max_km']:+8.3f} da14={out['da_final_km']:+9.3f} km"
          + ("  REENTRY" if reentered else ""))
    return out, nt, da


REENTRY_MARKERS = tuple(_DECAY_MARKERS) + ("Infinite value", "NRLMSISE00", "altitude", "Altitude")
PARTIAL = os.path.join(RESULTS, "v10_partial.json")


def _load_partial():
    if os.path.exists(PARTIAL):
        with open(PARTIAL) as f:
            return json.load(f)
    return []


def _save_partial(rows):
    with open(PARTIAL, "w") as f:
        json.dump(rows, f, indent=1)


def run_safe(alt_km, atm, ltan, pitch, use_srp, label):
    """run() with re-entry (including NRLMSISE-00 'infinite density' inside the dense
    atmosphere) recorded instead of raised; the recorder keeps the samples up to the
    failure so span_days is the re-entry time."""
    try:
        return run(alt_km, atm, ltan, pitch, use_srp, label)
    except Exception as exc:
        if not any(m in str(exc) for m in REENTRY_MARKERS):
            raise
        out = dict(label=label, altitude_km=alt_km, use_srp=use_srp, reentered=True, span_days=None,
                   da_max_km=0.0, da_final_km=None, t_at_max_d=None)
        print(f"[{alt_km:.0f} km] {label:34s} srp={use_srp!s:5s} RE-ENTRY within the window ({str(exc)[:60]})")
        return out, None, None


def main():
    ltan, pitch = anchor_geometry()
    atmos = {"US-1976 (manuscript baseline)": US1976Atmosphere(EME2000, corotating=False)}
    for lab, (f, fa, ap) in LEVELS.items():
        atmos[f"NRLMSISE-00 {lab}"] = NRLMSISE00(ConstantSpaceWeather(f, fa, ap), SUN, WGS84)
    try:
        atmos["NRLMSISE-00 CSSI file (epoch Jan 2026)"] = NRLMSISE00(CssiSpaceWeatherData("SpaceWeather-All-v1.2.txt"), SUN, WGS84)
    except Exception as exc:
        print("(CSSI space weather unavailable:", exc, ")")
    rows = _load_partial()
    done = {(r["altitude_km"], r["label"], r["use_srp"]) for r in rows}
    for alt in (800.0, 700.0):
        for lab, atm in atmos.items():
            for use_srp in (True, False):
                if (alt, lab, use_srp) in done:
                    continue
                o, nt, da = run_safe(alt, atm, ltan, pitch, use_srp, lab)
                rows.append(o); _save_partial(rows)
    os.makedirs(RESULTS, exist_ok=True)
    out = dict(days=DAYS, anchor=dict(ltan_h=ltan, pitch_deg=pitch), levels=LEVELS, rows=rows,
               note="14-day full-model (SRP on) and drag-only (SRP off) runs at the gain-anchor geometry; DP853 with eclipse events; NRLMSISE-00 evaluated with Orekit's own conventions (geodetic altitude, co-rotation)")
    with open(os.path.join(RESULTS, "v10_space_weather.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("wrote results/v10_space_weather.json")
    make_figure(rows, ltan, pitch)


def make_figure(rows, ltan, pitch):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    labels = ["US-1976 (manuscript baseline)"] + [f"NRLMSISE-00 {k}" for k in LEVELS] + ["NRLMSISE-00 CSSI file (epoch Jan 2026)"]
    short = ["US-1976", "NRLMSISE-00\nlow (70, 4)", "NRLMSISE-00\nmoderate (140, 15)", "NRLMSISE-00\nhigh (200, 40)", "NRLMSISE-00\nCSSI, Jan 2026"]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.0))
    for ax, alt in zip(axes, (800.0, 700.0)):
        x = np.arange(len(labels)); w = 0.36
        for k, (srp, col, lab) in enumerate(((True, "C0", "full model (SRP on): $\\Delta a(14\\,\\mathrm{d})$"), (False, "C3", "drag only: $\\Delta a(14\\,\\mathrm{d})$"))):
            vals, hatch = [], []
            for L in labels:
                r = next((r for r in rows if r["altitude_km"] == alt and r["label"] == L and r["use_srp"] == srp), None)
                if r is None:
                    vals.append(np.nan); hatch.append(False)
                elif r.get("reentered"):
                    vals.append(np.nan); hatch.append(True)
                else:
                    vals.append(r["da_final_km"]); hatch.append(bool(r.get("reentered")))
            bars = ax.bar(x + (k - 0.5) * w, [0 if np.isnan(v) else v for v in vals], w, color=col, label=lab, alpha=0.9)
            for xi, v, h in zip(x + (k - 0.5) * w, vals, hatch):
                if np.isnan(v):
                    ax.text(xi, -1.0, "re-entry", rotation=90, ha="center", va="top", fontsize=7, color=col)
        for L, xi in zip(labels, x):
            r = next((r for r in rows if r["altitude_km"] == alt and r["label"] == L and r["use_srp"]), None)
            if r is not None and r["da_max_km"] > 0:
                ax.plot(xi - 0.5 * w, r["da_max_km"], "k*", ms=9, zorder=5, label=r"$\Delta a_{\max,14\mathrm{d}}$ (SRP on)" if L == labels[0] or ax.get_legend_handles_labels()[1].count(r"$\Delta a_{\max,14\mathrm{d}}$ (SRP on)") == 0 else None)
        ax.axhline(0, color="k", lw=0.6); ax.set_xticks(x); ax.set_xticklabels(short, fontsize=7.5)
        ax.set_title(f"{alt:.0f} km, LTAN {ltan:.1f} h, pitch {pitch:+.0f}°", fontsize=10); ax.set_ylabel("$\\Delta a$ over 14 d [km]")
        ax.grid(axis="y", alpha=0.3)
    h, l = axes[0].get_legend_handles_labels(); seen = {}
    for hh, ll in zip(h, l):
        seen.setdefault(ll, hh)
    axes[0].legend(list(seen.values()), list(seen.keys()), fontsize=7.5, loc="lower left")
    fig.tight_layout(); os.makedirs(FIGS, exist_ok=True)
    p = os.path.join(FIGS, "orekit_space_weather.png"); fig.savefig(p, dpi=200); print("wrote", p)
    paper = os.path.join(os.path.dirname(ROOT), "Figures", "r_space_weather.png")
    try:
        fig.savefig(paper, dpi=200); print("wrote", paper)
    except Exception as exc:
        print("(could not write the paper figure:", exc, ")")
    plt.close(fig)


if __name__ == "__main__":
    if "--replot" in sys.argv:
        with open(os.path.join(RESULTS, "v10_space_weather.json")) as f:
            d = json.load(f)
        make_figure(d["rows"], d["anchor"]["ltan_h"], d["anchor"]["pitch_deg"])
    else:
        main()
