# Orekit simulations — independent cross-validation with Orekit 13

Re-runs the validation battery of the manuscript's Section "Validation" using
[Orekit](https://www.orekit.org/) 13.1 in place of Ansys STK 13 / Astrogator,
and reproduces the passive-gain results with an Orekit propagator.

The sibling study `../STK simulations/` holds the STK build and the paper's
open-source reference propagator. This study imports that reference code
verbatim — it does not re-transcribe the physics — so every comparison below is
between two *tools*, not between two typings of the same equations.

## Why Orekit, and why it matters here

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
| `runners/run_gain_lobe.py` | LTDN × pitch map of 14-day Δa_max (Fig. 2 / `repro_gain_lobe`) |
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
