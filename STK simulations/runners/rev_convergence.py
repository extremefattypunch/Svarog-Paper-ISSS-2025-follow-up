"""
Step-size convergence of the fixed-step RK4 propagator for the eclipse-gated
force model (manuscript Section 9, numerical caveat; answers Reviewer 2's point
on the trustworthiness of the open-source reproduction).

Runs the 14-day 800 km gain anchor and the 700 km legacy anchor at a ladder of
step sizes, for (i) the full model, (ii) SRP with the umbra disabled and
(iii) drag only.  The Orekit DP853 + eclipse-event reference values are taken
from ../Orekit simulations/results/v7_eclipse_discontinuity.json when present.

Usage: python runners/rev_convergence.py
"""
from __future__ import annotations
import os, sys, time, json
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from runners.rev_common import (save_json, fig_path, mpl, GAIN800, ANCHOR700_OLD,
                                N_WORKERS, PAPER_ROOT, RESULTS)
from core.offline_propagator import SailCase, propagate

DAYS = 14.0
STEPS = [120.0, 60.0, 30.0, 15.0, 10.0, 7.5, 5.0, 2.5]
CONFIGS = {
    "full model (eclipse-gated SRP + drag)": dict(),
    "SRP with umbra disabled + drag": dict(disable_eclipse=True),
    "drag only (no SRP)": dict(use_srp=False),
}


def one(args):
    geo, cfg_name, dt = args
    kw = dict(CONFIGS[cfg_name]); kw.update(geo); kw["dt"] = dt
    t0 = time.time()
    r = propagate(SailCase(**kw), DAYS)
    return geo["altitude_km"], cfg_name, dt, r["da_max"], r["da_final"], r["da_at_14d"], time.time() - t0


def main():
    jobs = [(geo, c, dt) for geo in (GAIN800, ANCHOR700_OLD) for c in CONFIGS for dt in STEPS]
    rows = []
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        for alt, c, dt, dmax, dfin, d14, sec in ex.map(one, jobs):
            rows.append(dict(altitude_km=alt, config=c, dt_s=dt, da_max_km=dmax,
                             da_final_km=dfin, da_at_14d_km=d14, wall_s=sec))
            print(f"{alt:.0f} km | {c:38s} | dt={dt:6.1f} s | da_max={dmax:+8.4f} | da14={d14:+8.4f} | {sec:5.1f}s")

    # Orekit reference (DP853 with eclipse events), if the v7 file carries it
    # v7 names -> this script's config names; v7["reference"] is the tightest DP853 run
    NAME_MAP = {"full model (eclipse-gated SRP + drag)": "full model (eclipse-gated SRP)",
                "SRP with umbra disabled + drag": "SRP with umbra disabled",
                "drag only (no SRP)": "drag only, no SRP"}
    ref = {}
    v7 = os.path.join(PAPER_ROOT, "Orekit simulations", "results", "v7_eclipse_discontinuity.json")
    if os.path.exists(v7):
        with open(v7) as f:
            d = json.load(f)
        src = d.get("reference") or {}
        if not src and "adaptive" in d:      # tightest tolerance = last entry
            src = {name: lst[-1]["da_final_km"] for name, lst in d["adaptive"].items()}
        if not src and "fixed_step" in d:    # finest fixed step as a proxy
            src = {name: min(lst, key=lambda x: x["dt_s"])["da_final_km"] for name, lst in d["fixed_step"].items()}
        ref = {c: float(src[NAME_MAP[c]]) for c in CONFIGS if NAME_MAP.get(c) in src}
        ref_geom = dict(ltan_h=d.get("ltdn_h", d.get("ltan_h")), pitch_deg=d.get("pitch_deg"))
    else:
        ref_geom = None
    out = dict(days=DAYS, steps_s=STEPS, rows=rows, orekit_reference=ref, orekit_reference_geometry=ref_geom,
               note=("Orekit DP853 + eclipse-event reference (800 km): " + ", ".join(f"{c}: {v:+.4f} km" for c, v in ref.items()))
               if ref else "no Orekit reference found")
    save_json("convergence.json", out)

    plot(rows, ref)


def plot(rows, ref):
    """Top row: Delta a(14 d) vs step. Bottom row: deviation from the reference
    (Orekit DP853 at 800 km; the finest RK4 step at 700 km) on a log scale, which
    exposes the first-order convergence of the eclipse-gated configuration."""
    plt = mpl()
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 6.6), sharex="col")
    for col_i, alt in enumerate((800.0, 700.0)):
        ax, axd = axes[0, col_i], axes[1, col_i]
        for c, mk, colr in zip(CONFIGS, ("o-", "s--", "^:"), ("C0", "C1", "C2")):
            sel = sorted([r for r in rows if r["altitude_km"] == alt and r["config"] == c], key=lambda r: r["dt_s"])
            dts = [r["dt_s"] for r in sel]; vals = [r["da_at_14d_km"] for r in sel]
            ax.plot(dts, vals, mk, ms=4, lw=1.2, label=c, color=colr)
            if alt == 800.0 and ref and c in ref:
                ax.axhline(ref[c], color=colr, lw=0.8, ls="-.",
                           label="Orekit DP853 + eclipse events" if c == list(CONFIGS)[0] else None)
                base = ref[c]; blab = "DP853"
            else:
                base = vals[0]; blab = f"{dts[0]:g} s"
            dev = [abs(v - base) for v, d in zip(vals, dts) if not (alt != 800.0 and d == dts[0])]
            ddt = [d for d in dts if not (alt != 800.0 and d == dts[0])]
            axd.plot(ddt, [max(x, 1e-5) for x in dev], mk, ms=4, lw=1.2, color=colr, label=f"{c} (vs {blab})")
        for order, ls in ((1, ":"), (4, "--")):
            x = np.array([2.5, 60.0]); y0 = 0.02 if order == 1 else 0.002
            axd.plot(x, y0 * (x / 2.5) ** order, "k" + ls, lw=0.7, label=f"slope {order}")
        ax.set_xscale("log"); axd.set_xscale("log"); axd.set_yscale("log")
        ax.set_ylabel("$\\Delta a(14\\,\\mathrm{d})$ [km]"); axd.set_ylabel("|deviation from reference| [km]")
        axd.set_xlabel("RK4 step $\\Delta t$ [s]")
        ax.set_title(f"{alt:.0f} km, LTAN {GAIN800['ltan_h'] if alt==800 else ANCHOR700_OLD['ltan_h']:.2f} h, "
                     f"pitch {GAIN800['pitch_deg'] if alt==800 else ANCHOR700_OLD['pitch_deg']:.1f}°")
        ax.legend(fontsize=6.5, loc="best"); axd.legend(fontsize=6, loc="best")
    fig.tight_layout(); p = fig_path("r_convergence.png"); fig.savefig(p); plt.close(fig); print("wrote", p)


if __name__ == "__main__":
    if "--replot" in sys.argv:
        with open(os.path.join(RESULTS, "convergence.json")) as f:
            d = json.load(f)
        plot(d["rows"], d.get("orekit_reference") or {})
    else:
        main()
