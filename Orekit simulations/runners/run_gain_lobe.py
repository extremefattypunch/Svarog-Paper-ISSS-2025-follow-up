"""
LTDN x pitch map of the 14-day Delta a_max -- the counterpart of the
manuscript's Fig. 2 reproduction, computed with Orekit.

Grid matches the existing STK-study sweep (LTDN 0-24 h, pitch 0-90 deg) so the
two maps can be laid side by side. The integrator is adaptive DP853 with
Orekit's eclipse event detection, because a fixed step biases the answer for a
discontinuous, eclipse-gated force (see validation/v7_eclipse_discontinuity.py).

Usage: ./run.sh runners/run_gain_lobe.py [alt_km] [n_ltdn] [n_pitch] [days] [workers]
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orekit_core.orekit_setup import boot, ROOT  # noqa: E402

boot()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from orekit_core.attitude import raan_for_ltdn  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    ANCHOR_LTDN_H, ANCHOR_PITCH_DEG, inclination_for,
)
from orekit_core.sweep import run_sweep  # noqa: E402

ALT = float(sys.argv[1]) if len(sys.argv) > 1 else 800.0
NL = int(sys.argv[2]) if len(sys.argv) > 2 else 25
NP = int(sys.argv[3]) if len(sys.argv) > 3 else 25
DAYS = float(sys.argv[4]) if len(sys.argv) > 4 else 14.0
WORKERS = int(sys.argv[5]) if len(sys.argv) > 5 else max(1, (os.cpu_count() or 4) - 2)

LTDNS = np.linspace(0.0, 24.0, NL, endpoint=False)   # 24 h == 0 h: not repeated
PITCHES = np.linspace(-90.0, 90.0, NP)

FIGS = os.path.join(ROOT, "reproduced_figures")
RESULTS = os.path.join(ROOT, "results")


def main():
    inc = inclination_for(ALT)
    cases = []
    for i, ltdn in enumerate(LTDNS):
        for j, pitch in enumerate(PITCHES):
            cases.append(((i, j), dict(
                altitude_km=ALT, inc_deg=inc, raan_deg=raan_for_ltdn(float(ltdn)),
                pitch_deg=float(pitch), integrator="dp853", dt=30.0)))

    print(f"Orekit gain-lobe sweep at {ALT:.0f} km: {NL} x {NP} = {len(cases)} cases, "
          f"{DAYS:.0f} days, {WORKERS} workers")
    t0 = time.time()
    res = run_sweep(cases, DAYS, workers=WORKERS, chunksize=2)
    print(f"  finished in {(time.time()-t0)/60:.1f} min")

    Z = np.full((NP, NL), np.nan)
    for (i, j), r in res.items():
        Z[j, i] = r["da_max"]

    n_bad = int(np.sum(~np.isfinite(Z)))
    finite = np.isfinite(Z)
    npos = int(np.sum(Z[finite] > 0.05))
    peak = np.unravel_index(np.nanargmax(Z), Z.shape)
    print(f"  peak Delta a_max = {np.nanmax(Z):.3f} km at LTDN = {LTDNS[peak[1]]:.2f} h, "
          f"pitch = {PITCHES[peak[0]]:.1f} deg")
    print(f"  positive cells (> 0.05 km): {npos}/{finite.sum()} "
          f"({100*npos/max(1,finite.sum()):.1f} %)   failed cells: {n_bad}")

    os.makedirs(RESULTS, exist_ok=True)
    np.savez(os.path.join(RESULTS, f"gain_lobe_{int(ALT)}.npz"),
             Z=Z, ltdn=LTDNS, pitch=PITCHES, alt=ALT, days=DAYS)

    lim = max(1.0, float(np.nanmax(np.abs(Z))))
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.pcolormesh(LTDNS, PITCHES, Z, shading="auto", cmap="RdBu_r",
                       vmin=-lim, vmax=lim)
    ax.set_xlabel("LTAN [h]")
    ax.set_ylabel("sail pitch [deg]")
    ax.set_title(rf"Orekit: 14-day $\Delta a_{{\max}}$ [km] at {int(ALT)} km", fontsize=10)
    ax.plot(ANCHOR_LTDN_H, ANCHOR_PITCH_DEG, "k*", ms=13,
            label="reduced-model anchor (12.27 h, 24.8$^\\circ$)")
    ax.legend(loc="upper right", fontsize=8)
    fig.colorbar(im, ax=ax, label=r"$\Delta a_{\max}$ [km]")
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    out = os.path.join(FIGS, f"orekit_gain_lobe_{int(ALT)}km.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
