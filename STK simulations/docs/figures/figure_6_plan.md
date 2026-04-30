# Figure 6 — Roll Sensitivity at the Gain Anchor (700 km vs 800 km)

**Paper reference**: `Sections/sensitivity.tex`, label `fig:roll_sensitivity_gain_anchor`. Source PNG: `Figures/fig6_w78.png`.

---

## Scientific objective

Show that the gain regime tolerates a **finite neighbourhood** of attitude misalignments: the response peaks at zero roll and falls off symmetrically. Crucially, the envelope is **broader at 800 km** than at 700 km — at 800 km, a ±45° roll still preserves ~50% of the nominal response; at 700 km the same offset retains only a small fraction. This altitude dependence is itself an interesting finding of the paper.

What the figure must show:

1. Single peak at zero roll for both altitudes.
2. Symmetric (or near-symmetric) fall-off about zero.
3. 800 km curve substantially wider and higher than 700 km.

If the curves are flat or peaked off-zero, the inertial-attitude construction in `core/attitude.py` is wrong (likely the rotation axis order or sign).

---

## Setup

Reference geometry (gain anchor):
- LTDN = 12.266176 h
- Pitch = 24.8°
- RAAN = 285.5°
- A/m = 10 m²/kg
- ε₀ = 1×10⁻⁴

Roll sweep: 11–15 points in [−45°, +45°], including 0°. Suggested grid: {−45, −30, −20, −10, −5, 0, +5, +10, +20, +30, +45}°.

Two altitudes:
- 700 km, i = 98.17°
- 800 km, i = 98.31°

Each case: 14-day HPOP, full force model (SRP plugin + drag plugin + J₂), record Δa_max,14d.

---

## Acceptance gate

| Quantity | 700 km | 800 km | Tolerance |
|---|---|---|---|
| Δa_max @ roll=0° | ≈ 14.96 km | ≈ 33.94 km | ±10% |
| Peak at roll=0° | ✓ | ✓ | yes/no |
| 800 km envelope wider | — | — | qualitative |

If the 700 km nominal point disagrees with the heatmap-peak number from Fig. 2 (paper reports +20.07 km from heatmap vs 14.96 km in sensitivity, see `transient.tex` vs `sensitivity.tex`), document the discrepancy. The paper itself shows this difference; treat the lower (sensitivity) number as authoritative for this figure.

---

## Runner

`runners/run_fig6_roll_sensitivity.py`

- For each (altitude, roll):
  - Build gain-anchor scenario with the specified roll offset (passed to `core/attitude.inertial_sail_normal_from_pitch_roll`).
  - Propagate 14 d.
  - Compute Δa_max,14d.
  - Write row to `results/fig6/roll_sensitivity.csv` (`altitude_km, roll_deg, delta_a_max_km`).

---

## Plot

`post/plot_fig6_roll.py`

- Two curves on same axes: 700 km (solid), 800 km (dashed/different color).
- X-axis: roll offset [°], Y-axis: Δa_max,14d [km].
- Markers at each sample point.
- Save to `reproduced_figures/fig6_roll_sensitivity.png`.

Visual diff target: `Figures/fig6_w78.png`.
