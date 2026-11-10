"""
Figure 9 — 75-day orbital element evolution.

Reads results/fig9/elements_75d.csv (produced by runners/run_fig9_long_horizon.py)
and produces a 4-panel figure of a, h_a, h_p, e vs time. Matches the layout
of paper Figures/fig9_rect.png.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.work_diagnostics import read_classical_csv, with_apogee_perigee_time

# Paper reference values (from breakdown.tex)
PAPER_REF = {
    "a0_km": 7078.137,
    "a_peak_km": 7098.211,
    "t_a_peak_d": 26.50,
    "a_final_km": 7064.717,
    "ha_peak_km": 864.548,
    "t_ha_peak_d": 39.50,
    "hp_min_km": 546.370,
    "t_hp_min_d": 42.17,
    "e_peak": 2.176e-2,
    "t_e_peak_d": 40.72,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path,
                   default=_PROJECT_ROOT / "results" / "fig9" / "elements_75d.csv")
    p.add_argument("--out", type=Path,
                   default=_PROJECT_ROOT / "reproduced_figures" / "fig9_elements_75d.png")
    args = p.parse_args()

    rows = read_classical_csv(args.csv)
    if not rows:
        raise SystemExit(f"no rows in {args.csv}")
    t0 = rows[0]["t_iso"]
    rows = with_apogee_perigee_time(rows, t0)
    t_d = [r["t_sec"] / 86400.0 for r in rows]
    a   = [r["sma_km"] for r in rows]
    e   = [r["ecc"] for r in rows]
    ha  = [r["ha_km"] for r in rows]
    hp  = [r["hp_km"] for r in rows]

    fig, axs = plt.subplots(4, 1, figsize=(8, 11), sharex=True)

    axs[0].plot(t_d, a, lw=1.2)
    axs[0].axhline(PAPER_REF["a0_km"], ls="--", c="grey", lw=0.8)
    axs[0].axhline(PAPER_REF["a_peak_km"], ls=":", c="C1", lw=0.8,
                   label=f"paper a_peak={PAPER_REF['a_peak_km']:.3f}")
    axs[0].set_ylabel("a [km]")
    axs[0].set_title("Figure 9 — 75-day evolution, gain anchor (LTDN 12.266 h, pitch 24.8°)")
    axs[0].legend(loc="best", fontsize=8)

    axs[1].plot(t_d, ha, lw=1.2, c="C2")
    axs[1].axhline(PAPER_REF["ha_peak_km"], ls=":", c="C1", lw=0.8,
                   label=f"paper ha_peak={PAPER_REF['ha_peak_km']:.3f}")
    axs[1].set_ylabel("h_a [km]")
    axs[1].legend(loc="best", fontsize=8)

    axs[2].plot(t_d, hp, lw=1.2, c="C3")
    axs[2].axhline(PAPER_REF["hp_min_km"], ls=":", c="C1", lw=0.8,
                   label=f"paper hp_min={PAPER_REF['hp_min_km']:.3f}")
    axs[2].set_ylabel("h_p [km]")
    axs[2].legend(loc="best", fontsize=8)

    axs[3].plot(t_d, e, lw=1.2, c="C4")
    axs[3].axhline(PAPER_REF["e_peak"], ls=":", c="C1", lw=0.8,
                   label=f"paper e_peak={PAPER_REF['e_peak']:.3e}")
    axs[3].set_ylabel("e")
    axs[3].set_xlabel("time [days]")
    axs[3].legend(loc="best", fontsize=8)

    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
