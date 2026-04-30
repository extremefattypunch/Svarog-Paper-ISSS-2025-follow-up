# Figure 7 — Atmospheric Density Sensitivity at the Gain Anchor (700 km vs 800 km)

**Paper reference**: `Sections/sensitivity.tex`, label `fig:density_sensitivity_gain_anchor`. Source PNG: `Figures/fig7_w78.png`.

---

## Scientific objective

Demonstrate that **drag is the dominant bounding mechanism** for the gain regime — the regime exists only while the eclipse-biased SRP surplus exceeds drag losses. Higher altitude pushes the drag-limited boundary outward; the regime is robust at 800 km even at 4× density, but collapses at 700 km past 2× density.

What the figure must show:

1. Both altitudes peak at lower density factors (gain helped by less drag).
2. 700 km curve falls to zero at ~2× density.
3. 800 km curve remains positive across the entire 0.25–4× range.
4. 800 km absolute values higher than 700 km at every density factor.

If the 700 km curve at 1× already shows zero (or much less than 14.96 km), the drag plugin is over-applying — likely missing the cos(θ) projected-area factor or using a wrong scale height in the US-1976 table.

---

## Setup

Reference geometry: gain anchor (LTDN 12.266 h, pitch 24.8°, roll 0°).

Density-scaling factors: **{0.25, 0.5, 1.0, 2.0, 4.0}** — five points per altitude.

Two altitudes:
- 700 km, i = 98.17°
- 800 km, i = 98.31°

The drag plugin reads `density_scaling_factor` from `PluginSettings` (see `plugin_design.md` §3.3). Each case: 14-day HPOP, full force model.

---

## Acceptance gate

| Density × | 700 km Δa_max [km] | 800 km Δa_max [km] | Tolerance |
|---|---|---|---|
| 0.25 | ≈ 34.89 | TBD (>800 km @ 1×) | ±15% |
| 0.5 | ≈ 28.59 | ≈ 26.49 | ±15% |
| 1.0 | ≈ 14.96 | ≈ 33.94 | ±10% |
| 2.0 | ≈ 0 | TBD (>10) | qualitative |
| 4.0 | ≈ 0 | ≈ 10.25 | ±20% |

Note: 800 km @ 0.25× is not given in the paper text we extracted; record observed value.

---

## Runner

`runners/run_fig7_density_sensitivity.py`

- For each (altitude, density_factor):
  - Build scenario with `density_scaling_factor` set on the drag plugin.
  - Propagate 14 d.
  - Compute Δa_max,14d.
  - Write row to `results/fig7/density_sensitivity.csv` (`altitude_km, density_factor, delta_a_max_km`).

---

## Plot

`post/plot_fig7_density.py`

- Two curves: 700 km, 800 km.
- X-axis: density factor (log scale), Y-axis: Δa_max,14d [km].
- Markers at the five sweep points.
- Save to `reproduced_figures/fig7_density_sensitivity.png`.

Visual diff target: `Figures/fig7_w78.png`.

---

## Implementation note

If `PluginSettings.SetProperty("density_scaling_factor", ...)` proves not to propagate dynamically (ie STK caches the plugin between cases), fall back to **template-generating a per-factor plugin file** with the constant baked in, then load that file via `Filename`. This adds bookkeeping but is robust.
