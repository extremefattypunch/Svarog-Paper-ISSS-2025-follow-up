# Figure 3 — Eclipse-on vs Eclipse-off SMA(t) for the Representative Gain Case

**Paper reference**: `Sections/transient.tex`, label `SMA_eclipse`. Source PNGs: `Figures/fig3oldno.png`, plus rect/square/clut variants.

---

## Scientific objective

Prove that **eclipse is causally responsible** for the SMA gain — not just correlated. The same geometry, propagated *without* eclipse shadowing, must decay strongly. The 14-day separation between the two trajectories (≈58 km in the paper) is the headline number that establishes causality.

What this figure must show:

1. Eclipse-on case: monotonic-ish Δa rising for ~14 days, then turning over.
2. Eclipse-off case: monotonic decay from t=0, no positive excursion.
3. The two curves separate immediately and continue to diverge for the full 75-day window (eclipse-off curve crosses zero around day ~42.8 according to `transient.tex`).

If the two curves track each other, the SRP plugin's eclipse hook is broken — the plugin is computing SRP regardless of the umbra flag.

---

## Setup

| Item | Value |
|---|---|
| Altitude | 700 km |
| Inclination | 98.17° |
| Eccentricity | 1×10⁻⁴ |
| LTDN | 12.266 h (gain anchor) |
| Pitch | 24.8° |
| Roll | 0° |
| RAAN | 285.5° (computed from LTDN at epoch 1 Jan 2026 12:00 UT — verify) |
| Time horizon | 75 days |
| Step | 60 s |
| Cases | 2 (eclipse-on, eclipse-off) |

The only difference between the two propagations is the SRP plugin's `disable_eclipse` flag (`False` = paper baseline; `True` = eclipse hook bypassed, SRP applied always).

---

## Acceptance gate

| Quantity | Eclipse-on | Eclipse-off | Tolerance |
|---|---|---|---|
| Δa @ day 14 | ≈ +10.31 km | ≈ −47.75 km | ±15% (each) |
| Separation @ day 14 | ≈ 58 km | — | ±10% |
| Eclipse-off zero-crossing | — | ≈ day 42.8 | ±3 days |
| Eclipse-on long-horizon | a peaks ~day 26.5 then decays | — | qualitative |

Note the slight discrepancy between paper numbers: the heatmap peak is +20.07 km but the eclipse-on Δa @ day 14 is reported as +10.31 km — these are different metrics (max over window vs value at endpoint of window). The runner records both.

---

## Runner

`runners/run_fig3_eclipse_compare.py`

- Build gain-anchor scenario.
- Run twice with `disable_eclipse ∈ {False, True}`.
- For each, extract Classical Elements at 60 s for 75 days.
- Save `results/fig3/sma_eclipse_on.csv` and `sma_eclipse_off.csv` with columns `t_sec, t_days, a_km, delta_a_km`.

---

## Plot

`post/plot_fig3_sma_eclipse.py`

- Two curves on same axes: Δa(t) for eclipse-on (solid) and eclipse-off (dashed).
- X-axis: time [days], 0–75.
- Y-axis: Δa [km].
- Annotate: separation at day 14 (vertical reference line + value), eclipse-off zero-crossing.
- Save to `reproduced_figures/fig3_sma_eclipse.png`.

Visual diff target: `Figures/fig3oldno.png`.

---

## Dependencies

- Plugins validated.
- Phase 1 gate (Fig. 9 anchor) must have passed — same geometry.
- `runners/run_fig9_long_horizon.py` can share its eclipse-on result with this figure (no need to re-run).
