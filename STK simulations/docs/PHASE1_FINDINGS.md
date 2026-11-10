# Phase 1 findings — STK Astrogator N-Plate pipeline + the gain-regime discrepancy

## What now works (verified)
- **STK Astrogator N-Plate pipeline is built and runs headless** (STKEngine, ~12 s for a 14-day
  propagation). `core/astrogator_mcs.py` + `core/nplate_files.py` configure: Gravitational Force
  (deg 2 / order 0 = central+J2), `US Standard Atmosphere` (1976) drag with an N-Plate area model
  (opposed ±Z plates → projected area A·|cosθ|), and `NPlate SRP` (one +Z body plate, specular 0.70
  → C_r,eff = 1.7), Cylindrical shadow, inertially-fixed attitude, Duration stop. API fully mapped in
  `astrogator_design.md`.
- **Force models validated in mean elements** (Brouwer-Lyd Mean Long, which removes the ±9 km J2
  short-period osculating wiggle): J2-only → flat; SRP-only → mean SMA rises; drag-only → decays.
- **Offline SRP calibration gate passes** (`validation/calibration_gate.py`): the N-Plate (0.3,0.7,0)
  matches the paper's 1.7cos²α magnitude to ≤1.6% for α≤45°.

## The discrepancy: the paper's transient gain does NOT reproduce
At the paper's gain anchor (LTDN 12.266 h, pitch 24.8°, RAAN 285.5°, 700 km), **both STK and an
independent offline propagation of the paper's own model show monotone mean-SMA decay, not the
paper's +14.958 km (14-day) / +20.07 km (26-day) gain.** A scan over LTDN∈[0,24] × pitch∈[−35,45]
finds **no gain cell anywhere**.

### Root causes found (via `validation/work_probe.py`, per-orbit specific work in J/kg)
1. **SRP direction matters decisively.** With SRP along the **Sun line** (the paper's *implemented*
   Eq. `srp_force`, `a∝cos²α·r̂`), the per-orbit SRP net work is ≈ **0** at every geometry — the
   eclipse sits on the work-cycle zero-crossing (anti-Sun point) and the positive/negative arcs
   cancel (50% eclipse "sign-selectivity"). Only with SRP along the **sail normal** (the paper's
   *reduced* model `a∝cos²β·n̂`, and what STK's specular N-Plate computes) does eclipse gating produce
   net work. **STK's normal-directed N-Plate is therefore necessary to reproduce the mechanism.**
2. **Attitude convention.** The prior `core/attitude.py` tilted the sail normal toward the orbit
   normal (out of plane) → no along-track SRP. Fixed to tilt **in the orbital plane** (base =
   r̂_sun × ĥ), which yields the along-track component the pumping mechanism requires.
3. With (1)+(2) the mechanism reproduces: per-orbit SRP net work reaches **±280–314 J/kg**,
   sign-flips with pitch sign, eclipse-selectivity swings 34%→72%, and `SRP_off ≈ 0` confirms the
   work is entirely eclipse-enabled — qualitatively the paper's mechanism.

### Why it still doesn't tip into net gain
- My drag ≈ **−500 to −680 J/kg/orbit** (order-matches the paper's ~−500).
- My SRP net work ceiling ≈ **+320 J/kg/orbit**. With a ~35% eclipse fraction (sun-in-plane at LTDN
  12.27), the eclipse can cover at most ~70% of the negative half-cycle, capping the recoverable work
  near +320 J/kg — **less than the drag**, so net is negative everywhere → decay.
- The paper reports SRP **+799 J/kg/orbit** (Fig 5), which **exceeds** what a 35%-eclipse geometry can
  produce at this SRP magnitude (peak power ≈ 0.48 W/kg). The paper's own Fig 4 (85.7% eclipse
  selectivity) implies ~+320 J/kg by the same accounting — **internally inconsistent with Fig 5's
  +799 J/kg**. The ~2.5× SRP gap and the ~1.35× drag gap together decide gain-vs-decay.

## ROOT CAUSE of the STK SRP failure (found)
STK Astrogator's **N-plate SRP force model does not use the satellite's
`eProfileFixedInAxes` attitude**. Evidence:
- STK's effective `SRPArea = 0`, `Cr = 0` for the N-plate build (read from the
  `Astrogator Values > Spacecraft Properties` provider), i.e. the one-sided +Z sail
  plate is oriented ~90° from the Sun → zero SRP force. With plate normal −Z the
  effective SRPArea is only ~4 m² (≈100·cos 87.6°), confirming the plate normal sits
  ~90° from the Sun, i.e. along the in-plane `base` vector, **not** the intended
  24.8°-from-Sun sail normal.
- The satellite's attitude IS set correctly: the `Attitude Quaternions` provider
  returns (0.361, 0.897, 0.256, 0), which exactly equals `normal_to_quaternion_eci(N)`
  (body +Z → the intended sail normal). So `sat.Attitude.Basic` is right, but the
  Astrogator N-plate force model ignores it.
- Setting the attitude before vs after `SetPropagatorType(Astrogator)` makes no
  difference (both give SRPArea = 0).
- The N-plate **drag** model *does* respond to attitude (`DragArea` sweeps 1.2→99.4 =
  the |cosθ| velocity projection) — but it uses Astrogator's default body frame, the
  same one that leaves the SRP plate ⊥ to the Sun.

**Corrected sub-facts** (earlier tentative worries, now resolved):
- STK's `US Standard Atmosphere` density at 700 km = 3.2e-14 kg/m³ (reported 3.2e-5
  kg/km³), which **matches** the paper's table (3.07e-14). Drag is correct.
- `Cartesian Acceleration` reports only central gravity, not perturbations — it cannot
  be used to read SRP/drag; use `Astrogator Values` effective areas or the mean-SMA
  trajectory response instead.

**Remaining fix**: make Astrogator's N-plate force models use the inertially-fixed
sail attitude (correct attitude→force-model coupling, an Astrogator-specific setup),
or adopt one of the alternative paths in the session report.

## Unresolved STK-side issues (likely config, separate from the paper question)
- **STK's N-Plate SRP net effect on mean SMA is ~0** with the in-plane attitude: SRP-only is
  identical to J2-only (both da_end ≈ +0.008 km/2d), and full == drag-only. Before the attitude
  change SRP-only gave +0.28 km/2d. STK's N-Plate is attitude-dependent, but a *zero* net effect is
  suspicious — needs a direct measurement of STK's applied SRP acceleration (via an accel data
  provider or ephemeris differencing) and a check that the eProfileFixedInAxes quaternion orients the
  plate +Z normal to the intended Sun-facing direction (one-sided plate → zero force if STK sees the
  Sun on the back face).
- **STK's `US Standard Atmosphere` (1976) density at 700 km appears ~8× lower than the paper's
  16-segment table** (STK drag-only ≈ −0.57 km/2d vs offline ≈ −4.48 km/2d). Needs a direct density
  read-back at 700/800 km and reconciliation with `density_us1976_kg_m3` (3.07e-14) — the paper's
  drag baseline may differ from STK's built-in 1976 model.

## Open question (needs the paper's exact numerics / a decision)
Reproducing the published gain requires closing the SRP-work gap (and/or the drag gap). That depends
on the paper's exact constants and conventions — solar-flux value, the precise SRP direction actually
used for the propagated figures (Sun-line vs normal), the eclipse model, and whether Fig 5's +799
J/kg is a first-orbit or a later-orbit value. This is a co-author decision (see the session report).

## Reusable artifacts
- `validation/calibration_gate.py` — offline SRP calibration (α-sweep + one-orbit model agreement).
- `validation/probe_*.py` — STK API discovery (→ `astrogator_*.md`).
- `validation/test_build_run.py` — end-to-end STK build/run/extract (mean SMA).
- `validation/diag_srp.py` — J2/SRP/drag isolation (mean elements).
- `validation/offline_reference.py`, `offline_scan.py`, `work_probe.py` — offline paper-model
  cross-checks and per-orbit work diagnostics.
