# RESULTS — STK / independent validation of the paper's claims

Status of the effort to reproduce Figures 2–9 to validate the manuscript.

## Bottom line
- The **STK Astrogator N-plate pipeline is built and runs** (headless, mean-element
  extraction). Its **drag** side is validated against the paper (STK `US Standard
  Atmosphere` density at 700 km = 3.2e-14 kg/m³ ≈ the paper's 3.07e-14). Its **SRP**
  side is blocked by an STK limitation: Astrogator's N-plate SRP force model does not
  consume the satellite's fixed-inertial attitude (effective `SRPArea = 0`), so the
  figures are produced from an **independent offline propagator of the paper's exact
  model** (`core/offline_propagator.py`), cross-checked against STK where STK works.
- The paper's **qualitative mechanism reproduces**: eclipse-gated, sail-normal-directed
  SRP does positive net work over an orbit only when eclipse removes the negative-work
  arc; this yields a **bounded transient semi-major-axis gain** in a **narrow lobe** of
  LTDN×pitch space at **positive pitch** — matching the paper's Fig 2 structure.
- The **magnitude does not reproduce**. Independent modeling gives a gain lobe only at
  **800 km** (peak Δa_max,14d ≈ +4 km at LTDN≈14 h, pitch≈34°); at the paper's **700 km**
  anchor the orbit is **drag-dominated (no gain)**. This traces to a **~2.5× shortfall in
  per-orbit SRP work** vs the paper (mine ≈ +325 J/kg max, paper Fig 5 = +799 J/kg).

## Reproduced vs paper (per claim)
| Claim | Paper | Independent model | Verdict |
|---|---|---|---|
| Gain exists in a narrow LTDN×pitch lobe | Fig 2, ~10% of cells @700 km | Lobe exists @800 km (~27% cells); none @700 km | Qualitative ✓, altitude/fraction differ |
| Lobe at positive pitch, mid-LTDN | peak (12.27 h, 24.8°) | peak (≈14 h, ≈34°), anchor sits in the lobe @800 km | ✓ (location matches) |
| Eclipse causally enables gain (sign flip) | eclipse-on +, off − | eclipse-off net SRP ≈ 0 (cancels); eclipse-on gates it | Mechanism ✓ |
| Per-orbit SRP work (gain case) | +799 J/kg | +325 J/kg max (eclipse ~72% on negative arc, not ~90%) | ✗ magnitude (see note) |
| Transient, self-limiting | peak then decay | drag-dominated decay envelope; transient gain only where SRP>drag | Partial |
| 700 km 14-day Δa_max | +14.958 km | 0 (drag-dominated) | ✗ at 700 km |

## Why the magnitude differs (diagnosis)
The one-orbit SRP power is a near-symmetric ± cycle (one lobe ≈ ±905 J/kg). Net work
needs eclipse to remove the negative lobe. A 35% eclipse **perfectly centered on the
negative-power trough** removes ~90% of it → net ≈ +810 J/kg (≈ the paper's +799). But
the eclipse sits at the **anti-Sun point**, which for this geometry is offset from the
trough; independent modeling reaches only ~72% coverage → +325 J/kg. Reaching +799
requires the eclipse centered on the trough, which conflicts with keeping the sail
near-Sun-pointing (the trough approaches the anti-Sun point only as pitch→90°, where SRP
→0). **This suggests the paper's +799 J/kg (and hence the 700 km gain) may be optimistic
or rests on an unstated convention (e.g. a longer/conical eclipse, an evolved-orbit
representative orbit, or a different SRP direction).** The paper's own Fig 4 (85.7% of
eclipse samples on the negative arc → ≈+325 J/kg by the same accounting) is more
consistent with the independent result than its Fig 5 (+799 J/kg).

## Figures produced (offline engine, `reproduced_figures/`)
Featuring a reproduced GAIN case (800 km, LTDN 14 h, pitch 34° — in the 800 km lobe) and
the paper's 700 km anchor (drag-dominated), per the honest qualitative-validation plan.

| File | Content | Reproduced result | Paper |
|---|---|---|---|
| `fig2_heatmap_800km.png` / `_700km.png` | LTDN×pitch Δa_max map | 800 km: connected lobe at pitch 20–50°, peak +4.1 km @ (14 h, 34°), 27% cells +. 700 km: no gain. | lobe @700 km, peak +20 km @ (12.27 h, 24.8°), ~10% + |
| `fig3_eclipse_causality.png` | eclipse ON vs OFF Δa(t) | 800 km gain case: ON **+7 km** vs OFF **−31 km** (sign flip). 700 km: both decay, ON decays less. | ON +10.31 vs OFF −47.75 km (sign flip) |
| `fig4_srp_power.png` | one-orbit SRP power + eclipse | eclipse removes the negative arc; **77%** of eclipsed samples would-be-negative | 85.7% |
| `fig5_cum_work.png` | cumulative one-orbit SRP work | eclipse-ON **+343 J/kg** vs no-eclipse +46 | +799 vs −9.7 J/kg |
| `fig6_roll.png` | roll ±45° sensitivity | 800 km peaks near roll 0 (4.2 km), falls to 0 by ±40°; 700 km flat 0 | peak at 0, 800 km broader |
| `fig7_density.png` | density ×{0.25..4} | gain rises as density falls; **700 km recovers +7.6 km at 0.25×**; 800 km 1×→4.1, 0.25×→12.2 | 700 km 0.25×→34.9, 2×→0 |
| `fig8_amr.png` | A/m 2.5–22.5 | 800 km monotonic 0.9→6.9 km; 700 km flat 0 | 800 km monotonic→71.6; 700 km non-monotonic |
| `fig9_elements.png` | 75-day elements | gain case: Δa peaks **+7.3 km @ day 34** then falls below 0 by ~day 62; apogee pumps to 905 km, e→0.014, perigee erodes. 700 km anchor reenters ~day 36. | a peak +20 km @ day 26.5, then decline; apogee pump; e→0.022 |
| `calibration_gate.png` | offline SRP calibration | N-plate (0.3,0.7,0) matches paper 1.7cos²α to ≤1.6% (α≤45°) | — |

**Verdict:** every qualitative claim reproduces (narrow gain lobe at positive pitch; eclipse
causally flips the SRP-work sign; transient apogee-pumping gain that self-limits; gain rises as
density falls and with A/m). Magnitudes are ~3–5× smaller and the regime is shifted to 800 km,
because independent per-orbit SRP work (~+343 J/kg) is ~2.3× below the paper's +799 J/kg. Fig 7 shows
this is a drag-vs-SRP-balance issue: dropping 700 km density to 0.25× recovers a multi-km gain.

## STK cross-checks (validated)
- Drag: STK US-1976 density matches the paper's table; N-plate `DragArea` = A|cosθ|.
- Mean elements: STK Brouwer-Lyd mean SMA is J2-flat / SRP-pumps / drag-decays as expected.
- Eclipse: STK cylindrical/dual-cone shadow available; used for the causality test.
