# Method and conventions

What was held fixed, what was allowed to differ, and why.

## The comparison design

The purpose is to distinguish *implementation* differences from *modelling*
differences. Three things are therefore pinned across both tools:

1. **Physical constants.** `orekit_core/constants.py` carries the paper's
   values — mu = 3.986004418e14 m³/s², R_e = 6 378 136.3 m,
   J2 = 1.082626173e-3, P_1AU = 4.5605e-6 N/m², 1 AU = 1.495978707e11 m — and
   they are passed explicitly into every Orekit constructor. Orekit would
   otherwise default to WGS-84 / EIGEN-5C values, which differ in the 8th digit
   and would show up as a spurious inter-tool residual.
2. **The reference implementation.** The paper's force code is imported from
   `../STK simulations/` rather than retyped: `core.dynamics.gravity_j2_eci`,
   `plugins.flatplate_drag_hpop`, `plugins.flatplate_srp_hpop`,
   `core.attitude.inertial_sail_normal`, `core.orbit_init.raan_from_ltdn`. A
   disagreement is therefore a disagreement between Orekit and the paper, not
   between two transcriptions.
3. **The initial state and the mean-element definition.** Both tools start from
   the same Keplerian elements (a = R_e + h, e = 1e-4, i per altitude, RAAN
   from LTDN, argument of perigee 0, true anomaly 0) at 1 Jan 2026 12:00 UT, and
   both extract mean elements by the same stroboscopic rule (first sample at or
   after the z sign change from negative to positive, no interpolation).

## What is deliberately *not* pinned

Three things are left as each tool's own, and are quantified rather than
removed:

* **Sun ephemeris.** Orekit reads DE-440; the paper uses a low-precision
  analytic (Meeus) series and holds the Earth-Sun distance at exactly 1 AU.
  Measured in `v1_component_gates.py`: the directions differ by up to 0.37° over
  the 75-day window, and the true Sun distance departs from 1 AU by up to 1.7%,
  which is a 3.4% flux difference — the epoch sits within days of perihelion.
  The three force gates are evaluated with a *shared* Sun position so they
  isolate the force law; the propagated comparisons are not corrected.
* **Integrator.** The default here is the paper's scheme (fixed-step classical
  RK4, dt = 30 s, integrated in Cartesian coordinates) so the propagated
  comparison is apples to apples. Adaptive DP853 with Orekit's eclipse event
  detection is available via `integrator="dp853"` and is used for every
  production run, for the reason in `v7_eclipse_discontinuity.py`.
* **Frame.** EME2000 throughout, except where a rotating frame is deliberately
  introduced for the co-rotation experiment (ITRF, IERS 2010, simple EOP).

## Model mapping

| paper | Orekit |
|---|---|
| central gravity | `NumericalPropagator`'s built-in Newtonian attraction at the orbit's mu |
| J2, degree 2 order 0 | `J2OnlyPerturbation(mu, R_e, J2, EME2000)` — reproduces `gravity_j2_eci`'s perturbation to 2.8e-17 relative |
| inertially-frozen sail normal | `FrameAlignedProvider(Rotation(n_eci, PLUS_K), EME2000)` |
| one-sided flat plate for SRP | `FixedPanel(PLUS_K, A, doubleSided=False, C_D, liftRatio=0, absorption=0.3, reflection=0.7)` in a `BoxAndSolarArraySpacecraft` |
| two-sided flat plate for drag (`A|cos θ|`) | the same panel with `doubleSided=True`, in a **separate** `BoxAndSolarArraySpacecraft` |
| binary cylindrical umbra | `CylindricallyShadowedLightFluxModel(P_1AU·AU², Sun, R_e)` |
| eclipse disabled (Fig. 3 branch) | the same model with occulting radius 0 |
| US-1976 piecewise exponential, no co-rotation | `US1976Atmosphere` (this study) attached to EME2000 |
| cannonball drag (validation configuration) | `IsotropicDrag(A, C_D)` |

Two panels are needed because a single Orekit `Panel` carries one
`doubleSided` flag and is shared by the drag and radiation paths of
`BoxAndSolarArraySpacecraft`, whereas the paper's sail is one-sided for SRP and
two-sided for drag. This mirrors the STK arrangement described in the
manuscript (one +Z SRP plate, two opposed ±Z drag plates).

## Implementing Orekit interfaces from Python

`orekit_jpype` exposes the stock Orekit jars through JPype, so Java interfaces
are implemented with `@JImplements` / `@JOverride`. Two traps:

* **JPype proxies do not inherit Java `default` methods.** `Atmosphere` supplies
  a default `getVelocity`, but a Python proxy that omits it raises
  `NoSuchMethodError` the moment `DragForce` calls it. Every method of every
  implemented interface is therefore written out explicitly. In this case that
  was a benefit: it makes atmosphere co-rotation an explicit switch rather than
  an inherited assumption.
* **Field variants.** Orekit calls `getDensity(FieldAbsoluteDate, FieldVector3D,
  Frame)` when computing partial derivatives. JPype dispatches both overloads to
  the same Python method, so each one branches on whether its argument carries
  `getReal()`.

## Parallelism

`orekit_core/sweep.py` uses a `multiprocessing` pool with the **spawn** start
method. Forking a process that already holds a live JVM yields a child with a
half-initialised runtime that deadlocks on its first Java call; with spawn, each
worker imports the module fresh and boots its own JVM.

## Environment

Arch Linux, CPython 3.14.6, OpenJDK 21.0.11, `orekit_jpype` 13.1.7.0 (Orekit
13.1.7, Hipparchus 4.0.3), JPype 1.7.1, NumPy 2.5. Orekit data archive from
`gitlab.orekit.org/orekit/orekit-data`, branch `main`.
