# Phase 1 Status — Where We Are and Decision Needed

Date: 2026-05-02

## What's done and verified offline

All physics modules and core utilities are written and pass offline unit tests. The runner can spin up STK Engine and create a satellite. The blocker is that **HPOP's Python plugin interface is more elaborate than the plan assumed** — see §"What we learned" below.

| Module | Status | Notes |
|---|---|---|
| `plugins/flatplate_srp_hpop.py` | physics validated offline | cos²α correct, umbra correct (cyl), edge-on/back-side give 0 |
| `plugins/flatplate_drag_hpop.py` | physics validated offline | US-1976 table matches at 700/725/800 km; cos(θ) projected area; density scaling exact |
| `core/orbit_init.py` | validated offline | JD, Sun RA, SSO inclination match paper; LTDN → RAAN within 0.5° of paper anchor |
| `core/attitude.py` | validated offline | pitch=0/24.8/90/180, roll=90 all match expected cos(α) |
| `core/scenario_builder.py` | structurally complete | wires up HPOP + plugin enums; **plugin call rejected by STK** (see below) |
| `core/data_extract.py` | written, untested in STK | DataProvider pattern from prior `export_stk_reports.py:18-51` |
| `core/work_diagnostics.py` | pure-Python, no STK dep | Δa_max, cumulative work integrals |
| `runners/run_fig9_long_horizon.py` | runs to plugin-attach step | crashes when setting `PluginName = "FlatPlateDrag"` |
| `post/plot_fig9_elements.py` | written, awaiting CSV | needs Fig 9 propagation to land first |

## What we learned about the STK 13 plugin API

1. STK has a single registered Python plugin shim per force-model type. The only legal `PluginName` value on this machine is **`"Python Drag Model"`** (and presumably `"Python SRP Model"` for SRP) — these are AGI's pre-registered Python loaders. They take a `Filename` setting pointing at our Python file.

2. The plugin file must define a class implementing **`IAgAsDragModelPlugin`** (drag) or **`IAgAsLightReflectionPlugin`** (SRP). These interfaces come from `AgAsHpopPlugin.dll` (shared between STK and ODTK). Required methods:
   - `Init(site)` → bool (must return True)
   - `Register(result)` → None (declare estimable parameters)
   - `PreCompute(result)`, `PreNextStep(result)`, `PostCompute(result)`
   - `Evaluate(resultEval)` → bool (per-step, this is where physics goes)
   - `Free()`

3. The `Evaluate` callback **does NOT receive position/velocity directly**. It receives a `resultEval` COM object whose methods include:
   - `PosVel(frame, x, y, z, vx, vy, vz)` — the spacecraft state
   - `SunPosition(eTrue, frame, x, y, z)` — Sun position
   - `IncidentDirection(frame, x, y, z)` — for drag, the relative wind
   - Properties: `Density`, `Altitude`, `TotalMass`, `Mu`, `Cr`, `SolarIntensity`, `LightSpeed`, ...
   - **For drag**: call `SetReflectance(frame, [rx,ry,rz])` where HPOP computes `F = 0.5·ρ·v²·reflectanceVec`. So `reflectanceVec = Cd·A·|cosθ|·(-v̂)` for our flat-plate.
   - **For SRP**: call `AddAcceleration(frame, ax, ay, az)` to add an arbitrary acceleration (this is what the shipped `TdrsSrpPlugin.wsc` does — it's a Perl plugin we found at `c:\Program Files\AGI\STK_ODTK 13\Data\Resources\common\plugins\TdrsSrpPlugin.wsc.txt`).

4. The plugin must be **registered as a Windows COM server** (ProgID + CLSID). The shipped Perl example is a `.wsc` (Windows Script Component) registered via `regsvr32`. For Python, this means `pywin32` COM-server registration.

5. The atmosphere density that HPOP feeds to the drag plugin via `result.Density` is **STK's** atmosphere model, not our US-1976. To get US-1976, we need a *separate* `IAgAsDensityModelPlugin` plugin OR override the density inside the drag plugin (but we'd need to bypass the `0.5·ρ·v²` factor STK applies).

## Where we are stuck

The current Python plugin classes I wrote (`FlatPlateSRP`, `FlatPlateDrag`) have:
- The wrong method signatures (took my own `(time, r, v)` tuple instead of the COM `resultEval` object).
- No COM-server registration (no ProgID, no `_reg_clsid_`, no pywin32 wrappers).
- A direct `(ax, ay, az)` return value instead of `SetReflectance` / `AddAcceleration`.

These are all fixable, but the work is non-trivial: it requires writing pywin32 COM-server boilerplate, registering it in the system COM registry, and iterating against STK's actual error reports — and STK plugin debugging is notoriously a "guess + run + read traceback" loop without good local tooling.

## Decision needed: which path forward?

Below are three concrete options. Each has different cost/fidelity trade-offs.

### Option 1 — Full COM plugin (what the plan originally said)

Rewrite `flatplate_srp_hpop.py` and `flatplate_drag_hpop.py` as proper pywin32 COM servers implementing `IAgAsLightReflectionPlugin` and `IAgAsDragModelPlugin`, plus a `IAgAsDensityModelPlugin` for US-1976 atmosphere. Register via `python flatplate_srp_hpop.py /regserver`. Fix the per-step call to use `result.AddAcceleration` (SRP) and `result.SetReflectance` (drag).

- **Pros**: highest fidelity, faithful to plan, STK is genuinely the propagator.
- **Cons**: 1–2 days of empirical STK plugin debugging with no easy local test loop. The previous Project Svarog attempt got stuck here and never recovered.
- **Risk**: high — the failure modes are obscure COM HRESULTs and hard-to-trace import errors at the STK shim boundary.

### Option 2 — STK as ephemeris provider, Python as integrator (Recommended)

Use STK only for: (a) Sun/Moon/Earth position queries, (b) frame transformations, and (c) initial-state setup. Write a small Python RK7/8 integrator (or use `scipy.integrate.solve_ivp`) that:

- Computes gravity (J2 or higher) with a simple Python implementation calibrated against STK two-body.
- Calls our existing flat-plate SRP and US-1976 drag functions from the validated plugins.
- Steps the orbit and writes the same Classical-Elements CSV the rest of the pipeline expects.

- **Pros**: works today; physics is exactly the paper's; one debug loop in pure Python; easy to add diagnostics; bypasses the entire STK plugin COM problem.
- **Cons**: STK is no longer the propagator — it becomes a (high-precision) ephemeris service. Defensible for a reproduction paper since the paper's force model is fully specified, but it does narrow what "STK reproduction" claims.
- **Risk**: low — pure Python with a well-defined physics spec.

### Option 3 — Approximation via stock spherical models with attitude-tracked Cr/A scaling

Disable the plugin path entirely. Use STK's stock spherical SRP and stock spherical drag, but at each propagation step **rebuild the satellite** with `C_r·cos²α(t)` and `A·|cosθ(t)|` scaled in. Effectively a piecewise-constant approximation of the flat-plate model.

- **Pros**: no plugin work; uses HPOP's own integrator.
- **Cons**: STK doesn't naturally let you change `C_r` mid-propagation (would need many short propagations stitched together). Quality loss is hard to bound. Would not reproduce the paper accurately.
- **Risk**: medium implementation, low fidelity.

## My recommendation

**Option 2** — Python integrator using STK as ephemeris service. Rationale:

- The paper's force model is fully specified (J₂, US-1976, flat-plate cos²α SRP, binary umbra) — there is no proprietary STK behaviour we're trying to capture.
- All the physics functions are already written and unit-tested.
- We can validate each piece (gravity-only against STK two-body; SRP against an analytic test) before adding complexity.
- Avoids the STK plugin debugging black hole that bit the prior Project Svarog attempt.
- We still report acceptance vs. the paper's published numbers — that's the real reproduction test, not "we used STK's button instead of scipy's".

If you want STK genuinely doing the propagation as a matter of methodological purity, Option 1 is the path — but I would budget 1–2 days for plugin debugging.

If you want to try plugin route first and fall back to Option 2 only if it bogs down, I can spend a fixed time-box on Option 1 (say, 4 hours of empirical iteration) and report back.

What would you like to do?
