"""
Revision cross-validation of the open-source propagator against STK Astrogator
(STK Engine 13.0.1, agi.stk13 Object Model, CPython 3.12).

Two configuration errors in the submitted STK build were found by reading STK's
effective inputs back during propagation (rev_stk_retest.py, rev_stk_probe.py):
  (1) the Astrogator Initial State fuel tank carried its default 50 kg of fuel,
      so the propagated mass was 60 kg rather than 10 kg (A/m 1.67 not 10);
  (2) IAgOrientationQuaternion.AssignQuaternion takes (qx, qy, qz, qs); the
      scalar-first tuple was passed, mis-orienting the sail plate (effective SRP
      area 16 m^2 instead of A cos(alpha) = 83 m^2).
Both are fixed in core/astrogator_mcs.build_satellite.  This script re-runs the
comparison with the corrected build and keeps the as-submitted drag case for the
record.

  A. two-body + J2                          700, 800 km   14 d
  B. J2 + spherical US-1976 drag            700, 800 km   14 d   (+ default-tank variant)
  C. J2 + N-plate drag (A|cos theta|)        700, 800 km   14 d
  D. J2 + N-plate SRP, no drag               800 km, eclipse on / off   14 d
  E. full model at the gain anchor           800 km, eclipse on / off   14 d; 700 km anchor 14 d
  F. full model, gain anchor                 800 km   75 d   (--long)

Both tools are compared on the same mean-element definition: the osculating
semi-major axis sampled every 60 s and averaged over one orbital period.

Usage: python validation/rev_stk_validation.py [--long] [--ltan H --pitch DEG]
Writes results/revision/stk_validation.json, stk_validation_series.json and
Figures/r_stk_validation.png.
"""
from __future__ import annotations
import os, sys, math, json, time, argparse, traceback
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
os.environ.setdefault("ANSYSLMD_LICENSE_FILE", "1055@localhost")
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.attitude import inertial_sail_normal
from core.orbit_init import sun_direction_eci, raan_from_ltan
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from runners.rev_common import FIGURES, RESULTS, INC, DT_PROD, mpl, load_json

EPOCH = "1 Jan 2026 12:00:00.000"; RE = 6378.1363; MU = 3.986004418e14
STEP = 60.0
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)


def period_of(alt): return 2 * math.pi * math.sqrt((RE + alt) ** 3 * 1e9 / MU)


def orbit_average(t, a, period):
    dt = t[1] - t[0]; w = max(1, int(round(period / dt)))
    if w >= len(a): return t, a
    am = np.convolve(a, np.ones(w) / w, mode="valid")
    return t[(w - 1) // 2:(w - 1) // 2 + len(am)], am


def stk_mean_series(sat, alt, days):
    stop = _add_seconds_to_iso(EPOCH, days * 86400.0)
    grp = sat.DataProviders.Item("Classical Elements").Group.Item("ICRF")
    ds = grp.ExecElements(EPOCH, stop, STEP, ["Time", "Semi-major Axis"])
    for i in range(ds.DataSets.Count):
        if ds.DataSets.Item(i).ElementName == "Semi-major Axis":
            a = np.array(ds.DataSets.Item(i).GetValues(), dtype=float)
    t = np.arange(len(a)) * STEP
    tt, am = orbit_average(t, a, period_of(alt))
    return tt, am


def opensource_mean_series(sc: SailCase, days):
    """Same mean definition as STK: osculating a every 60 s, orbit-averaged."""
    stride = max(1, int(round(STEP / sc.dt)))
    r = propagate(sc, days, want_forces=True, force_stride=stride)
    F = r["forces"]; t = F[:, 0]; a = F[:, 8]
    tt, am = orbit_average(t, a, period_of(sc.altitude_km))
    return tt, am, r


def av_first(sat, group, el, days):
    try:
        g = sat.DataProviders.Item("Astrogator Values").Group.Item(group)
        ds = g.ExecElements(EPOCH, _add_seconds_to_iso(EPOCH, days * 86400.0), STEP, ["Time", el])
        for i in range(ds.DataSets.Count):
            d = ds.DataSets.Item(i)
            if d.ElementName == el:
                v = np.array(d.GetValues(), dtype=float); return float(v[0])
    except Exception:
        return None


def density_readback(sat, alt, days):
    """STK's applied density (Astrogator Values/Environment/AtmosDensity, kg/km^3)
    against the open-source US-1976 interpolation at the same geocentric altitude."""
    from plugins.flatplate_drag_hpop import density_us1976_kg_m3
    stop = _add_seconds_to_iso(EPOCH, days * 86400.0)
    try:
        g = sat.DataProviders.Item("Astrogator Values").Group.Item("Environment")
        ds = g.ExecElements(EPOCH, stop, STEP, ["Time", "AtmosDensity"])
        rho = None
        for i in range(ds.DataSets.Count):
            if ds.DataSets.Item(i).ElementName == "AtmosDensity":
                rho = np.array(ds.DataSets.Item(i).GetValues(), dtype=float) * 1e-9
        grp = sat.DataProviders.Item("Cartesian Position").Group.Item("ICRF")
        ds2 = grp.ExecElements(EPOCH, stop, STEP, ["Time", "x", "y", "z"])
        xyz = {}
        for i in range(ds2.DataSets.Count):
            nm = ds2.DataSets.Item(i).ElementName
            if nm in ("x", "y", "z"): xyz[nm] = np.array(ds2.DataSets.Item(i).GetValues(), dtype=float)
        rmag = np.sqrt(xyz["x"] ** 2 + xyz["y"] ** 2 + xyz["z"] ** 2); h = rmag - RE
        n = min(len(rho), len(h)); rho = rho[:n]; h = h[:n]
        ours = np.array([density_us1976_kg_m3(hh * 1e3) for hh in h])
        ratio = rho / ours
        return dict(n=int(n), h_min_km=float(h.min()), h_max_km=float(h.max()),
                    stk_rho_first=float(rho[0]), ours_rho_first=float(ours[0]),
                    ratio_mean=float(ratio.mean()), ratio_min=float(ratio.min()), ratio_max=float(ratio.max()),
                    note="ratio = STK density / open-source US-1976 interpolation at the same geocentric altitude")
    except Exception as e:
        return dict(error=str(e)[:200])


def run_case(root, name, alt, ltan, pitch, days, use_drag, use_srp, drag_model="nplate",
             disable_eclipse=False, zero_fuel=True, series=None, res=None, note=""):
    inc = INC[alt]; raan = raan_from_ltan(ltan, JD_EPOCH)
    n = inertial_sail_normal(sun_direction_eci(JD_EPOCH), raan, inc, pitch, 0.0)
    # The centred one-period average is undefined within T/2 of either end of the
    # propagation, so propagate one extra period and take the window [T/2, T/2 + days]:
    # the quoted change then spans exactly `days`, between two centred orbit means.
    T = period_of(alt); ext_days = days + T / 86400.0
    rc = RunCase(name=name, altitude_km=alt, inc_deg=inc, raan_deg=raan, sma_km=RE + alt, ecc=1e-4,
                 sail_normal_eci=n, epoch_iso=EPOCH, duration_sec=ext_days * 86400.0, step_sec=STEP,
                 sail=SailParams(), disable_eclipse=disable_eclipse)
    t0 = time.time()
    sat, drv = build_satellite(root, rc, sat_name=name, use_drag=use_drag, use_srp=use_srp,
                               drag_model=drag_model, zero_fuel=zero_fuel)
    run_mcs(drv); wall = time.time() - t0
    ts, as_ = stk_mean_series(sat, alt, ext_days)
    sc = SailCase(altitude_km=alt, inc_deg=inc, raan_deg=raan, pitch_deg=pitch, dt=DT_PROD,
                  use_drag=use_drag, use_srp=use_srp, drag_mode=drag_model, disable_eclipse=disable_eclipse)
    to, ao, r = opensource_mean_series(sc, ext_days)
    w0, w1 = T / 2.0, T / 2.0 + days * 86400.0
    a_s0, a_s1 = np.interp(w0, ts, as_), np.interp(w1, ts, as_)
    a_o0, a_o1 = np.interp(w0, to, ao), np.interp(w1, to, ao)
    m_o = (to >= w0) & (to <= w1)
    tw = to[m_o] - w0
    da_o = ao[m_o] - a_o0
    da_s_i = np.interp(to[m_o], ts, as_) - a_s0
    row = dict(name=name, note=note, altitude_km=alt, ltan_h=ltan, pitch_deg=pitch, days=days,
               window_days=float((w1 - w0) / 86400.0),
               use_drag=use_drag, use_srp=use_srp, drag_model=drag_model if use_drag else None,
               eclipse=(not disable_eclipse) if use_srp else None, fuel_zeroed=zero_fuel,
               stk_da_end_km=float(a_s1 - a_s0), opensource_da_end_km=float(a_o1 - a_o0),
               stk_da_max_km=float(da_s_i.max()), opensource_da_max_km=float(da_o.max()),
               max_abs_diff_km=float(np.max(np.abs(da_o - da_s_i))),
               rms_diff_km=float(np.sqrt(np.mean((da_o - da_s_i) ** 2))),
               stk_srp_area_first_m2=av_first(sat, "Spacecraft Properties", "SRPArea", ext_days) if use_srp else None,
               stk_drag_area_first_m2=av_first(sat, "Spacecraft Properties", "DragArea", ext_days) if use_drag else None,
               stk_wall_s=wall)
    if r.get("reentry_day") is not None: row["opensource_reentry_day"] = r["reentry_day"]
    if use_drag and drag_model == "spherical" and zero_fuel:
        row["density_tabulation"] = density_readback(sat, alt, ext_days)
    log(f"[{name:12s}] {note:38s} STK {row['stk_da_end_km']:+9.3f} km | open-source {row['opensource_da_end_km']:+9.3f} km | "
        f"max|diff| {row['max_abs_diff_km']:.3f} km | peak STK {da_s_i.max():+.3f} / OS {da_o.max():+.3f} | {wall:.0f}s")
    if res is not None: res.append(row)
    if series is not None:
        series[name] = dict(t_d=(tw / 86400.0).tolist(), stk=da_s_i.tolist(), opensource=da_o.tolist())
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", action="store_true", help="also run the 75-day full-model case")
    ap.add_argument("--ltan", type=float, default=None); ap.add_argument("--pitch", type=float, default=None)
    ap.add_argument("--replot", action="store_true", help="only redraw the figure from the saved series")
    args = ap.parse_args()
    if args.replot:
        with open(os.path.join(RESULTS, "stk_validation.json"), encoding="utf-8") as f:
            anchor = json.load(f)["anchor"]
        with open(os.path.join(RESULTS, "stk_validation_series.json"), encoding="utf-8") as f:
            make_figure(json.load(f), anchor["ltan_h"], anchor["pitch_deg"])
        return
    # gain anchor: from cases.json if available, else the preliminary geometry
    ltan, pitch = 14.0, 34.0
    try:
        cj = load_json("cases.json"); g = cj["cases"]["gain"]; ltan, pitch = float(g["ltan_h"]), float(g["pitch_deg"])
    except Exception:
        pass
    if args.ltan is not None: ltan = args.ltan
    if args.pitch is not None: pitch = args.pitch
    log(f"gain anchor: 800 km, LTAN {ltan:.2f} h, pitch {pitch:.1f} deg")

    from agi.stk13.stkengine import STKEngine
    res, series = [], {}
    out = dict(stk_engine=None, python=sys.version.split()[0], step_s=STEP, dt_opensource_s=DT_PROD,
               anchor=dict(altitude_km=800.0, ltan_h=ltan, pitch_deg=pitch), rows=res, log=LOG)
    app = STKEngine.StartApplication(noGraphics=True); root = app.NewObjectRoot()
    try:
        root.NewScenario("RevValidation")
        out["stk_engine"] = str(root.ExecuteCommand("GetSTKVersion /").Item(0)); log(out["stk_engine"])
        for alt in (700.0, 800.0):
            a = int(alt)
            run_case(root, f"J2_{a}", alt, ltan, pitch, 14.0, False, False, series=series, res=res, note="two-body + J2")
            run_case(root, f"DragSph_{a}", alt, ltan, pitch, 14.0, True, False, "spherical", series=series, res=res, note="J2 + spherical drag (corrected)")
            run_case(root, f"DragSphTank_{a}", alt, ltan, pitch, 14.0, True, False, "spherical", zero_fuel=False, series=series, res=res, note="J2 + spherical drag (as submitted: default tank)")
            run_case(root, f"DragNp_{a}", alt, ltan, pitch, 14.0, True, False, "nplate", series=series, res=res, note="J2 + N-plate drag")
        run_case(root, "Srp_800", 800.0, ltan, pitch, 14.0, False, True, series=series, res=res, note="J2 + N-plate SRP, eclipse on")
        run_case(root, "SrpNoEcl_800", 800.0, ltan, pitch, 14.0, False, True, disable_eclipse=True, series=series, res=res, note="J2 + N-plate SRP, eclipse off")
        run_case(root, "Full_800", 800.0, ltan, pitch, 14.0, True, True, series=series, res=res, note="full model, eclipse on (gain anchor)")
        run_case(root, "FullNoEcl_800", 800.0, ltan, pitch, 14.0, True, True, disable_eclipse=True, series=series, res=res, note="full model, eclipse off (gain anchor)")
        run_case(root, "Full_700", 700.0, 12.266, 24.8, 14.0, True, True, series=series, res=res, note="full model, 700 km former anchor")
        if args.long:
            run_case(root, "Full_800_75d", 800.0, ltan, pitch, 75.0, True, True, series=series, res=res, note="full model, 75 d (gain anchor)")
    finally:
        app.ShutDown()
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "stk_validation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    with open(os.path.join(RESULTS, "stk_validation_series.json"), "w", encoding="utf-8") as f:
        json.dump(series, f)
    log("wrote stk_validation.json")

    make_figure(series, ltan, pitch)


def make_figure(series, ltan, pitch):
    mpl()
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.6))
    ax = axes[0, 0]
    # the centred one-period mean keeps a ~50 m residual of the J2 short period in both
    # tools; the informative quantity for the conservative dynamics is the difference
    for a, col in ((700, "C0"), (800, "C1")):
        s = series[f"J2_{a}"]; t = np.array(s["t_d"]); d = (np.array(s["stk"]) - np.array(s["opensource"])) * 1e3
        w = max(1, int(round(period_of(float(a)) / STEP)))          # one orbit of 60 s samples
        n = len(d) // w
        env = np.abs(d[:n * w]).reshape(n, w).max(axis=1); tm = t[:n * w].reshape(n, w).mean(axis=1)
        ax.plot(tm, env, col, lw=1.4, label=f"{a} km (max {np.max(np.abs(d)):.2f} m)")
    ax.set_ylim(bottom=0)
    ax.set_title("(a) two-body + $J_2$: |STK $-$ open-source|, per-orbit maximum"); ax.set_ylabel("difference in mean $a$ [m]")
    ax = axes[0, 1]
    for a, col in ((700, "C0"), (800, "C1")):
        s = series[f"DragSph_{a}"]; ax.plot(s["t_d"], s["stk"], col, lw=1.5, label=f"STK, {a} km"); ax.plot(s["t_d"], s["opensource"], col + "--", lw=1.2, label=f"open-source, {a} km")
        s = series[f"DragSphTank_{a}"]; ax.plot(s["t_d"], s["stk"], col + ":", lw=1.0, label=f"STK as submitted, {a} km")
    ax.set_title("(b) $J_2$ + spherical US-1976 drag")
    ax = axes[1, 0]
    for a, col in ((700, "C0"), (800, "C1")):
        s = series[f"DragNp_{a}"]; ax.plot(s["t_d"], s["stk"], col, lw=1.5, label=f"STK, {a} km"); ax.plot(s["t_d"], s["opensource"], col + "--", lw=1.2, label=f"open-source, {a} km")
    ax.set_title(r"(c) $J_2$ + N-plate drag, $A|\cos\theta|$"); ax.set_xlabel("time [d]"); ax.set_ylabel(r"mean $a-a_0$ [km]")
    ax = axes[1, 1]
    for key, col, lab in (("Srp_800", "C2", "SRP only, eclipse on"), ("SrpNoEcl_800", "C3", "SRP only, eclipse off"),
                          ("Full_800", "C4", "full model, eclipse on"), ("FullNoEcl_800", "C5", "full model, eclipse off")):
        s = series[key]; ax.plot(s["t_d"], s["stk"], col, lw=1.5, label=f"STK: {lab}"); ax.plot(s["t_d"], s["opensource"], col + "--", lw=1.2, label=f"open-source: {lab}")
    ax.axhline(0, color="k", lw=0.6); ax.set_title(f"(d) 800 km gain anchor (LTAN {ltan:.1f} h, pitch {pitch:.0f}$^\\circ$)"); ax.set_xlabel("time [d]")
    for ax in axes.flat: ax.grid(alpha=0.3); ax.legend(fontsize=7.5)
    fig.tight_layout(); fig.savefig(os.path.join(FIGURES, "r_stk_validation.png"), dpi=200); plt.close(fig)
    log("figure written")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
