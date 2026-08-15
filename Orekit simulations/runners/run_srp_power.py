"""
One-orbit SRP specific power and cumulative work -- the counterpart of the
manuscript's Fig. 4/5 reproduction.

The mechanism the paper proposes is that the umbra removes the negative-work arc
of an otherwise near-symmetric SRP power cycle, so the orbit-averaged SRP work
comes out positive. This runner draws that directly from Orekit: the eclipse-on
power profile, the no-eclipse reference obtained by setting the occulting radius
to zero, the shaded umbra interval, and the running work integral of each.

Usage: ./run.sh runners/run_srp_power.py
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
    REPRO_LTDN_H, REPRO_PITCH_DEG, INC_800,
)
from orekit_core.propagation import (  # noqa: E402
    OrekitCase, build_propagator, keplerian_period, T0,
)

FIGS = os.path.join(ROOT, "reproduced_figures")
RESULTS = os.path.join(ROOT, "results")
DT = 5.0


def one_orbit(disable_eclipse):
    case = OrekitCase(altitude_km=800.0, inc_deg=INC_800,
                      raan_deg=raan_for_ltdn(REPRO_LTDN_H),
                      pitch_deg=REPRO_PITCH_DEG,
                      disable_eclipse=disable_eclipse, dt=DT)
    prop, rec, st0, n = build_propagator(case, want_diagnostics=True)
    period = keplerian_period(case.sma_m)
    prop.propagate(T0, T0.shiftedBy(period))
    t = np.asarray(rec.t)
    p = np.asarray(rec.p_srp)
    lit = np.asarray(rec.lit) > 0.5
    work = np.concatenate([[0.0], np.cumsum(0.5 * (p[1:] + p[:-1]) * np.diff(t))])
    return t, p, lit, work, period


def main():
    t_on, p_on, lit_on, w_on, period = one_orbit(False)
    t_off, p_off, lit_off, w_off, _ = one_orbit(True)

    n_ecl = int(np.sum(~lit_on))
    frac = n_ecl / len(lit_on)
    # of the samples that fall inside the umbra, how many would have carried
    # negative SRP work had the sail stayed illuminated?
    sel = float(np.mean(p_off[~lit_on] < 0.0) * 100.0) if n_ecl else float("nan")

    print(f"gain case: 800 km, LTDN {REPRO_LTDN_H:g} h, pitch {REPRO_PITCH_DEG:g} deg")
    print(f"  orbit period          : {period/60:.2f} min ({len(t_on)} samples @ {DT:.0f} s)")
    print(f"  umbra fraction        : {frac*100:.1f} %")
    print(f"  eclipse sign-selectivity : {sel:.1f} % of eclipsed samples would be "
          "negative-work  (manuscript Fig. 4: 85.7 %)")
    print(f"  net per-orbit SRP work, eclipse ON  : {w_on[-1]:+8.2f} J/kg")
    print(f"  net per-orbit SRP work, eclipse OFF : {w_off[-1]:+8.2f} J/kg")
    print("  (manuscript Fig. 5: +799 J/kg on, -9.7 J/kg off)")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    tm = t_on / 60.0
    axes[0].plot(tm, p_on, lw=1.7, label="eclipse ON")
    axes[0].plot(t_off / 60.0, p_off, "--", lw=1.3, color="0.4", label="no-eclipse reference")
    axes[0].axhline(0, color="k", lw=0.6)
    inside, labelled = False, False
    for i, dark in enumerate(~lit_on):
        if dark and not inside:
            start = tm[i]; inside = True
        if (not dark or i == len(lit_on) - 1) and inside:
            axes[0].axvspan(start, tm[i], color="0.85", zorder=0,
                            label=None if labelled else "umbra")
            labelled, inside = True, False
    axes[0].set_xlabel("time [min]")
    axes[0].set_ylabel(r"SRP specific power $\mathbf{a}_{\rm SRP}\!\cdot\!\mathbf{v}$ [W/kg]")
    axes[0].set_title("One-orbit SRP power (shaded = umbra)", fontsize=9)
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    axes[1].plot(tm, w_on, lw=1.7, label="eclipse ON")
    axes[1].plot(t_off / 60.0, w_off, "--", lw=1.3, color="0.4", label="no-eclipse reference")
    axes[1].axhline(0, color="k", lw=0.6)
    axes[1].set_xlabel("time [min]")
    axes[1].set_ylabel("cumulative SRP work [J/kg]")
    axes[1].set_title("Cumulative one-orbit SRP work", fontsize=9)
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.suptitle("Orekit: the umbra removes the negative-work arc", fontsize=10)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    p = os.path.join(FIGS, "orekit_srp_power.png")
    fig.savefig(p, dpi=140)
    plt.close(fig)
    print(f"\nwrote {p}")

    os.makedirs(RESULTS, exist_ok=True)
    q = os.path.join(RESULTS, "srp_power.json")
    with open(q, "w") as f:
        json.dump(dict(period_s=float(period), dt_s=DT,
                       umbra_fraction=float(frac),
                       eclipse_sign_selectivity_pct=sel,
                       work_eclipse_on_J_per_kg=float(w_on[-1]),
                       work_eclipse_off_J_per_kg=float(w_off[-1]),
                       manuscript_fig5_on=799.0,
                       manuscript_fig5_off=-9.7,
                       manuscript_fig4_selectivity_pct=85.7), f, indent=2)
    print(f"wrote {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
