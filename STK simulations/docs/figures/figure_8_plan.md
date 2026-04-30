# Figure 8 — Area-to-Mass Ratio Sensitivity at the Gain Anchor (700 km vs 800 km)

**Paper reference**: `Sections/sensitivity.tex`, label `fig:amr_sensitivity_gain_anchor`. Source PNG: `Figures/fig8_w78.png`.

---

## Scientific objective

Show that **larger sails help**, but only up to a point at low altitude. SRP force scales with A while drag also scales with A — at 700 km the two compete, producing a finite optimum near A/m ≈ 14.4 m²/kg (sail side ~12 m). At 800 km the drag roll-over is pushed beyond the sampled range, so larger A/m always improves Δa.

This contrast separates the **drag-dominated** and **SRP-dominated** regimes — a key paper insight beyond the simple "bigger is better" intuition.

What the figure must show:

1. 700 km curve **non-monotonic**, with peak around A/m ≈ 14.4.
2. 800 km curve **monotonic**, climbing through the entire range.
3. 800 km values higher than 700 km at every A/m.

If 700 km is monotonic up through A/m=22.5, the drag plugin is undermodelling drag (probably the cos(θ) factor not applied). If 800 km is non-monotonic, the SRP plugin is undermodelling SRP at high A.

---

## Setup

Reference geometry: gain anchor (LTDN 12.266 h, pitch 24.8°, roll 0°).

A/m sweep: mass fixed at **10 kg**; sail side L ∈ {5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15} m → A = L² ∈ {25, 36, 49, 64, 81, 100, 121, 144, 169, 196, 225} m² → A/m ∈ {2.5, 3.6, 4.9, 6.4, 8.1, 10.0, 12.1, 14.4, 16.9, 19.6, 22.5} m²/kg.

Two altitudes:
- 700 km, i = 98.17°
- 800 km, i = 98.31°

Both plugins must read sail area from `PluginSettings` (see `plugin_design.md`). Mass also propagated to STK satellite mass property.

Each case: 14-day HPOP, full force model.

---

## Acceptance gate

| A/m [m²/kg] | 700 km Δa_max [km] | 800 km Δa_max [km] | Tolerance |
|---|---|---|---|
| 2.5 | ≈ 4.17 | ≈ 8.54 | ±15% |
| 10.0 | ≈ 14.96 | ≈ 33.94 | ±10% |
| 14.4 | ≈ 17.92 (peak) | TBD (>nominal) | ±15% |
| 22.5 | < peak (decline) | ≈ 71.61 | ±15% |

Qualitative:
- 700 km: non-monotonic, peak in [12.1, 16.9] window.
- 800 km: monotonic, values increasing across full range.

---

## Runner

`runners/run_fig8_amr_sensitivity.py`

- For each (altitude, sail_side_m):
  - Compute A = L², A/m = A / 10.
  - Build scenario with sail area passed to both plugins via `PluginSettings`.
  - STK satellite mass property set to 10 kg.
  - Propagate 14 d.
  - Compute Δa_max,14d.
  - Write row to `results/fig8/amr_sensitivity.csv` (`altitude_km, sail_side_m, area_m2, amr_m2_per_kg, delta_a_max_km`).

---

## Plot

`post/plot_fig8_amr.py`

- Two curves: 700 km, 800 km.
- X-axis: A/m [m²/kg], Y-axis: Δa_max,14d [km].
- Markers at each sample point.
- Annotate the 700 km peak.
- Save to `reproduced_figures/fig8_amr_sensitivity.png`.

Visual diff target: `Figures/fig8_w78.png`.
