# Figure 2 — LTDN × Pitch Heatmap of Δa_max,14d at 700 km

**Paper reference**: `Sections/transient.tex`, label `fig:heatmap_700km`. Source PNG: `Figures/ltdn.png`.

---

## Scientific objective

Establish that the eclipse-modulated SMA-gain regime is **spatially confined**: across a full 2D LTDN × pitch space, only a narrow lobe near LTDN ≈ 12.27 h, pitch ≈ 24.8° produces net Δa > 0 within 14 days. The figure must visually demonstrate that the gain regime is the *exception, not the rule* — supporting the abstract's "narrow result" framing. If the heatmap shows positive Δa across most of the parameter space, we have not reproduced the paper's central finding.

What this figure must show, beyond just data:

1. **A single dominant positive lobe** at the gain anchor; not multiple disconnected high-Δa regions.
2. **The bulk of the map net-decaying** (Δa ≤ 0); the paper reports ~10% positive cells.
3. **Sharp rather than diffuse boundary** of the positive lobe.

If any of these three features are missing, the SRP plugin is suspect — most likely the `cos²α` factor or the eclipse hook.

---

## Setup

| Item | Value |
|---|---|
| Altitude | 700 km |
| Inclination | 98.17° (SSO at 700 km) |
| Eccentricity | 1×10⁻⁴ |
| Sail area | 100 m² |
| Mass | 10 kg |
| C_r | 1.7 |
| C_D | 2.2 |
| Time horizon T | 14 days |
| Step | 60 s (HPOP), 30 s (sidecar log) |
| Phase 1 grid | 15 × 15 = **225 cases** (LTDN ∈ [0, 24] h, pitch ∈ [0°, 180°]) |
| Phase 2 grid | 30 × 30 = **900 cases** (matches paper resolution) |

**Sweep variables**:
- LTDN: linspace(0, 24, N) hours, with N ∈ {15, 30}
- Pitch: linspace(0, 180, N) degrees

**Roll**: held at 0° throughout (roll is the Fig. 6 sweep variable, not Fig. 2's).

---

## Output metric

Per (LTDN, pitch) cell:

```
Δa_max,14d = max_{t ∈ [0, 14d]} (a(t) − a₀)        [km]
```

`a(t)` from STK Classical Elements (ICRF) DataProvider at 60 s. `a₀ = 7078.137 km` (initial). Cells where `a(t) − a₀ < 0` ∀ t are reported as `Δa_max = 0` (or as the most-positive value, even if negative — keep the sign so the diverging colormap reads correctly).

---

## Acceptance gate

**Phase 1 (15×15 grid)**:
- Peak cell: Δa_max ≈ +20 km within ±15% (grid coarseness allows ±15%).
- Peak cell location: nearest-neighbour to (LTDN=12.27 h, pitch=24.8°).
- Total positive cells: 8–25% of 225.
- Visual lobe shape: single connected region, not fragmented.

**Phase 2 (30×30 grid)**:
- Peak cell: Δa_max ≈ +20.07 km within ±5%.
- Peak cell location: within one grid cell of (12.27 h, 24.8°).
- Total positive cells: ~89/900 ≈ 9.9% (target 8–12%).
- Two minor retrograde-pitch clusters (gains <0.14 km) visible.

If Phase 1 fails any gate, **stop the sweep** and debug (most likely the SRP plugin's α computation or eclipse hook). Phase 2 is only run after Phase 1 passes.

---

## Runner

`runners/run_fig2_sweep.py`

```
usage: run_fig2_sweep.py [--n N] [--resume] [--workers W]
  --n      grid size per axis (default 15; use 30 for paper resolution)
  --resume skip cells already in results/fig2/cells/{ltdn}_{pitch}.csv
  --workers concurrent STK Engine processes (default 1; cap at min(N_cells, n_cores))
```

- Builds an STK Engine session per worker.
- For each (LTDN, pitch) cell:
  - Compute RAAN at epoch from LTDN (`core/orbit_init.compute_raan_from_ltdn`).
  - Compute inertial sail-normal vector (`core/attitude.inertial_sail_normal_from_pitch_roll`).
  - Build scenario + satellite + force model with plugins (`core/scenario_builder.build_satellite`).
  - Propagate 14 days.
  - Extract Classical Elements at 60 s (`core/data_extract.extract_classical_elements`).
  - Compute `Δa_max,14d` (`core/work_diagnostics.delta_a_max`).
  - Write `results/fig2/cells/{ltdn:.4f}_{pitch:.4f}.csv` with one row.
- Aggregate all cells into `results/fig2/heatmap.csv` with columns `ltdn_h, pitch_deg, delta_a_max_km`.

---

## Plot

`post/plot_fig2_heatmap.py`

- Reads `results/fig2/heatmap.csv`.
- Reshapes to 2D grid.
- `pcolormesh` with diverging colormap (`RdBu_r`), centered at 0, symmetric clip at ±|max(|Δa|)|.
- Overlay contour at Δa = 0 (white line).
- Mark gain anchor (12.27 h, 24.8°) with a black cross.
- Save to `reproduced_figures/fig2_heatmap_700km.png`.

Visual diff target: `Figures/ltdn.png`.

---

## Compute estimate

Per case: 14 d × 86400 s / 60 s = 20,160 integration steps. HPOP with custom Python plugins likely 1–3 ms per step → ~20–60 s wall per case. 225 cases × 30 s = ~2 hours single-threaded; 900 cases × 30 s = ~7.5 hours single-threaded. Multi-process via STK Engine should bring 30×30 to overnight.

If single-case time is much higher (say 5+ minutes), the plugin's per-step COM overhead is the bottleneck — investigate caching the Sun position and avoid repeated DataProvider calls.

---

## Dependencies (must exist before this runner runs)

- `plugins/flatplate_srp_hpop.py` (validated against published anchor)
- `plugins/flatplate_drag_hpop.py` (validated)
- `core/{stk_session,scenario_builder,attitude,orbit_init,data_extract,work_diagnostics}.py`
- Acceptance of Fig. 9 single-case run (Phase 1 gate)
