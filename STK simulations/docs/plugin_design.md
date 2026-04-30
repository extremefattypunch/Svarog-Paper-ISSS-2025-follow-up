# HPOP Force-Model Plugin Design

This document specifies the two custom Python force-model plugins HPOP will load to reproduce the paper's flat-plate SRP and US-1976 exponential drag exactly. STK 13's HPOP supports Python force-model plugins via `eDragModelPlugin` and the analogous SRP plugin interface. The previous attempt at `C:\Users\Ian Poon\Documents\STK_ODTK 13\LEOsolarsailSIMS\setup_validation_pystk.py:111-148` set up the registration scaffolding but reverted to STK's spherical model — we will close that gap.

---

## 1. Why custom plugins are necessary

STK HPOP's built-in SRP and drag models are **spherical (cannon-ball)**: they apply force as if the satellite presents the same area to every direction. The paper uses a **flat plate**:

| Force | Paper model | STK default | Discrepancy |
|---|---|---|---|
| SRP | a_SRP ∝ A · C_r · cos²(α) | a_SRP ∝ A · C_r | Sign-selective work cycle disappears |
| Drag | a_drag ∝ A · |cos(θ)| | a_drag ∝ A | Drag overestimated when sail is feathered |
| Eclipse | Binary umbra | DualCone (penumbra) | Penumbra smears the on/off transition |

The cos²α factor is the **mechanism** of the entire paper — without it the orbit-averaged SRP work integral does not produce the asymmetric cycle that eclipse can selectively gate. Spherical SRP gives a constant outward push; the gain regime simply does not exist in that model. So the plugin is non-optional.

---

## 2. SRP plugin — `plugins/flatplate_srp_hpop.py`

### 2.1 Force law

Per `Sections/dynmodel.tex`:

```
a_SRP = (P_1AU · (1 AU / r_sun)² · A · C_r / m) · cos²(α) · r̂_{sun→sat}     (illuminated)
a_SRP = 0                                                                      (in umbra)
```

where:

- `P_1AU` = 4.5605 × 10⁻⁶ N/m² (TSI / c at 1 AU; we use the paper's value if specified, else this constant)
- `A` = sail area [m²], default 100, **runtime-overridable** for Fig. 8
- `C_r` = 1.7, **runtime-overridable**
- `m` = 10 kg, **runtime-overridable** for Fig. 8
- `α` = angle between sail normal `n̂` and Sun direction `r̂_{sun→sat}`
- `cos(α) = -n̂ · r̂_{sun→sat}` (negative because force is anti-Sun); **clamp to ≥0** (one-sided sail)

### 2.2 Plugin entry points (STK Python force-model interface)

The plugin is a Python class with the methods STK invokes. Naming and exact signatures match STK 13's plugin interface:

```python
class FlatPlateSRP:
    def Register(self, ICOM):
        """Called once when STK loads the plugin. Read settings."""
        # PluginSettings keys we expect:
        #   sail_area_m2, mass_kg, cr, sail_normal_eci_x, sail_normal_eci_y, sail_normal_eci_z
        #   disable_eclipse (bool, for Fig. 3 eclipse-off case)
        #   sidecar_log_path (str)

    def Initialize(self, scenario_root):
        """Cache central body, Sun ID, R_earth, AU constant."""

    def ComputeAcceleration(self, time_seconds, r_eci, v_eci):
        """Per-step force callback.
           Returns 3-tuple (ax, ay, az) in m/s² in ECI."""

    def Finalize(self):
        """Close sidecar log."""
```

### 2.3 Eclipse computation (inside plugin)

We **disable STK's SRP shadowing** (set `EnableShadowing = False`) and compute umbra in-plugin. Geometric umbra test (Earth as occulter, point Sun, ignoring Sun radius for simplicity since the paper uses a binary cone):

```python
def in_umbra(r_eci_sat, r_eci_sun_to_sat):
    # r_eci_sun_to_sat is sat - sun (vector from Sun to sat in ECI)
    # Earth is at origin in ECI
    # Project sat onto sun-to-sat line; if sat is behind Earth and within R_earth, eclipsed.
    sun_dir = -r_eci_sun_to_sat / |r_eci_sun_to_sat|       # unit vector from sat toward Sun
    along = r_eci_sat · sun_dir                            # projection along Sun line
    if along > 0:                                          # sat is on Sun side
        return False
    perp = |r_eci_sat - along * sun_dir|                   # perpendicular distance to Sun-Earth line
    return perp < R_EARTH
```

This is a **cylindrical umbra** approximation. If the paper's "conical umbra" is required, replace `R_EARTH` with the umbra radius at distance `|along|`:
`R_umbra(d) = R_earth − (R_sun − R_earth) · d / (AU − d)` (true cone). For LEO altitudes (<1000 km) the cylindrical approximation is within ~0.05° and matches "binary umbra" closely. Document the choice in `plugin_design.md` regression notes.

For Fig. 3 eclipse-off case, the plugin reads `disable_eclipse=True` from settings and unconditionally returns illuminated.

### 2.4 Sail normal vector

Since attitude is inertially fixed, the sail normal in ECI is constant for the entire propagation. The runner script computes it via `core/attitude.py` and passes it in via `PluginSettings.SetProperty("sail_normal_eci_x", ...)` etc. The plugin caches it on `Initialize`.

For future generality (spin-coupled or actively-steered cases), an alternative path is to read the satellite's body-axis quaternion via `Satellite.Attitude.Coord` each step — but for this paper, fixed inertial is sufficient and avoids per-step COM calls.

### 2.5 Sidecar log format

CSV per integration step, written to `sidecar_log_path`:

```
t_sec,r_x,r_y,r_z,v_x,v_y,v_z,a_srp_x,a_srp_y,a_srp_z,cos_alpha,eclipse_flag
```

Used by `post/plot_fig4_srp_power.py` and `post/plot_fig5_cum_work.py` and by `core/work_diagnostics.py`.

---

## 3. Drag plugin — `plugins/flatplate_drag_hpop.py`

### 3.1 Force law

Per `Sections/dynmodel.tex`:

```
a_drag = -0.5 · ρ(h) · v² · C_D · (A · |cos(θ)| / m) · v̂
```

where:

- `ρ(h)` = US Standard 1976 piecewise-exponential density at altitude `h = |r_eci| − R_earth`
- `v` = inertial velocity (atmosphere co-rotation neglected, per paper)
- `θ` = angle between sail normal `n̂` and `v̂`
- `cos(θ) = n̂ · v̂`, take `|cos(θ)|` because flat plate drags symmetrically
- `C_D` = 2.2, **runtime-overridable**
- `A`, `m` shared with SRP plugin

### 3.2 US-1976 atmosphere table

Reuse 16-segment table from `C:\Users\Ian Poon\Documents\STK_ODTK 13\LEOsolarsailSIMS\Plugins\FlatPlateDrag.py` (altitude 0–1000 km). For altitudes >1000 km extrapolate from the last segment's scale height. **Do not** silently zero out — return the extrapolated density even if extremely small, since the work-budget integrals must be deterministic.

### 3.3 Density scaling parameter (Fig. 7)

Plugin reads `density_scaling_factor` from `PluginSettings` (default 1.0). Multiplies the table-lookup density before applying. Allowed values for Fig. 7 sweep: {0.25, 0.5, 1.0, 2.0, 4.0}.

### 3.4 Plugin entry points

Same shape as SRP plugin (`Register`, `Initialize`, `ComputeAcceleration`, `Finalize`).

### 3.5 Sidecar log format

Append to the same per-run sidecar log (different columns) or write a sibling file:

```
t_sec,altitude_km,rho_kg_m3,a_drag_x,a_drag_y,a_drag_z,cos_theta
```

---

## 4. Plugin registration

### 4.1 STK plugin discovery

STK Engine looks for plugins in:

- `<STK install>\STKData\Plugins\` (system-wide)
- `<user>\AppData\Local\AGI\STK 13\Plugins\` (user)
- Path passed via `PluginSettings.SetProperty("Filename", <abs_path>)` (per-run)

We use the **per-run path** (most robust). Each runner script writes the plugin file to a temp directory (or references the project's `plugins/` dir directly) and passes the absolute path.

### 4.2 Force-model wiring (in `core/scenario_builder.py`)

Adapted from `setup_validation_pystk.py:111-148`. Key sequence:

```python
fm = sat.Propagator.ForceModel

# Disable STK's built-in SRP and drag, enable plugin variants
fm.SolarRadiationPressure.Use = False    # we'll add SRP via plugin
fm.Drag.Use = True
fm.Drag.SetDragModelType(o.AgEDragModel.eDragModelPlugin)
dplug = fm.Drag.DragModel
dplug.PluginName = "FlatPlateDrag"
dplug.PluginSettings.SetProperty("Filename", str(Path("plugins/flatplate_drag_hpop.py").resolve()))
dplug.PluginSettings.SetProperty("sail_area_m2", str(SAIL_AREA))
dplug.PluginSettings.SetProperty("mass_kg", str(MASS))
dplug.PluginSettings.SetProperty("cd", str(CD))
dplug.PluginSettings.SetProperty("density_scaling_factor", str(rho_factor))
dplug.PluginSettings.SetProperty("sail_normal_eci_x", str(nx))
dplug.PluginSettings.SetProperty("sail_normal_eci_y", str(ny))
dplug.PluginSettings.SetProperty("sail_normal_eci_z", str(nz))
dplug.PluginSettings.SetProperty("sidecar_log_path", str(Path(f"results/{tag}_drag.csv").resolve()))

# SRP plugin — STK 13's SRP plugin interface (verify exact enum name on first run)
fm.SolarRadiationPressure.Use = True
fm.SolarRadiationPressure.SetSRPModelType(o.AgESRPModel.eSRPModelPlugin)  # may differ slightly in STK 13 API
splug = fm.SolarRadiationPressure.SRPModel
splug.PluginName = "FlatPlateSRP"
splug.PluginSettings.SetProperty("Filename", str(Path("plugins/flatplate_srp_hpop.py").resolve()))
# ... same parameter pattern
fm.SolarRadiationPressure.EnableShadowing = False  # plugin computes umbra itself
```

If `eSRPModelPlugin` enum doesn't exist in this STK 13 build, fallback paths:

1. Use STK External Force Model (separate plugin category) for SRP.
2. Treat plugin as drag-only and add SRP via a wrapper external force.

Document the working enum name in `plugin_design.md` once empirically confirmed.

---

## 5. Validation

Each plugin ships with a `__main__` block that exercises the physics offline (no STK):

- **SRP plugin**: at α=0° (sail facing Sun), confirm |a_SRP| = (P · A · C_r / m) within machine precision; at α=60°, confirm |a_SRP| = baseline · cos²(60°) = baseline / 4.
- **Drag plugin**: at θ=0° (sail face into wind), confirm |a_drag| = baseline; at θ=90° (sail edge-on), confirm |a_drag| ≈ 0.

Then end-to-end:
- **Phase 1 gate**: gain anchor 75-day run reproduces a-peak ≈ 7098.211 km at day ~26.5 within ±1%. If not, the plugin is wrong and we debug before any sweep.

---

## 6. Known-unknowns to resolve in implementation

1. **Exact STK 13 SRP plugin enum**. The drag plugin path is documented (`eDragModelPlugin`); the SRP equivalent must be confirmed on the first plugin load.
2. **Whether per-step `PluginSettings` reads** are cheap enough to allow per-step density scaling, or whether we need to template-generate plugin files per scaling factor. Default plan: read once on `Initialize`.
3. **Plugin sidecar log throughput**. If 60 s step × 14 d × 225 cases = 4.5M rows × 13 columns is too much I/O, switch to binary `np.save`/parquet. Default plan: CSV; revisit if I/O dominates wall time.
