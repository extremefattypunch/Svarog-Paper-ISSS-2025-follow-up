# STK Astrogator Object Model — verified API for the N-Plate build

Authoritative for this machine (STK 13, `agi.stk13`, Python 3.12), captured by the
`validation/probe_*.py` scripts. Raw probe dumps: `astrogator_forcemodels.md`,
`astrogator_propfuncs.md`, `astrogator_nplate.md`, `astrogator_addfuncs.md`.

## Session
- `STKEngine.StartApplication(noGraphics=True)` works headless; `root = app.NewObjectRoot()`.

## Propagator = Astrogator
- `sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorAstrogator)`
- `driver = sat.Propagator` → `AgVADriverMCS` (has `MainSequence`, `RunMCS()`, `RunMCS2()`).
- `mcs = driver.MainSequence` → 3 segments: `Initial State` (AgVAMCSInitialState),
  `Propagate` (AgVAMCSPropagate), `-` (AgVAMCSEnd).

## Initial State segment
- `seg.SetElementType(astro.AgEVAElementType.eVAElementTypeKeplerian)` (=1); default is Cartesian (0).
- `seg.OrbitEpoch = "1 Jan 2026 12:00:00.000"`; `seg.CoordSystemName = "CentralBody/Earth Inertial"`.
- `el = seg.Element` (AgVAElementKeplerian after switch) — set SMA/ecc/inc/argP/RAAN/TA.
- `seg.SpacecraftParameters` (AgVASpacecraftParameters): `DryMass`, `Cd`, `Cr`, `DragArea`,
  `RadiationPressureArea`, `SolarRadiationPressureArea`, `K1`, `K2`, `Ck`. (For N-plate the plate
  file carries area/reflectivity/Cd; **DryMass is still the mass the accel is divided by** → set 10 kg.)

## Propagate segment
- `seg.PropagatorName = "<owned propagator name>"` (references a component by name).
- `seg.StoppingConditions.Item("Duration").Properties.Trip = <seconds>` (14 d / 75 d).
- `seg.MaxPropagationTime`, `seg.OverrideMaxPropagationTime` — raise if a run exceeds the default cap.

## Numerical propagator (component directory)
- `cd = root.CurrentScenario.ComponentDirectory`
- `astro_cat = cd.GetComponents(2)`  # AgEComponent.eComponentAstrogator = 2 → AgComponentInfoCollection
- Folders: Calculation Objects, Central Bodies, Constraints, Custom Functions, Design Tools,
  Engine Models, Flight Dynamics Records, MCS Segments, Power Sources, **Propagator Functions**,
  **Propagators**, Stopping Conditions, Thruster Sets.
- `props = astro_cat.GetFolder("Propagators")` — items include **Earth Point Mass**, Earth J2,
  Earth Default High Fidelity v13, ...
- `props.DuplicateComponent("Earth Point Mass", "SailProp")`; `prop = props.Item("SailProp")`
  → `AgVANumericalPropagatorWrapper` (has `PropagatorFunctions`, `NumericalIntegrator`,
  `SetNumericalIntegrator`). `props.Remove("SailProp")` to delete.

## Force models: `prop.PropagatorFunctions` (AgVAPropagatorFunctionCollection)
- API: `Add(name)`, `Remove(name)`, `RemoveAll()`, `Item(i|name)`, `GetItemByName`, `Count`.
- `Add(name)` takes an exact template name from the "Propagator Functions" folder:
  - **Atmospheric Models**: `US Standard Atmosphere` (=1976), Exponential, Cira72, Jacchia*, MSIS*, ...
  - **Gravity Models**: `TwoBody Force`, `Gravitational Force`, `CR3BP Force`.
  - **SRP Models**: `NPlate SRP`, `Spherical SRP`, `TabAreaVector SRP`, ...
  - **Third Bodies**: Sun, Moon, ... (paper uses none).

### Gravity (`AgVAGravityFieldFunction`, name "Gravitational Force")
- `Degree=2`, `Order=0` (central + J2). `UseOceanTides=False`, `UseSecularVariations=False`,
  `IncludeTimeDependentSolidTides=False`. Remove any `TwoBody Force` so the central term isn't doubled.

### Drag (atmosphere force function, name "US Standard Atmosphere")
- `DragModelType = AgEVADragModelType.eVADragModelTypeNPlate` (=3). Others: Spherical=0, Plugin=1, VariableArea=2.
- `NPlateDefinitionFile = <path to .nplate DragCd file>`; `UseApproximateAltitude` (bool).
- **No co-rotation toggle exposed** → STK uses its default atmosphere-relative velocity. Documented
  difference vs the paper's inertial-velocity drag (minor at near-polar LEO).

### SRP (`AgVASRPNPlate`, name "NPlate SRP")
- `NPlateDefinitionFile = <path to .nplate SRP file>`.
- `ShadowModel = AgEVAShadowModel.eVAShadowModelCylindrical` (=0, primary), `eVAShadowModelDualCone` (=1),
  `eVAShadowModelNone` (=2, eclipse-off). `MeanFlux` (W/m² @1AU), `EclipsingBodies`, `SolarForceMethod`.

## N-Plate definition file format (.nplate) — from STKData/Flight_Dynamics/{SRP,Drag}_NPlate_Example.nplate
```
Version 1.0
Formulation SRP        # or: Formulation DragCd
Begin Plates
# [Name] [Group] [Type B|S|A] [Area m^2] [Unit Normal X Y Z] [Spec.Reflect.] [Diff.Reflect.]   (SRP)
# [Name] [Group] [Type B|S|A] [Area m^2] [Unit Normal X Y Z] [Drag Coeff.]                      (DragCd)
   PlusZ  Body  B  100.0  0.0 0.0 1.0  0.70  0.0
End Plates
```
- Type `B` = fixed in body frame (our inertially-fixed sail, via eProfileFixedInAxes attitude).
- **Sail SRP**: one `B` plate, area 100, normal +Z, Spec 0.70, Diff 0.0 → one-sided, C_r,eff = 1+ρ_s = 1.7.
- **Sail drag**: two `B` plates (+Z, −Z), area 100 each, Cd 2.2 → projected area A·|cosθ| (both faces).
- Fig 7 density sweep → scale plate Cd by factor (drag ∝ ρ·Cd). Fig 8 A/m → change plate Area.

## Attitude (unchanged; now load-bearing for N-plate)
- `sat.SetAttitudeType(eAttitudeStandard)`; `sat.Attitude.Basic.SetProfileType(eProfileFixedInAxes)`;
  `prof.ReferenceAxes = "CentralBody/Earth Inertial"`; `prof.Orientation.AssignQuaternion(qw,qx,qy,qz)`
  mapping body +Z → ECI sail normal (`core/attitude.normal_to_quaternion_eci`).

## Run + extract
- `driver.RunMCS()`.
- `sat.DataProviders.Item("Classical Elements").Group.Item("ICRF").ExecElements(startISO, stopISO, step, cols)`.
- **The MCS driver has no `EphemerisInterval`** → pass explicit ISO start/stop (epoch, epoch+duration).
