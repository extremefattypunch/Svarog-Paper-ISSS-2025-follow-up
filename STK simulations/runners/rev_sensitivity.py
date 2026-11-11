"""
Local sensitivity sweeps about the gain-anchor geometry (manuscript Section 8):
static roll offset, atmospheric-density multiplier and area-to-mass ratio, each
at 800 km (production) and 700 km (contrast).  Metric: Delta a_max,14d.

The anchor LTAN/pitch are read from results/revision/cases.json (written by
rev_cases.py); falls back to LTAN 14 h / pitch 34 deg.
"""
from __future__ import annotations
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from runners.rev_common import save_json, load_json, fig_path, mpl, INC, DT_PROD, N_WORKERS
from core.offline_propagator import SailCase, propagate

DAYS = 14.0
ROLLS = list(np.linspace(-45.0, 45.0, 19))
DENS = [0.25, 0.5, 1.0, 2.0, 4.0]
AMRS = [2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5]


def anchor():
    try:
        g = load_json("cases.json")["cases"]["gain"]
        return float(g["ltan_h"]), float(g["pitch_deg"])
    except Exception:
        return 14.0, 34.0


def one(args):
    kind, alt, x, ltan, pitch = args
    kw = dict(altitude_km=alt, inc_deg=INC[alt], ltan_h=ltan, pitch_deg=pitch, dt=DT_PROD)
    if kind == "roll": kw["roll_deg"] = x
    elif kind == "dens": kw["cd_scale"] = x
    elif kind == "amr": kw["area_m2"] = x * 10.0      # mass fixed at 10 kg
    r = propagate(SailCase(**kw), DAYS)
    return kind, alt, x, r["da_max"], r["da_at_14d"]


def main():
    ltan, pitch = anchor()
    jobs = ([("roll", a, x, ltan, pitch) for a in (700.0, 800.0) for x in ROLLS]
            + [("dens", a, x, ltan, pitch) for a in (700.0, 800.0) for x in DENS]
            + [("amr", a, x, ltan, pitch) for a in (700.0, 800.0) for x in AMRS])
    res = {}
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        for kind, alt, x, dmax, d14 in ex.map(one, jobs):
            res.setdefault(kind, {}).setdefault(str(int(alt)), []).append(dict(x=x, da_max_km=dmax, da_at_14d_km=d14))
    for kind in res:
        for alt in res[kind]:
            res[kind][alt].sort(key=lambda d: d["x"])
    out = dict(days=DAYS, dt_s=DT_PROD, anchor=dict(ltan_h=ltan, pitch_deg=pitch), sweeps=res,
               grids=dict(roll_deg=ROLLS, density_factor=DENS, area_over_mass=AMRS))
    save_json("sensitivity.json", out)

    plt = mpl()
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
    spec = (("roll", "static roll offset about the Sun line [deg]", False),
            ("dens", "atmospheric-density multiplier", True),
            ("amr", "area-to-mass ratio $A/m$ [m$^2$ kg$^{-1}$]", False))
    for ax, (kind, xl, logx) in zip(axes, spec):
        for alt, col in (("800", "C0"), ("700", "C3")):
            pts = res[kind][alt]
            ax.plot([p["x"] for p in pts], [p["da_max_km"] for p in pts], "o-", color=col, ms=3.5, lw=1.3, label=f"{alt} km")
        if logx: ax.set_xscale("log")
        ax.axhline(0, color="k", lw=0.5); ax.set_xlabel(xl); ax.legend()
    axes[0].set_ylabel("$\\Delta a_{\\max,14\\mathrm{d}}$ [km]")
    fig.suptitle(f"Sensitivity about the gain anchor (LTAN {ltan:.1f} h, pitch {pitch:+.0f}°)", fontsize=9.5)
    fig.tight_layout(); fig.savefig(fig_path("r_sensitivity.png")); plt.close(fig)
    for kind in res:
        for alt in res[kind]:
            print(kind, alt, [(round(p["x"], 2), round(p["da_max_km"], 3)) for p in res[kind][alt]])


if __name__ == "__main__":
    main()
