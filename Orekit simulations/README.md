# Orekit simulations — independent cross-validation with Orekit 13

## Revision update (October 2026)

The text below this section was written for the submitted manuscript and is
kept as a record; the revision (`../STK simulations/docs/REVISION_NOTES.md`)
changed three things that supersede several of its headline numbers.

**What changed**

- *Atmosphere table.* `plugins/flatplate_drag_hpop._ATM_TABLE` paired the
  US-1976 base densities with scale heights shifted by one layer, so the profile
  was discontinuous at the layer boundaries (×1.198 at 700 km, ×1.206 at 800 km)
  and up to 21% too dense just below each boundary. The table is now
  interpolated exponentially between the tabulated US-1976 values (3.070×10⁻¹⁴
  at 700 km, 1.136×10⁻¹⁴ kg/m³ at 800 km, continuous). `orekit_core`'s
  `US1976Atmosphere` delegates to the same function, so every Orekit result
  inherits the fix.
- *STK configuration errors found and corrected.* (i) The Astrogator initial
  state carried a default 50 kg fuel tank, so STK propagated a 60 kg vehicle —
  the "−7 km" drag decay. (ii) `AssignQuaternion` takes the scalar *last*; the
  build passed it first, which put the plate normal ~80° from the Sun — the
  "effective SRP area 0 m² / N-plate SRP ignores attitude" finding. With both
  fixed, STK reproduces the SRP response (14-day J2 + N-plate SRP at 800 km:
  STK +15.554 km vs open-source +15.565 km; effective SRP area 81.97 m² at
  epoch) and the gain (full model, 14 d: STK +6.441 km vs open-source
  +5.846 km; 75-day peak +12.92 km vs +10.60 km). Corrected STK spherical drag
  is −60.295 km (700 km) and −17.678 km (800 km) against −70.564 / −18.547 km
  open-source (ratios 0.854 / 0.953, accounted for by STK's co-rotating
  atmosphere and geodetic altitude, see V6 factors below).
- *Anchor moved* from 700 km / LTDN 12.27 h / pitch +24.8° to **800 km,
  LTAN 14.0 h, pitch +35°**. "LTDN" is renamed **LTAN** throughout (the
  formula was always the ascending-node one).

**New headline numbers** (all in `results/*.json`; Orekit = open-source to
≤ 4×10⁻¹⁰ km wherever both are run)

| item | value |
|---|---|
| V2, 14-day J2 + spherical drag, 700 km | **−69.872 km** (was −84.040) |
| V2, 14-day J2 + spherical drag, 800 km | **−18.382 km** (was −21.898) |
| V6 factors, 700 km: co-rotation / geodetic / both / Harris-Priester / NRLMSISE-00 | ×1.034 / ×0.816 / ×0.842 / ×7.081 (re-entry day 10.45) / ×2.574 |
| V6 factors, 800 km | ×1.024 / ×0.901 / ×0.922 / ×3.147 / ×1.587 |
| V7 DP853 + eclipse-event reference, 800 km anchor (full / umbra off / drag only) | **+5.9401** / −10.5864 / −9.8989 km; RK4 30 s +6.127 (+3.1%), 60 s +7.229 (+22%) |
| V8 gain case, 800 km: fixed-1 AU flux vs Orekit analytic Sun; 1/d² flux vs DE-440 | +5.438 vs +5.605 km; +5.933 vs +6.127 km; ephemeris effect 0.52 km |
| V8 former anchor, 700 km | −21.478 vs −21.180 km; −21.158 vs −20.842 km; ephemeris effect 0.36 km |
| LTAN × pitch map, 800 km (24×19 Orekit subset of the 48×37 grid, 456 cells) | **82/82** positive cells agree, RMS diff 0.029 km, max 0.236 km, peak 5.75 vs 5.78 km at LTAN 14.0 h / pitch 30° |
| eclipse causality, 30 d, 800 km pitch 35° | ON +10.33 km, OFF −28.53 km (700 km / 24.8°: ON −90.66, OFF −459 km) |
| 75-day transient, 800 km gain case | peak **+10.95 km on day 37.9**, final −2.37 km, e → 0.0123, apogee 885.6 km, perigee 709.7 km (open-source +10.86 km on day 38.1, final −2.69 km) |
| one-orbit SRP work, 800 km anchor (node-to-node, 6052 s) | umbra 32.0%, sign-selectivity 77.6%, eclipse ON +309.7 J/kg, OFF +0.77 J/kg (open-source +310.3 / +1.4) |
| V10 space weather, 800 km, 14 d, Δa_max (SRP on / SRP off Δa) | US-1976 +5.940 / −9.899; NRLMSISE-00 low (F10.7 = 70, Ap = 4) +13.178 / −2.327; moderate (140, 15) +2.215 / −12.724; high (200, 40) none, −45.455 / −59.583; CSSI file (Jan 2026) +0.500 / −14.426 km |
| V10 space weather, 700 km | US-1976 none, −13.766 / −31.152; low +10.685 / −4.685; moderate none, −30.872 / −45.154; high re-entry within 14 d; CSSI none, −38.517 / −52.777 km |

Superseded statements in the older text below are flagged with
"*Superseded — see Revision update*".

---

Re-runs the validation battery of the manuscript's Section "Validation" using
[Orekit](https://www.orekit.org/) 13.1 in place of Ansys STK 13 / Astrogator,
and reproduces the passive-gain results with an Orekit propagator.

The sibling study `../STK simulations/` holds the STK build and the paper's
open-source reference propagator. This study imports that reference code
verbatim — it does not re-transcribe the physics — so every comparison below is
between two *tools*, not between two typings of the same equations.

## Why Orekit, and why it matters here

> *Superseded — see Revision update:* the STK failure described here was a
> quaternion component-order error in the STK build, now corrected; STK does
> consume the attitude (effective area 81.97 m² at the 800 km anchor).

STK Astrogator could not exercise the configuration the paper actually needs.
Its built-in N-plate SRP model did not consume the satellite's inertially-fixed
attitude: the effective Sun-facing area came out zero for the passively oriented
sail, so an SRP-only propagation was indistinguishable from a J2-only one. The
manuscript therefore had to validate the SRP implementation analytically rather
than against a second tool.

Orekit does not have that limitation, and it also happens to ship exactly the
model elements the paper specifies:

| paper's model | Orekit component |
|---|---|
| central + J2 gravity, degree 2 order 0 | `NewtonianAttraction` + `J2OnlyPerturbation` |
| inertially-frozen sail normal | `FrameAlignedProvider` |
| single body-fixed flat plate, specular/diffuse decomposition | `FixedPanel` inside `BoxAndSolarArraySpacecraft` |
| **binary cylindrical umbra, no penumbra** | `CylindricallyShadowedLightFluxModel` |
| US-1976 piecewise-exponential density | implemented here as an Orekit `Atmosphere` |
| flat-plate drag with `A|cos θ|` projection | the same `BoxAndSolarArraySpacecraft`, double-sided |
| cannonball drag (validation configuration) | `IsotropicDrag` |

Only the density profile had to be supplied, because Orekit ships DTM2000,
NRLMSISE-00, JB2008 and Harris-Priester but not US-1976. It is injected by
implementing Orekit's `Atmosphere` interface in Python via JPype and delegating
`rho(h)` to the paper's own table.

## Results in one paragraph

> *Superseded — see Revision update:* the −84.04 km decay, STK's −7 km and
> 0 m², and the factor 5.9 are pre-revision numbers (now −69.872 km, STK
> −60.295 km and 81.97 m², ×7.081).

Every force component agrees with the paper's own code to machine precision
(≤ 3 × 10⁻¹⁴ relative). The 14-day propagated cross-validation agrees to
3.7 × 10⁻¹⁰ km — sub-micron — including the −84.04 km drag decay at 700 km that
STK reported as −7 km. So two independent propagators agree and STK is the
outlier. Orekit's N-plate SRP model *does* consume the fixed-inertial attitude
(effective area 90.8 m² at the anchor pitch, against STK's 0 m²), which closes
the gap the manuscript had to leave open. Two new findings fall out: the
manuscript's three candidate explanations for the drag divergence are each far
too small to account for it, whereas the choice of atmosphere model spans a
factor of 5.9; and the 14-day gain magnitude is step-size dependent, because a
binary umbra makes the SRP force discontinuous and a fixed-step integrator pays
an O(Δt) penalty at every shadow crossing.

Full numbers: [`docs/RESULTS.md`](docs/RESULTS.md).
Method and conventions: [`docs/METHOD.md`](docs/METHOD.md).

## Layout

```
Orekit simulations/
├── orekit_core/    JVM setup, constants, atmosphere, attitude, spacecraft,
│                   propagator, parallel sweep driver
├── validation/     v1–v7, the cross-validation battery (see below)
├── runners/        gain-regime reproduction, one script per figure
├── docs/           METHOD.md, RESULTS.md
├── results/        JSON/NPZ outputs (tracked — small and quotable)
├── reproduced_figures/  output PNGs (tracked)
├── data/           orekit-data.zip (not tracked; fetch with scripts/fetch_data.sh)
└── scripts/        environment setup and data fetch
```

The package is named `orekit_core`, not `core`, so that it and the reference
study's `core` package can both sit on `sys.path` without shadowing each other.

## Validation battery

| script | what it checks |
|---|---|
| `validation/v1_component_gates.py` | gravity, drag, SRP and eclipse flag, state by state, against the paper's own force code; attitude coupling; residual Sun-ephemeris difference |
| `validation/v2_crossvalidation.py` | 14-day propagated mean SMA, J2-only and J2+drag, 700 and 800 km |
| `validation/v3_instantaneous_drag.py` | density and instantaneous drag acceleration at a matched state |
| `validation/v4_srp_attitude_coupling.py` | **the test STK failed** — does the N-plate SRP model see the fixed-inertial attitude? |
| `validation/v5_calibration_gate.py` | Orekit N-plate against the paper's reduced `C_r cos²α` model |
| `validation/v6_drag_decomposition.py` | co-rotation, geodetic altitude, element definition and atmosphere model, isolated one at a time |
| `validation/v7_eclipse_discontinuity.py` | step-size convergence of the eclipse-gated force |

## Reproduction runners

| script | manuscript counterpart |
|---|---|
| `runners/run_gain_lobe.py` | LTAN (formerly "LTDN") × pitch map of 14-day Δa_max (Fig. 2 / `repro_gain_lobe`) |
| `runners/run_eclipse_causality.py` | eclipse ON vs OFF sign flip (Fig. 3 / `repro_eclipse`) |
| `runners/run_srp_power.py` | one-orbit SRP power and cumulative work (Figs. 4–5 / `repro_srp_power`) |
| `runners/run_long_horizon.py` | 75-day element evolution (Fig. 9 / `repro_transient`) |

## Setup

Arch Linux, CPython 3.14, OpenJDK 21. There is no conda here, and the classic
JCC-based `orekit` package is conda-only, so this study uses `orekit_jpype`,
which drives the stock Orekit jars through JPype.

```bash
./scripts/setup_env.sh     # venv + orekit_jpype + numpy/scipy/matplotlib
./scripts/fetch_data.sh    # orekit-data.zip from gitlab.orekit.org
./run.sh validation/v1_component_gates.py
```

`run.sh` executes any script inside the study's virtual environment from the
study root.

## Reproduce everything

```bash
./scripts/run_all.sh
```

Takes roughly an hour on 16 cores, dominated by the two gain-lobe sweeps.
