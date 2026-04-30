# STK simulations — Reproducing Figures 2–9 in Ansys STK / HPOP

Recreates the Julia-based simulations behind Figures 2–9 of the paper using **Ansys STK 13 + HPOP** with custom Python force-model plugins for the paper's flat-plate cos²α SRP and US-1976 exponential-atmosphere drag (HPOP's built-in models are spherical, which would erase the paper's mechanism).

## Read this first

- `docs/MASTER_PLAN.md` — full architecture, parameters, design decisions.
- `docs/plugin_design.md` — HPOP plugin physics + STK API wiring.
- `docs/figures/figure_N_plan.md` — per-figure scientific objective, runner, acceptance gate.

## Layout

```
STK simulations/
├── docs/         plans (start here)
├── plugins/      HPOP Python force-model plugins
├── core/         scenario builder, attitude, orbit init, data extraction
├── runners/      one per figure
├── post/         plotting scripts
├── results/      raw CSVs (gitignored)
└── reproduced_figures/   output PNGs (gitignored)
```

## Recommended order to develop / run

1. **Phase 1**: build plugins + `core/`. Run `runners/run_fig9_long_horizon.py` first — it's the smallest end-to-end test and gates everything else (must reproduce a-peak ≈ 7098.211 km at day ~26.5 within ±1%).
2. **Phase 2**: `runners/run_fig3_eclipse_compare.py`, `runners/run_fig4_5_per_orbit.py`.
3. **Phase 3**: sensitivity sweeps Fig. 6, 7, 8.
4. **Phase 4**: heatmap sweep — start at 15×15 then scale to 30×30.
5. **Phase 5**: cross-checks; fill in `docs/RESULTS.md`.

## Sail and orbit parameters (locked)

| | |
|---|---|
| Mass | 10 kg |
| Sail area | 100 m² |
| C_r | 1.7 |
| C_D | 2.2 |
| Altitude | 700 km (primary), 800 km (sensitivity) |
| Inclination | 98.17° / 98.31° |
| Eccentricity | 1×10⁻⁴ |
| Gain anchor | LTDN = 12.266 h, pitch = 24.8°, roll = 0° |
| Epoch | 1 Jan 2026 12:00:00 UT |

These come from `Sections/dynmodel.tex` and `breakdown.tex` of the paper. **Do not** copy the parameters from the prior `Documents/STK_ODTK 13/LEOsolarsailSIMS/` project — those are for a different sail (36 m², C_r=1.8).

## STK environment expectations

- Ansys STK 13 with HPOP licence.
- Python 3.x with `agi.stk13` package installed.
- STK Engine (headless) for sweeps; STK Desktop for interactive debugging.

## Reusable templates from the prior attempt

`C:\Users\Ian Poon\Documents\STK_ODTK 13\LEOsolarsailSIMS\`:
- `setup_validation_pystk.py:78-148` — HPOP scenario builder pattern
- `Plugins/FlatPlateSRP.py` — physics reference (note: uses cos¹; paper uses cos²)
- `Plugins/FlatPlateDrag.py` — US-1976 atmosphere table
- `run_ltan_sso_solar_sail_pystk.py:120-127` — LTAN→RAAN and `eProfileFixedInAxes`
- `export_stk_reports.py` — DataProvider extraction

## Status

Phase 0 (this commit): planning docs + directory scaffolding. No code yet.
