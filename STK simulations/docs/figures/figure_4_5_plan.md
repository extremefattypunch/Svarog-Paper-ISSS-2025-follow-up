# Figures 4 & 5 — Per-Orbit SRP Power and Cumulative Work, Gain / Neutral / Decay Cases

**Paper references**: `Sections/transient.tex`. Figure 4 label `srp_vs_anomaly`, Figure 5 label `cum_SRP`. Source PNGs: `Figures/Fig4_Fullrect.png`, `Fig5_fullrect.png`. They share data so they live in the same plan.

---

## Scientific objective

These two figures are the **mechanism evidence** at the single-orbit level. They show *why* eclipse can produce gain in one geometry and decay in another:

- For an inertially fixed sail the SRP power `P(t) = a_SRP · v` has positive arcs and negative arcs over an orbit (the cycle integrates to zero in the absence of eclipse).
- Eclipse blanks a phase interval. Whether the orbit gains or loses energy depends entirely on **which arc** the eclipse covers.

What the figures must show:

| Case | What eclipse blanks | Cumulative SRP work over 1 orbit |
|---|---|---|
| Gain | Predominantly negative-power arc (≈85.7% of eclipse samples are in the negative branch) | Strongly positive (~+800 J/kg eclipse-on; ~−10 J/kg if no eclipse) |
| Neutral | Mixed; ~50–95% positive samples | ~−665 J/kg eclipse-on; ~−5 J/kg no-eclipse |
| Decay | Predominantly positive-power arc | ~−858 J/kg eclipse-on; ~−54 J/kg no-eclipse |

The asymmetry across cases is the proof. If all three cases look qualitatively the same, the cos²α factor in the SRP plugin is wrong (a constant outward force has no power asymmetry).

---

## Setup

Three cases at 700 km, all 1-orbit propagations starting from the same epoch:

| Case | LTDN [h] | Pitch [°] | Source |
|---|---|---|---|
| Gain | 12.266 | 24.8 | gain anchor |
| Neutral | TBD from heatmap (Fig. 2) — pick cell with Δa_max,14d ≈ 0 | TBD | Fig. 2 grid |
| Decay | TBD from heatmap — pick cell with strongly negative Δa_max,14d | TBD | Fig. 2 grid |

**Note**: neutral and decay LTDN/pitch are *chosen from the heatmap after Fig. 2 is done*. Until then, candidate values from `transient.tex` discussion can be used as placeholders (e.g., decay = LTDN 0 h, pitch 90°).

For each case, run **two** 1-orbit propagations:
1. Eclipse-on (plugin applies umbra)
2. Eclipse-off (plugin's `disable_eclipse=True`)

**Step**: ≤10 s for high-cadence sampling. One orbit at 700 km ≈ 5900 s → ~600 samples.

---

## Output data

Plugin sidecar log (per case, per eclipse setting): per-step `t, a_srp_vec, eclipse_flag, true_anomaly`. Post-processing computes:

- `P(t) = a_srp · v` (specific SRP power, J/kg/s)
- `W(t) = ∫₀ᵗ P(t') dt'` (cumulative specific SRP work, J/kg)
- True anomaly ν(t) for the x-axis

For Fig. 4: P vs ν, with eclipse interval shaded; dashed reference = same case eclipse-off.
For Fig. 5: W vs ν, both eclipse-on and eclipse-off curves overlaid.

---

## Acceptance gate

Fig. 5 end-of-orbit cumulative work (per case, eclipse-on vs eclipse-off):

| Case | Eclipse-on [J/kg] | Eclipse-off [J/kg] | Tolerance |
|---|---|---|---|
| Gain | +799.29 | −9.69 | ±10% |
| Neutral | −665.25 | −4.81 | ±20% |
| Decay | −857.93 | −53.90 | ±10% |

Fig. 4 mechanism check (sample-count statistics, gain case):
- Of all samples where eclipse_flag = True, ≥80% have eclipse-off-reference power < 0.

If gain case eclipse-on cumulative work is *negative* or near-zero, the cos²α factor or eclipse hook is wrong.

---

## Runner

`runners/run_fig4_5_per_orbit.py`

- Inputs (CLI): `--case {gain,neutral,decay}`, `--eclipse {on,off}`, `--n_orbits 1`.
- Builds 1-orbit scenario with finer step (10 s).
- Plugin writes sidecar log to `results/fig4_5/{case}_{eclipse}.csv`.
- After all 6 runs (3 cases × 2 eclipse settings), `runners/run_fig4_5_per_orbit.py --aggregate` produces the data tables for plotting.

---

## Plots

`post/plot_fig4_srp_power.py`:
- 3-panel figure (gain | neutral | decay) or single-panel with case overlay.
- For each case: P vs ν solid (eclipse-on), dashed (eclipse-off), shaded eclipse interval.
- X-axis: true anomaly [°]; Y-axis: specific SRP power [W/kg].
- Save to `reproduced_figures/fig4_srp_power.png`.

`post/plot_fig5_cum_work.py`:
- Same 3 cases. For each, two curves: cumulative W eclipse-on (solid), eclipse-off (dashed).
- X-axis: true anomaly [°]; Y-axis: cumulative work [J/kg].
- Annotate end-of-orbit values.
- Save to `reproduced_figures/fig5_cum_work.png`.

Visual diff targets: `Figures/Fig4_Fullrect.png`, `Figures/Fig5_fullrect.png`.

---

## Dependencies

- Plugins validated.
- Fig. 2 heatmap CSV available (to pick neutral/decay cells); placeholder choices acceptable for first iteration.
