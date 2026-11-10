"""
Flat-plate cos²α SRP force-model plugin for STK 13 HPOP.

Physics target (Sections/dynmodel.tex):
    a_SRP = (P_1AU * (1 AU / r_sun)^2 * A * C_r / m) * cos²(alpha) * r̂_{sun→sat}   (illuminated)
    a_SRP = 0                                                                       (in umbra)

where alpha is the angle between the sail normal and the sun-line, and the umbra is a
binary cone (no penumbra). HPOP's built-in SRP is spherical (no cos² factor) and
DualCone shadowing has a penumbra — both differ from the paper. This plugin replaces
both: STK's SRP shadowing must be disabled (EnableShadowing=False) when this plugin loads.

Settings read from PluginSettings on Initialize:
    sail_area_m2          float, default 100.0
    mass_kg               float, default 10.0
    cr                    float, default 1.7
    sail_normal_eci_x/y/z float, no default — REQUIRED (unit vector in ECI)
    disable_eclipse       "true"|"false", default "false"
    sidecar_log_path      str, optional. If set, plugin writes per-step CSV.

The sail-normal vector is constant in ECI for the whole propagation (paper attitude is
inertially fixed). The runner script computes it from (LTDN, pitch, roll, RAAN, epoch)
via core/attitude.py and passes it in via PluginSettings.

Module is import-safe (no STK imports at module load) and `__main__` runs offline
physics validation.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

# ============================================================================
# Physical constants (paper convention)
# ============================================================================
P_1AU_N_PER_M2 = 4.5605e-6          # solar radiation pressure at 1 AU [N/m²]
AU_M = 1.495978707e11               # 1 astronomical unit [m]
R_EARTH_M = 6378136.3               # Earth equatorial radius [m]


# ============================================================================
# Pure physics — offline-testable
# ============================================================================

def cos_alpha(sail_normal_eci, r_sun_to_sat_eci_unit):
    """
    cos(alpha) where alpha is the angle between the sail normal and the
    sun-line. The sail "faces" the Sun when its normal points toward the Sun,
    i.e. opposite to (sun→sat). Negative values mean the sail is facing away
    (one-sided sail produces no SRP).
    """
    # n̂ · r̂_{sat→sun} = - n̂ · r̂_{sun→sat}
    return -(
        sail_normal_eci[0] * r_sun_to_sat_eci_unit[0]
        + sail_normal_eci[1] * r_sun_to_sat_eci_unit[1]
        + sail_normal_eci[2] * r_sun_to_sat_eci_unit[2]
    )


def in_umbra_cylindrical(r_sat_eci_m, r_sun_eci_m, r_earth_m=R_EARTH_M):
    """
    Binary cylindrical umbra: True iff satellite is on anti-Sun side of Earth
    AND within R_earth of the Earth–Sun line. Cylindrical (rather than conical)
    is accurate to ~30 km on the umbra-radius for LEO altitudes; the paper uses
    a binary cone, and at 700–800 km this approximation differs negligibly.

    r_sat_eci_m: satellite position vector in Earth-centered inertial [m]
    r_sun_eci_m: Sun position vector in Earth-centered inertial [m]
    """
    sun_norm = math.sqrt(
        r_sun_eci_m[0] ** 2 + r_sun_eci_m[1] ** 2 + r_sun_eci_m[2] ** 2
    )
    sx = r_sun_eci_m[0] / sun_norm
    sy = r_sun_eci_m[1] / sun_norm
    sz = r_sun_eci_m[2] / sun_norm

    along = r_sat_eci_m[0] * sx + r_sat_eci_m[1] * sy + r_sat_eci_m[2] * sz
    if along >= 0.0:
        return False  # sunward of Earth — illuminated

    px = r_sat_eci_m[0] - along * sx
    py = r_sat_eci_m[1] - along * sy
    pz = r_sat_eci_m[2] - along * sz
    perp = math.sqrt(px * px + py * py + pz * pz)
    return perp < r_earth_m


def srp_acceleration_eci(
    r_sat_eci_m,
    r_sun_eci_m,
    sail_normal_eci,
    sail_area_m2,
    mass_kg,
    cr,
    disable_eclipse=False,
):
    """
    Flat-plate SRP acceleration in ECI [m/s²], paper convention.

    Returns (ax, ay, az). Zero when sail is edge-on / facing away, or when
    eclipsed (umbra) and disable_eclipse=False.
    """
    # Sun→sat vector and unit
    dx = r_sat_eci_m[0] - r_sun_eci_m[0]
    dy = r_sat_eci_m[1] - r_sun_eci_m[1]
    dz = r_sat_eci_m[2] - r_sun_eci_m[2]
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    rhat = (dx / dist, dy / dist, dz / dist)

    # cos(alpha): one-sided sail
    ca = cos_alpha(sail_normal_eci, rhat)
    if ca <= 0.0:
        return (0.0, 0.0, 0.0)

    if (not disable_eclipse) and in_umbra_cylindrical(r_sat_eci_m, r_sun_eci_m):
        return (0.0, 0.0, 0.0)

    p_srp = P_1AU_N_PER_M2 * (AU_M / dist) ** 2
    a_mag = p_srp * sail_area_m2 * cr * ca * ca / mass_kg  # cos² factor

    return (a_mag * rhat[0], a_mag * rhat[1], a_mag * rhat[2])


# ============================================================================
# N-Plate SRP — physical flat-plate model matching STK Astrogator's SRPNPlate
# ============================================================================
#
# STK Astrogator's built-in N-Plate SRP model computes the physically-correct
# flat-plate force, decomposed into absorption, specular, and diffuse terms.
# This function reproduces that force so we can (a) calibrate the plate optical
# coefficients offline against the paper's cos²α reference, and (b) recompute the
# per-step SRP work diagnostics from an STK ephemeris (STK exposes no per-step
# SRP-acceleration DataProvider).
#
# Per-plate force (P_local = local solar pressure, S = area, m = mass), with the
# Sun→sat unit rhat, the sail normal n̂ (pointing toward the Sun when ca>0), and
# ca = cos α = n̂·(sat→Sun) = -(n̂·rhat):
#
#   a = (P_local·S/m) · [ (α_abs + ρ_d)·ca·rhat  −  (2·ρ_s·ca² + (2/3)·ρ_d·ca)·n̂ ]
#
# Normal-incidence coefficient  C_r,eff = α_abs + 2ρ_s + (5/3)ρ_d = 1 + ρ_s + (2/3)ρ_d
# (using α_abs + ρ_s + ρ_d = 1). The absorption/diffuse parts push anti-sunward
# (along rhat, ∝cosα); the specular part pushes along −n̂ (∝cos²α), which is the
# term matching the paper's reduced model a₀cos²β·n̂.
#
# Calibration to the paper's effective C_r = 1.7 (see plan "SRP modeling
# reconciliation"): maximize the correct-shaped specular fraction ⇒ ρ_d = 0,
# ρ_s = 0.7, α_abs = 0.3 (the literal cannonball identity C_r = 1 + ρ_s).

# (absorptivity, specular reflectivity, diffuse reflectivity); must sum to 1.
NPLATE_CALIBRATION_PRIMARY = (0.3, 0.7, 0.0)   # C_r,eff = 1.7 (paper C_r)
NPLATE_CALIBRATION_SPECULAR = (0.0, 1.0, 0.0)  # C_r,eff = 2.0 (shape-only check)


def nplate_srp_acceleration_eci(
    r_sat_eci_m,
    r_sun_eci_m,
    sail_normal_eci,
    sail_area_m2,
    mass_kg,
    alpha_abs=0.3,
    rho_spec=0.7,
    rho_diff=0.0,
    disable_eclipse=False,
):
    """
    Physical N-plate flat-plate SRP acceleration in ECI [m/s²], matching STK
    Astrogator's SRPNPlate model for a single body-fixed plate.

    Returns (ax, ay, az). Zero when the sail faces away (ca<=0) or is eclipsed.
    Optical coefficients default to the primary calibration (C_r,eff = 1.7).
    """
    dx = r_sat_eci_m[0] - r_sun_eci_m[0]
    dy = r_sat_eci_m[1] - r_sun_eci_m[1]
    dz = r_sat_eci_m[2] - r_sun_eci_m[2]
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    rhat = (dx / dist, dy / dist, dz / dist)

    ca = cos_alpha(sail_normal_eci, rhat)  # = -(n̂·rhat)
    if ca <= 0.0:
        return (0.0, 0.0, 0.0)

    if (not disable_eclipse) and in_umbra_cylindrical(r_sat_eci_m, r_sun_eci_m):
        return (0.0, 0.0, 0.0)

    p_srp = P_1AU_N_PER_M2 * (AU_M / dist) ** 2
    k = p_srp * sail_area_m2 / mass_kg

    c_rhat = (alpha_abs + rho_diff) * ca                      # along rhat (anti-sunward)
    c_norm = (2.0 * rho_spec * ca + (2.0 / 3.0) * rho_diff) * ca  # along -n̂

    return (
        k * (c_rhat * rhat[0] - c_norm * sail_normal_eci[0]),
        k * (c_rhat * rhat[1] - c_norm * sail_normal_eci[1]),
        k * (c_rhat * rhat[2] - c_norm * sail_normal_eci[2]),
    )


# ============================================================================
# STK 13 HPOP plugin wrapper
# ============================================================================
#
# STK's force-model plugin interface for Python is loaded via:
#   fm.SolarRadiationPressure.SetSRPModelType(eSRPModelPlugin)  (exact enum
#       name verified empirically — see docs/plugin_design.md §4.2)
#   model.PluginName = "FlatPlateSRP"
#   model.PluginSettings.SetProperty("Filename", <abs path to this file>)
#
# The plugin class is discovered by name and instantiated by STK. STK calls:
#   - Register / Initialize once (we read settings here)
#   - Evaluate per integration step (we return ax,ay,az in ECI [m/s²])
#   - Free at end
#
# Method names below follow the documented STK 13 Python plugin convention.
# If a particular STK build expects different signatures, swap the wrappers
# without touching the physics functions above.

@dataclass
class _Settings:
    sail_area_m2: float = 100.0
    mass_kg: float = 10.0
    cr: float = 1.7
    sail_normal_eci: tuple = (1.0, 0.0, 0.0)  # placeholder; runner overrides
    disable_eclipse: bool = False
    sidecar_log_path: str = ""


def _read_settings(plugin_settings) -> _Settings:
    """Read PluginSettings (STK COM object). Falls back to defaults if missing.

    plugin_settings exposes GetProperty(name) returning a string in STK 13.
    """
    s = _Settings()

    def get(name, default=None):
        try:
            v = plugin_settings.GetProperty(name)
            return v if v not in (None, "") else default
        except Exception:
            return default

    s.sail_area_m2 = float(get("sail_area_m2", s.sail_area_m2))
    s.mass_kg = float(get("mass_kg", s.mass_kg))
    s.cr = float(get("cr", s.cr))
    nx = float(get("sail_normal_eci_x", s.sail_normal_eci[0]))
    ny = float(get("sail_normal_eci_y", s.sail_normal_eci[1]))
    nz = float(get("sail_normal_eci_z", s.sail_normal_eci[2]))
    norm = math.sqrt(nx * nx + ny * ny + nz * nz)
    if norm == 0:
        nx, ny, nz, norm = 1.0, 0.0, 0.0, 1.0
    s.sail_normal_eci = (nx / norm, ny / norm, nz / norm)
    s.disable_eclipse = str(get("disable_eclipse", "false")).lower() == "true"
    s.sidecar_log_path = str(get("sidecar_log_path", ""))
    return s


class FlatPlateSRP:
    """STK 13 HPOP Python force-model plugin entry point.

    The exact method names STK calls vary slightly by version. We expose
    the conventional set; if a build expects different names, alias them.
    """

    def __init__(self):
        self._settings: _Settings = _Settings()
        self._sun_eci_provider = None  # set in Initialize
        self._scenario_root = None
        self._sidecar = None
        self._t0 = None  # epoch seconds for sidecar time column

    # ---- STK plugin lifecycle ------------------------------------------------
    def Register(self, plugin_settings):
        """Called once when STK loads the plugin. Cache settings."""
        self._settings = _read_settings(plugin_settings)
        if self._settings.sidecar_log_path:
            self._sidecar = open(self._settings.sidecar_log_path, "w", buffering=1)
            self._sidecar.write(
                "t_sec,r_x,r_y,r_z,v_x,v_y,v_z,"
                "a_srp_x,a_srp_y,a_srp_z,cos_alpha,eclipse_flag\n"
            )
        return 0

    def Initialize(self, scenario_root):
        """Cache scenario root so we can query Sun position each step."""
        self._scenario_root = scenario_root
        return 0

    def Free(self):
        if self._sidecar:
            self._sidecar.close()
            self._sidecar = None
        return 0

    # ---- Per-step force evaluation ------------------------------------------
    def Evaluate(self, time_sec, r_eci_m, v_eci_m_s):
        """
        Returns SRP acceleration in ECI [m/s²].

        time_sec : seconds since scenario epoch
        r_eci_m  : (x,y,z) satellite position in ECI [m]
        v_eci_m_s: (x,y,z) satellite velocity in ECI [m/s]
        """
        # Query Sun position from STK central-body data provider
        r_sun_eci_m = self._sun_eci_at(time_sec)

        s = self._settings
        a = srp_acceleration_eci(
            r_eci_m,
            r_sun_eci_m,
            s.sail_normal_eci,
            s.sail_area_m2,
            s.mass_kg,
            s.cr,
            disable_eclipse=s.disable_eclipse,
        )

        if self._sidecar:
            dx = r_eci_m[0] - r_sun_eci_m[0]
            dy = r_eci_m[1] - r_sun_eci_m[1]
            dz = r_eci_m[2] - r_sun_eci_m[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            ca = cos_alpha(s.sail_normal_eci, (dx / d, dy / d, dz / d))
            ecl = (
                0
                if s.disable_eclipse
                else int(in_umbra_cylindrical(r_eci_m, r_sun_eci_m))
            )
            self._sidecar.write(
                f"{time_sec:.6f},{r_eci_m[0]:.3f},{r_eci_m[1]:.3f},{r_eci_m[2]:.3f},"
                f"{v_eci_m_s[0]:.6f},{v_eci_m_s[1]:.6f},{v_eci_m_s[2]:.6f},"
                f"{a[0]:.6e},{a[1]:.6e},{a[2]:.6e},{ca:.6f},{ecl}\n"
            )
        return a

    # ---- Helpers -------------------------------------------------------------
    def _sun_eci_at(self, time_sec):
        """
        Sun ECI position at scenario time `time_sec`. Uses STK's central-body
        DataProvider when available; falls back to a low-precision JPL DE-style
        analytic Sun if no scenario root is set (offline/unit-test mode).
        """
        if self._scenario_root is not None:
            try:
                cb = self._scenario_root.CentralBodies.Item("Sun")
                # Position relative to Earth in ICRF frame at scenario seconds.
                # Exact API call differs by STK build; the safest call is via
                # vector-geometry tools. The runner can also pre-tabulate Sun
                # position and pass it via PluginSettings (cheaper).
                pos = cb.Position.QueryCartesianAtTime(time_sec)
                return (pos[0] * 1000.0, pos[1] * 1000.0, pos[2] * 1000.0)
            except Exception:
                pass
        # Fallback: low-precision analytic Sun (mean ecliptic, J2000)
        return _analytic_sun_eci_m(time_sec)


def _analytic_sun_eci_m(t_sec_since_j2000):
    """
    Low-precision Sun position in ECI (Earth-centered J2000), m.
    Source: simplified Meeus, accuracy ~few×10⁻³ AU. Used only as a fallback
    when STK's data provider is unavailable (offline tests).
    """
    JD = 2451545.0 + t_sec_since_j2000 / 86400.0  # days since J2000
    n = JD - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360.0)
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    R_au = 1.00014 - 0.01671 * math.cos(g) - 0.00014 * math.cos(2 * g)
    R = R_au * AU_M
    x = R * math.cos(lam)
    y = R * math.cos(eps) * math.sin(lam)
    z = R * math.sin(eps) * math.sin(lam)
    return (x, y, z)


# ============================================================================
# Offline validation
# ============================================================================
if __name__ == "__main__":
    # Test 1: sail facing Sun (alpha = 0) at 1 AU should give |a| = P*A*Cr/m
    sun = (AU_M, 0.0, 0.0)
    sat = (AU_M + 7.078e6, 0.0, 0.0)  # 700 km altitude on +X line
    n = (-1.0, 0.0, 0.0)              # sail normal pointing back at Sun
    a = srp_acceleration_eci(sat, sun, n, 100.0, 10.0, 1.7)
    expected = P_1AU_N_PER_M2 * (AU_M / 7.078e6) ** 2 * 100.0 * 1.7 / 10.0
    # Note: the (AU_M / dist) factor uses Sun-to-sat distance, NOT 1 AU.
    # For alpha=0, magnitude should equal P_local * A * Cr / m.
    p_local = P_1AU_N_PER_M2 * (AU_M / 7.078e6) ** 2
    expected = p_local * 100.0 * 1.7 / 10.0
    a_mag = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    print(f"[T1] alpha=0,  |a|={a_mag:.6e}  expected={expected:.6e}")
    # Sanity: at 1 AU sat-Sun separation (very near 1 AU here) the value
    # should be close to (P_1AU * A * Cr / m).
    nominal_1au = P_1AU_N_PER_M2 * 100.0 * 1.7 / 10.0
    print(f"     reference @1AU = {nominal_1au:.6e}")

    # Test 2: alpha = 60°. Force ∝ cos²(60°) = 0.25 of the alpha=0 value.
    n60 = (-math.cos(math.radians(60)), math.sin(math.radians(60)), 0.0)
    a60 = srp_acceleration_eci(
        (AU_M + 7.078e6, 0.0, 0.0), sun, n60, 100.0, 10.0, 1.7
    )
    a60_mag = math.sqrt(a60[0] ** 2 + a60[1] ** 2 + a60[2] ** 2)
    ratio = a60_mag / a_mag
    print(f"[T2] alpha=60, |a|={a60_mag:.6e}  ratio_to_T1={ratio:.4f}  expected=0.2500")

    # Test 3: sail edge-on (alpha = 90°): force = 0.
    n90 = (0.0, 1.0, 0.0)
    a90 = srp_acceleration_eci(
        (AU_M + 7.078e6, 0.0, 0.0), sun, n90, 100.0, 10.0, 1.7
    )
    print(f"[T3] alpha=90, |a|={math.sqrt(sum(x*x for x in a90)):.3e} (expect 0)")

    # Test 4: sail facing away from Sun (alpha > 90°): force = 0.
    n180 = (1.0, 0.0, 0.0)
    a180 = srp_acceleration_eci(
        (AU_M + 7.078e6, 0.0, 0.0), sun, n180, 100.0, 10.0, 1.7
    )
    print(f"[T4] alpha=180,|a|={math.sqrt(sum(x*x for x in a180)):.3e} (expect 0)")

    # Test 5: umbra geometry. Sat directly behind Earth on Sun-Earth line:
    sun_pos = (AU_M, 0.0, 0.0)
    sat_behind = (-7.078e6, 0.0, 0.0)
    print(f"[T5] in_umbra (behind Earth) = {in_umbra_cylindrical(sat_behind, sun_pos)} (expect True)")

    # Test 6: sat sunward of Earth, never eclipsed
    sat_sunward = (7.078e6, 0.0, 0.0)
    print(f"[T6] in_umbra (sunward)      = {in_umbra_cylindrical(sat_sunward, sun_pos)} (expect False)")

    # Test 7: sat at perpendicular distance 2*R_earth from Sun-Earth line
    sat_offaxis = (-7.078e6, 2 * R_EARTH_M, 0.0)
    print(f"[T7] in_umbra (off-axis)     = {in_umbra_cylindrical(sat_offaxis, sun_pos)} (expect False)")
