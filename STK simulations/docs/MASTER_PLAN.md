# MASTER PLAN — Reproducing Figures 2–9 in Ansys STK / HPOP

> Mirror of `C:\Users\Ian Poon\.claude\plans\you-will-be-primarily-squishy-valiant.md`. The `.claude/plans/` copy is the canonical version that drives the Plan-Mode workflow; this copy lives with the code so contributors can read it without leaving the repo.

---

## Context

The paper (`main.tex` + `Sections/*.tex`) demonstrates that for a passively oriented, spin-stabilised solar sail in near-polar LEO, eclipse timing can produce a *bounded transient* semi-major-axis gain. The result rests on:

- A 2D LTDN×pitch heatmap showing where Δa>0 exists (Fig. 2)
- Eclipse-on vs eclipse-off causality test (Fig. 3)
- Per-orbit SRP power / cumulative work cycles for gain/neutral/decay archetypes (Figs. 4–5)
- Robustness sweeps over roll, density, A/m at 700 km and 800 km (Figs. 6–8)
- 75-day orbital element evolution showing transient nature (Fig. 9)

The original numerics are Julia-based and **not present in this repository** (`STK simulations/` was empty; no `.jl`/`.csv` artefacts exist). The user has an Ansys STK 13 + HPOP licence and a prior STK-HPOP solar-sail validation project at `C:\Users\Ian Poon\Documents\STK_ODTK 13\LEOsolarsailSIMS\` containing reusable Python templates (`agi.stk13` Object Model) and Python reference physics for flat-plate SRP and US-1976 exponential drag that were never wired into HPOP as true plugins.

This plan recreates Figures 2–9 with HPOP using the **exact** sail parameters and force/drag models from the paper. Per user decisions:

1. A real HPOP Python force-model plugin is implemented for flat-plate cos²α SRP.
2. A real HPOP plugin is implemented for US-1976 exponential drag with cos(θ) projected area.
3. The LTDN×pitch sweep starts at 15×15 = 225 cases (validate pipeline) before scaling to 30×30 = 900.
4. Plan files live in both `.claude/plans/` and `STK simulations/docs/`.

---

## Reference Sail / Orbit Parameters (from paper)

| Quantity | Value | Source |
|---|---|---|
| Mass | 10 kg | Table 2, dynmodel.tex |
| Sail area | 100 m² (10×10 m flat plate) | Table 2 |
| A/m | 10 m²/kg | Table 2 |
| C_r | 1.7 | Table 2 |
| C_D | 2.2 | Table 2 |
| Initial altitude | 700 km (primary), 800 km (sensitivity) | dynmodel.tex |
| Initial inclination | 98.17° (700 km), 98.31° (800 km) | paramspace.tex |
| Initial eccentricity | 1×10⁻⁴ | dynmodel.tex |
| Gravity model | Central + J₂ only | dynmodel.tex |
| Atmosphere | US Standard 1976 piecewise-exponential, no co-rotation | dynmodel.tex |
| SRP | Flat-plate, one-sided, cos²α, binary conical eclipse | dynmodel.tex |
| Third-body | none | dynmodel.tex |
| Attitude | Inertially fixed (no active steering) | dynmodel.tex / scope.tex |
| Representative gain case | LTDN = 12.266 h, pitch = 24.8°, RAAN = 285.5° | transient.tex / breakdown.tex |
| Primary metric | Δa_max(T) = max_{t∈[0,T]} (a(t) − a₀) | paramspace.tex |
| Analysis windows | T = 14 days (sweeps), 75 days (long-horizon) | transient.tex / breakdown.tex |

**Sanity checks** the implementation must hit:
- Δa_max,14d ≈ +20.07 km at the heatmap peak (Fig. 2)
- Eclipse-on vs eclipse-off separation ≈ 58 km by day 14 for the gain case (Fig. 3)
- Long-horizon: a peaks ≈ 7098.211 km at day ~26.5, falls to ≈ 7064.717 km by day 75 (Fig. 9)

---

## Architecture

```
STK simulations/
├── docs/
│   ├── MASTER_PLAN.md                  # this file
│   ├── plugin_design.md                # HPOP plugin spec
│   ├── RESULTS.md                      # paper-vs-reproduced numerical comparison (filled in Phase 5)
│   └── figures/
│       ├── figure_2_plan.md
│       ├── figure_3_plan.md
│       ├── figure_4_5_plan.md          # Figs. 4 & 5 share data
│       ├── figure_6_plan.md
│       ├── figure_7_plan.md
│       ├── figure_8_plan.md
│       └── figure_9_plan.md
├── plugins/
│   ├── flatplate_srp_hpop.py           # HPOP Python force-model plugin (cos²α SRP)
│   ├── flatplate_drag_hpop.py          # HPOP Python force-model plugin (US-1976 + cos(θ))
│   └── plugin_register/                # STK plugin registration helpers
├── core/
│   ├── stk_session.py
│   ├── scenario_builder.py
│   ├── attitude.py
│   ├── orbit_init.py
│   ├── data_extract.py
│   └── work_diagnostics.py
├── runners/
│   ├── run_fig2_sweep.py
│   ├── run_fig3_eclipse_compare.py
│   ├── run_fig4_5_per_orbit.py
│   ├── run_fig6_roll_sensitivity.py
│   ├── run_fig7_density_sensitivity.py
│   ├── run_fig8_amr_sensitivity.py
│   └── run_fig9_long_horizon.py
├── post/
│   ├── plot_fig2_heatmap.py
│   ├── plot_fig3_sma_eclipse.py
│   ├── plot_fig4_srp_power.py
│   ├── plot_fig5_cum_work.py
│   ├── plot_fig6_roll.py
│   ├── plot_fig7_density.py
│   ├── plot_fig8_amr.py
│   └── plot_fig9_elements.py
├── results/                            # CSV / parquet outputs (gitignored)
├── reproduced_figures/                 # output PNGs (gitignored)
├── README.md
└── .gitignore
```

---

## Critical Design Decisions

### D1. HPOP custom force-model plugins (the load-bearing bit)

STK 13 HPOP supports Python force-model plugins; the prior attempt at `setup_validation_pystk.py:111-148` set up the scaffolding but reverted to spherical because plugin integration was problematic. We must drive this through.

**`plugins/flatplate_srp_hpop.py`** — implements the HPOP plugin entry-point class. Physics (per `dynmodel.tex`):

```
a_SRP = (P_1AU · (1 AU / r_sun)² · A · C_r / m) · cos²(α) · r̂_sun     (illuminated)
a_SRP = 0                                                               (in umbra)
```

α = angle between sail normal (from inertial-fixed attitude) and Sun line. Eclipse: binary umbral cone.

**`plugins/flatplate_drag_hpop.py`** — US-1976 piecewise-exponential ρ(h) (16-segment table reused from `Documents/STK_ODTK 13/LEOsolarsailSIMS/Plugins/FlatPlateDrag.py`), with cos(θ) projected area:

```
a_drag = -0.5 · ρ(h) · v² · C_D · (A·|cos(θ)| / m) · v̂
```

θ = angle between sail normal and inertial velocity (no atmosphere co-rotation, per paper).

The drag plugin must accept a runtime **density-scaling factor** parameter (multiplier ∈ {0.25, 0.5, 1, 2, 4}) for the Fig. 7 sensitivity sweep.

**Plugin interface details** are specified in `plugin_design.md`.

**Validation gate**: gain anchor case must reproduce paper Δa_max,14d ≈ 14.96–20.07 km within ±5%. Failure → physics is wrong, not a search problem.

### D2. Inertially fixed attitude per (LTDN, pitch, roll, RAAN, epoch)

Sail-normal direction is constant in ECI for the whole propagation. Construction (`core/attitude.py`):

1. From (LTDN, epoch) compute initial RAAN.
2. From (RAAN, inclination) at epoch construct orbit normal and orbit-plane radial-at-epoch.
3. Apply pitch about orbit normal, roll about radial (both at epoch).
4. Freeze the resulting unit vector in ECI.

STK setup: `eVeAttitude.eAttitudeStandard` → `eVeProfile.eProfileFixedInAxes` with reference axes = Earth Inertial and an explicit quaternion that maps body +Z to the chosen sail normal.

**The plugin reads this constant via `PluginSettings`** rather than calling STK each step (since the attitude is inertially fixed, no per-step DataProvider call is needed).

### D3. Eclipse model

Paper uses binary umbral cone. STK's `DualCone` model includes a penumbra. We **bypass STK's SRP shadowing entirely** by disabling it in HPOP and computing eclipse inside the plugin from satellite ECI position vs Sun ECI position vs Earth umbral-cone geometry. This matches the paper exactly and avoids penumbral discrepancy.

### D4. Initial state from (LTDN, pitch)

LTDN → RAAN at epoch:
- Sun RA(epoch) computed from a JD-based formula (or read from STK CentralBody/Sun position).
- RAAN = SunRA + 15°·(LTDN_h − 12) (descending node convention; cf. `run_ltan_sso_solar_sail_pystk.py:120-127`).

Inclination per altitude: 700 km → 98.17°, 800 km → 98.31°.
True anomaly @ epoch = 0° (ascending node); argument of perigee = 0°.
Eccentricity = 1×10⁻⁴.

Epoch fixed at **1 Jan 2026 12:00:00 UT** (matching the prior attempt's convention — only enters via Sun RA, which is already absorbed by LTDN→RAAN).

### D5. Data extraction

- **Classical Elements (ICRF)** at 60 s step → a, e, i, Ω, ω, ν → r_a, r_p
- **Cartesian (ICRF)** at ≤10 s step for high-cadence per-orbit Fig. 4/5 plots
- **Eclipse intervals** computed inside the plugin and emitted via sidecar log
- **Custom plugin sidecar log** per integration step: `t, r_eci, v_eci, a_srp_vec, a_drag_vec, eclipse_flag` — avoids re-deriving forces from ephemeris

Post-processing (`core/work_diagnostics.py`) computes Δa_max(T), per-orbit ∫a·v dt for SRP and drag, and orbit-mean transverse/normal force decompositions.

### D6. Compute strategy

15×15 grid (225 cases × 14 d) → likely minutes per case in HPOP @ 60 s step → feasible serially. Use **STK Engine (headless)** via `agi.stk13.stkengine.STKEngine` for sweeps to avoid GUI overhead and enable per-process concurrency. Final 30×30 = 900 cases will likely take overnight.

---

## Per-Figure Plans (each in `docs/figures/figure_N_plan.md`)

| Figure | Goal | Sweep size | Time horizon | Acceptance gate |
|---|---|---|---|---|
| 2 | LTDN×pitch heatmap, narrow gain lobe @ 700 km | 15×15 → 30×30 | 14 d | Peak Δa ≈ +20 km @ (12.27 h, 24.8°), ~10% cells positive |
| 3 | Eclipse-on/off causality, gain anchor | 2 cases | 75 d | day 14: +10.31 km vs −47.75 km (Δ ≈ 58 km) |
| 4 | SRP power vs ν, gain/neutral/decay | 3 cases × 1 orbit | 1 orbit | gain: 85.7% of eclipse samples in negative-power arc |
| 5 | Cumulative SRP work vs ν | 3 cases × eclipse-on/off × 1 orbit | 1 orbit | gain: +799 vs −9.7 J/kg (eclipse on/off) |
| 6 | Roll sensitivity ±45° @ 700 + 800 km | ~30 cases | 14 d | 700: 14.96 km @ 0°; 800: 33.94 km @ 0°, broader envelope |
| 7 | Density 0.25× to 4× @ 700 + 800 km | 10 cases | 14 d | 700 km @ 2× → 0; 800 km @ 4× → 10.25 km |
| 8 | A/m 2.5–22.5 @ 700 + 800 km | 22 cases | 14 d | 700 non-monotonic w/ peak @ A/m=14.4; 800 monotonic to 71.61 km |
| 9 | 75-day element evolution, gain case | 1 case | 75 d | a_max ≈ 7098.211 km @ day 26.50; final ≈ 7064.717 km |

See `docs/figures/figure_N_plan.md` for the full per-figure spec including scientific objective, runner, plot script, exact sweep enumeration, and detailed acceptance numbers.

---

## Implementation Phases

| Phase | Work | Done when |
|---|---|---|
| **0** (this commit) | Scaffolding: docs, plan mirror, README, .gitignore, empty package dirs | Files written, user reviews |
| **1** | SRP + drag plugins, core utilities, Fig. 9 single-case smoke test | Gain anchor 75-day a-peak within ±1% of paper |
| **2** | Fig. 3 (eclipse-on/off) + Fig. 4/5 (per-orbit diagnostics) | Fig. 3 separation ≈ 58 km; Fig. 5 work numbers ±10% |
| **3** | Sensitivity sweeps Fig. 6, 7, 8 | Per-figure acceptance gates met |
| **4** | Fig. 2 sweep (15×15 → 30×30) | Heatmap peak at gain anchor; ~10% positive cells |
| **5** | Cross-checks, `RESULTS.md`, side-by-side visual diffs | All acceptance gates met across all figures |

---

## Critical Files to Reuse / Adapt

From `C:\Users\Ian Poon\Documents\STK_ODTK 13\LEOsolarsailSIMS\`:
- `setup_validation_pystk.py:78-148` — HPOP scenario / force-model setup template
- `Plugins/FlatPlateSRP.py` — physics reference (note: paper uses **cos²α** not cos¹; paper convention wins)
- `Plugins/FlatPlateDrag.py` — US-1976 atmosphere table
- `run_ltan_sso_solar_sail_pystk.py:120-127` — LTAN→RAAN formula and `eProfileFixedInAxes` template
- `export_stk_reports.py:18-51` — DataProvider extraction pattern

Read-only references:
- `Sections/dynmodel.tex`, `paramspace.tex`, `transient.tex`, `breakdown.tex`, `sensitivity.tex`
- `Figures/ltdn.png`, `Fig3oldno.png`, `Fig4_Fullrect.png`, `Fig5_fullrect.png`, `fig6_w78.png`, `fig7_w78.png`, `fig8_w78.png`, `Fig9_rect.png`

⚠ The prior attempt used a *different sail* (36 m², C_r=1.8). Do **not** carry those numbers forward — paper sail is 100 m², C_r=1.7.

---

## Verification

1. Run all 8 figure runners → CSVs in `results/figN/`.
2. Run all 8 plot scripts → PNGs in `reproduced_figures/`.
3. `docs/RESULTS.md` table compares each acceptance-gate number to reproduced number — every row within tolerance.
4. Manual visual diff: paper `Figures/<name>.png` vs reproduced PNG side-by-side.

---

## Risks

- **STK 13 Python plugin loader debugging.** The previous attempt stopped at this gate. If unresolved → fallback to STK External Force Model interface with per-step Connect callback.
- **Inertial vs RIC attitude semantics.** "Inertially fixed at given pitch" → exact construction encoded in `core/attitude.py`. Verify by computing α(t) over one orbit and checking the expected α-cycle.
- **Density-scaling parameter wiring.** Plugin parameter passing may need template-regenerated plugin files per density factor if `PluginSettings.SetProperty` doesn't propagate.
- **Compute time on full 30×30.** If single-case wall time >2 minutes, queue overnight; provide `--resume` flag.
