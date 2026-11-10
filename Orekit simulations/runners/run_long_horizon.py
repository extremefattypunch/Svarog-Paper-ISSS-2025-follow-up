"""
Long-horizon element evolution -- the counterpart of the manuscript's Fig. 9
reproduction, computed with Orekit.

The claimed signature is a transient, self-limiting one: mean semi-major axis
rises to a peak and then falls back below its initial value, driven by apogee
pumping, eccentricity growth and perigee erosion. This runner propagates the
reproduced 800 km gain case and the paper's 700 km anchor for 75 days and plots
mean a, e, and apogee/perigee altitude.

Series are truncated at reentry (perigee altitude below 120 km), where the
propagation stops being meaningful.

Usage: ./run.sh runners/run_long_horizon.py [days]
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

from orekit_core.attitude import raan_for_ltdn  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    ANCHOR_RAAN_DEG, ANCHOR_PITCH_DEG, REPRO_LTDN_H, REPRO_PITCH_DEG,
    INC_700, INC_800,
)
from orekit_core.propagation import OrekitCase, propagate  # noqa: E402

DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 75.0
HP_MIN_KM = 120.0
FIGS = os.path.join(ROOT, "reproduced_figures")
RESULTS = os.path.join(ROOT, "results")

CASES = [
    dict(label=f"gain case (800 km, LTDN {REPRO_LTDN_H:g} h, "
               f"pitch {REPRO_PITCH_DEG:g}$^\\circ$)",
         colour="tab:blue",
         kw=dict(altitude_km=800.0, inc_deg=INC_800,
                 raan_deg=raan_for_ltdn(REPRO_LTDN_H), pitch_deg=REPRO_PITCH_DEG)),
    dict(label="paper anchor (700 km, LTDN 12.27 h, pitch 24.8$^\\circ$)",
         colour="tab:red",
         kw=dict(altitude_km=700.0, inc_deg=INC_700, raan_deg=ANCHOR_RAAN_DEG,
                 pitch_deg=ANCHOR_PITCH_DEG)),
]


def clip_reentry(r):
    hp = r["node_hp"]
    below = np.nonzero(hp < HP_MIN_KM)[0]
    end = int(below[0]) if len(below) else len(hp)
    return slice(0, max(1, end))


def main():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    rows = []
    for cfg in CASES:
        case = OrekitCase(integrator="dp853", dt=30.0, **cfg["kw"])
        r = propagate(case, DAYS)
        sl = clip_reentry(r)
        t = r["node_t"][sl] / 86400.0
        a = r["node_a"][sl]
        e = r["node_e"][sl]
        ha = r["node_ha"][sl]
        hp = r["node_hp"][sl]
        reentry_day = float(r["node_t"][sl.stop - 1] / 86400.0) if sl.stop < len(r["node_hp"]) else None

        axes[0].plot(t, a - a[0], lw=1.6, color=cfg["colour"], label=cfg["label"])
        axes[1].plot(t, e, lw=1.6, color=cfg["colour"], label=cfg["label"])
        axes[2].plot(t, ha, lw=1.6, color=cfg["colour"], label=f"apogee, {cfg['label']}")
        axes[2].plot(t, hp, "--", lw=1.3, color=cfg["colour"],
                     label=f"perigee, {cfg['label']}")

        peak_i = int(np.argmax(a))
        rows.append(dict(label=cfg["label"].replace("$^\\circ$", " deg"),
                         altitude_km=cfg["kw"]["altitude_km"],
                         pitch_deg=cfg["kw"]["pitch_deg"],
                         da_peak_km=float(a[peak_i] - a[0]),
                         t_peak_days=float(t[peak_i]),
                         da_final_km=float(a[-1] - a[0]),
                         e_final=float(e[-1]),
                         apogee_final_km=float(ha[-1]),
                         perigee_final_km=float(hp[-1]),
                         reentry_day=reentry_day,
                         span_days=float(t[-1])))
        print(f"[{cfg['kw']['altitude_km']:.0f} km, pitch {cfg['kw']['pitch_deg']:g} deg] "
              f"Delta a peak = {a[peak_i]-a[0]:+7.3f} km @ day {t[peak_i]:5.2f}; "
              f"Delta a at day {t[-1]:.1f} = {a[-1]-a[0]:+8.3f} km; "
              f"e: {e[0]:.5f} -> {e[-1]:.5f}; "
              f"apogee {ha[0]:.1f} -> {ha[-1]:.1f} km; "
              f"perigee {hp[0]:.1f} -> {hp[-1]:.1f} km"
              + (f"  [reentry ~day {reentry_day:.1f}]" if reentry_day else ""))

    axes[0].axhline(0, color="k", lw=0.5)
    axes[0].set_xlabel("time [days]"); axes[0].set_ylabel(r"$\Delta a$ (mean) [km]")
    axes[0].set_title("mean semi-major axis", fontsize=9)
    axes[1].set_xlabel("time [days]"); axes[1].set_ylabel("eccentricity")
    axes[1].set_title("eccentricity", fontsize=9)
    axes[2].set_xlabel("time [days]"); axes[2].set_ylabel("altitude [km]")
    axes[2].set_title("apogee (solid) and perigee (dashed)", fontsize=9)
    for ax in axes:
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    fig.suptitle(f"Orekit: {DAYS:.0f}-day element evolution", fontsize=10)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    p = os.path.join(FIGS, "orekit_transient.png")
    fig.savefig(p, dpi=140)
    plt.close(fig)
    print(f"\nwrote {p}")

    os.makedirs(RESULTS, exist_ok=True)
    q = os.path.join(RESULTS, "long_horizon.json")
    with open(q, "w") as f:
        json.dump(dict(days=DAYS, hp_min_km=HP_MIN_KM, rows=rows), f, indent=2)
    print(f"wrote {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
