"""
Eclipse causality with Orekit -- the counterpart of the manuscript's Fig. 3
reproduction.

Toggling the umbra on and off at a representative gain geometry should flip the
sign of the short-horizon semi-major-axis response, demonstrating that it is
eclipse *timing*, not SRP magnitude, that controls the sign of the
orbit-averaged SRP work. The eclipse-off branch is realised by giving Orekit's
`CylindricallyShadowedLightFluxModel` an occulting radius of zero, so the sail is
permanently illuminated while every other model element is untouched.

Two geometries, following the existing STK-study figure: the reproduced 800 km
gain case (LTDN 14 h, pitch 34 deg) and the paper's 700 km reduced-model anchor
(LTDN 12.266 h, pitch 24.8 deg).

Usage: ./run.sh runners/run_eclipse_causality.py [days]
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

from orekit_core.constants import (  # noqa: E402
    ANCHOR_RAAN_DEG, ANCHOR_PITCH_DEG, REPRO_LTDN_H, REPRO_PITCH_DEG,
    INC_700, INC_800,
)
from orekit_core.attitude import raan_for_ltdn  # noqa: E402
from orekit_core.propagation import OrekitCase, propagate  # noqa: E402

DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
FIGS = os.path.join(ROOT, "reproduced_figures")
RESULTS = os.path.join(ROOT, "results")

GAIN = dict(altitude_km=800.0, inc_deg=INC_800,
            raan_deg=raan_for_ltdn(REPRO_LTDN_H), pitch_deg=REPRO_PITCH_DEG,
            label=f"gain case (800 km, LTDN {REPRO_LTDN_H:g} h, "
                  f"pitch {REPRO_PITCH_DEG:g}$^\\circ$)")
ANCHOR = dict(altitude_km=700.0, inc_deg=INC_700, raan_deg=ANCHOR_RAAN_DEG,
              pitch_deg=ANCHOR_PITCH_DEG,
              label="paper anchor (700 km, LTDN 12.27 h, pitch 24.8$^\\circ$)")


def main():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    rows = []
    for ax, cfg in zip(axes, (GAIN, ANCHOR)):
        for off, style, lab in ((False, "-", "eclipse ON"), (True, "--", "eclipse OFF")):
            case = OrekitCase(altitude_km=cfg["altitude_km"], inc_deg=cfg["inc_deg"],
                              raan_deg=cfg["raan_deg"], pitch_deg=cfg["pitch_deg"],
                              disable_eclipse=off, integrator="dp853", dt=30.0)
            r = propagate(case, DAYS)
            t = r["node_t"] / 86400.0
            da = r["node_a"] - r["node_a"][0]
            ax.plot(t, da, style, lw=1.7, label=lab)
            rows.append(dict(altitude_km=cfg["altitude_km"],
                             pitch_deg=cfg["pitch_deg"], eclipse_off=off,
                             da_max_km=r["da_max"], da_final_km=r["da_final"],
                             t_at_max_d=r["t_at_max_d"], days=DAYS))
            print(f"[{cfg['altitude_km']:.0f} km, pitch {cfg['pitch_deg']:g} deg] "
                  f"eclipse {'OFF' if off else 'ON ':3s}: "
                  f"Delta a_max = {r['da_max']:+8.3f} km @ day {r['t_at_max_d']:5.2f}, "
                  f"Delta a({DAYS:.0f} d) = {r['da_final']:+8.3f} km")
        ax.axhline(0, color="k", lw=0.5)
        ax.set_xlabel("time [days]")
        ax.set_ylabel(r"$\Delta a$ (mean) [km]")
        ax.set_title(cfg["label"], fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("Orekit: eclipse causally enables the gain "
                 r"(sign of $\Delta a$ flips)", fontsize=10)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    p = os.path.join(FIGS, "orekit_eclipse_causality.png")
    fig.savefig(p, dpi=140)
    plt.close(fig)
    print(f"\nwrote {p}")

    os.makedirs(RESULTS, exist_ok=True)
    q = os.path.join(RESULTS, "eclipse_causality.json")
    with open(q, "w") as f:
        json.dump(dict(days=DAYS, rows=rows), f, indent=2)
    print(f"wrote {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
