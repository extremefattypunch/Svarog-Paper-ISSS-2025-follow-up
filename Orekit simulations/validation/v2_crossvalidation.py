"""
V2 -- propagated cross-validation, the direct analogue of the STK comparison.

Same three configurations the manuscript uses for STK Astrogator, chosen so the
result cannot depend on the sail orientation:

  (a) two-body + J2, no SRP, no drag                     700 km and 800 km
  (b) two-body + J2 + spherical US-1976 drag, no SRP     700 km and 800 km
      (A/m = 10 m^2/kg, C_D = 2.2)

For each we propagate 14 days in Orekit and in the paper's open-source
propagator and compare the mean semi-major-axis history. Two mean-element
definitions are reported, because the manuscript shows the choice matters:

  * node-sampled  -- osculating a at ascending-node crossings (what the
                     open-source propagator uses)
  * orbit-averaged -- centred moving average of osculating a over one nodal
                     period (the energy-based mean used for STK, because STK's
                     Brouwer-Lyddane mean is a conservative-theory construct
                     and misbehaves under drag)

STK's published endpoints are carried through for the three-way table. They are
quoted from the existing STK study in this repository, not re-run here: STK 13
with an Astrogator licence is Windows-only, so those numbers are reported as
previously obtained rather than regenerated.

Writes reproduced_figures/orekit_validation.png and results/v2_crossvalidation.json.
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

from orekit_core.constants import ANCHOR_PITCH_DEG, REPRO_PITCH_DEG  # noqa: E402
from orekit_core.propagation import (  # noqa: E402
    OrekitCase, propagate, orbit_average, keplerian_period, osculating_elements,
    node_sample,
)
from orekit_core.attitude import raan_for_ltdn  # noqa: E402

# Paper's propagator, imported verbatim.
from core.offline_propagator import SailCase, propagate as propagate_paper  # noqa: E402

DAYS = 14.0
DT = 30.0
LTDN = 14.0
PITCH = REPRO_PITCH_DEG
RAAN = raan_for_ltdn(LTDN)

# Endpoints previously obtained with STK 13 / Astrogator (see
# Sections/validation.tex and "STK simulations"/docs/RESULTS.md). Not re-run here.
STK_REPORTED = {
    ("J2-only", 700.0): 0.0,     # "agree to better than 0.05 km over 14 days"
    ("J2-only", 800.0): 0.0,
    ("J2+drag", 700.0): -7.0,    # km, 14-day mean SMA decay
    ("J2+drag", 800.0): None,    # not separately quoted in the manuscript
}
STK_J2_AGREEMENT_KM = 0.05

RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "reproduced_figures")


def orekit_run(alt, use_drag):
    case = OrekitCase(altitude_km=alt, raan_deg=RAAN, pitch_deg=PITCH,
                      use_srp=False, use_drag=use_drag, drag_mode="spherical",
                      dt=DT)
    r = propagate(case, DAYS)
    period = keplerian_period(case.sma_m)
    t_avg, a_avg = orbit_average(r["t"], r["osc_a"], period)
    return dict(node_t=r["node_t"], node_a=r["node_a"],
                avg_t=t_avg, avg_a=a_avg, period=period)


def paper_run(alt, use_drag):
    inc = 98.31 if alt >= 750 else 98.17
    c = SailCase(altitude_km=alt, inc_deg=inc, raan_deg=RAAN, pitch_deg=PITCH,
                 ecc=1e-4, use_srp=False, drag_mode="spherical", dt=DT)
    if not use_drag:
        c.cd = 0.0
    r = propagate_paper(c, DAYS)
    return dict(node_t=r["node_t"], node_a=r["node_a"])


def compare(alt, use_drag, label):
    ok = orekit_run(alt, use_drag)
    pp = paper_run(alt, use_drag)

    da_ok = ok["node_a"] - ok["node_a"][0]
    da_pp = pp["node_a"] - pp["node_a"][0]
    # interpolate Orekit onto the paper's node times
    da_ok_i = np.interp(pp["node_t"], ok["node_t"], da_ok)
    diff = da_pp - da_ok_i

    da_avg = ok["avg_a"] - ok["avg_a"][0]

    row = dict(
        config=label, altitude_km=alt,
        orekit_da14_node_km=float(da_ok[-1]),
        paper_da14_node_km=float(da_pp[-1]),
        orekit_da14_orbitavg_km=float(da_avg[-1]),
        max_abs_diff_km=float(np.max(np.abs(diff))),
        rms_diff_km=float(np.sqrt(np.mean(diff ** 2))),
        orekit_a0_km=float(ok["node_a"][0]),
        paper_a0_km=float(pp["node_a"][0]),
        n_orbits=int(len(pp["node_a"])),
        stk_da14_km=STK_REPORTED.get((label, alt)),
    )
    print(f"[{label} {alt:.0f} km]  Delta a(14 d):  Orekit {da_ok[-1]:+9.3f} km   "
          f"open-source {da_pp[-1]:+9.3f} km   "
          f"max|diff| {row['max_abs_diff_km']:.4f} km   rms {row['rms_diff_km']:.4f} km")
    return row, ok, pp, diff


def main():
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(FIGS, exist_ok=True)

    rows, series = [], {}
    for alt in (700.0, 800.0):
        r, ok, pp, d = compare(alt, False, "J2-only")
        rows.append(r); series[("J2-only", alt)] = (ok, pp, d)
    for alt in (700.0, 800.0):
        r, ok, pp, d = compare(alt, True, "J2+drag")
        rows.append(r); series[("J2+drag", alt)] = (ok, pp, d)

    # ---- figure: mirrors Figures/stk_validation.png -------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    colours = {700.0: "tab:blue", 800.0: "tab:red"}
    for alt in (700.0, 800.0):
        ok, pp, d = series[("J2+drag", alt)]
        axes[0].plot(ok["node_t"] / 86400, ok["node_a"] - ok["node_a"][0],
                     lw=1.8, color=colours[alt], label=f"Orekit {int(alt)} km")
        axes[0].plot(pp["node_t"] / 86400, pp["node_a"] - pp["node_a"][0], "--",
                     lw=1.4, color=colours[alt], label=f"open-source {int(alt)} km")
        axes[1].plot(pp["node_t"] / 86400, d, lw=1.4, color=colours[alt],
                     label=f"{int(alt)} km")
    for alt in (700.0, 800.0):
        ok, pp, d = series[("J2-only", alt)]
        axes[1].plot(pp["node_t"] / 86400, d, ":", lw=1.2, color=colours[alt],
                     label=f"{int(alt)} km, $J_2$ only")

    axes[0].set_xlabel("time [days]")
    axes[0].set_ylabel(r"$\Delta a$ (mean) [km]")
    axes[0].set_title(r"$J_2$ + spherical US-1976 drag: open-source vs Orekit", fontsize=9)
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    axes[1].axhline(0, color="k", lw=0.5)
    axes[1].set_xlabel("time [days]")
    axes[1].set_ylabel(r"$\Delta a$ difference (open-source $-$ Orekit) [km]")
    axes[1].set_title("residual", fontsize=9)
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.suptitle("Cross-validation of the open-source propagator against Orekit", fontsize=10)
    fig.tight_layout()
    out = os.path.join(FIGS, "orekit_validation.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"\nwrote {out}")

    report = dict(days=DAYS, dt_s=DT, ltdn_h=LTDN, pitch_deg=PITCH, raan_deg=RAAN,
                  stk_j2_agreement_km=STK_J2_AGREEMENT_KM, rows=rows)
    p = os.path.join(RESULTS, "v2_crossvalidation.json")
    with open(p, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {p}")

    j2_ok = all(r["max_abs_diff_km"] < STK_J2_AGREEMENT_KM
                for r in rows if r["config"] == "J2-only")
    print(f"\nJ2-only agreement better than STK's {STK_J2_AGREEMENT_KM} km bar: {j2_ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
