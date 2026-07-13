"""
Flat-plate atmospheric drag force-model plugin for STK 13 HPOP.

Physics target (Sections/dynmodel.tex):
    a_drag = -0.5 * rho(h) * v² * C_D * (A * |cos(theta)| / m) * v̂

where:
- rho(h) is the US Standard Atmosphere 1976 piecewise-exponential density
- theta is the angle between sail normal and inertial velocity (atmosphere
  co-rotation neglected, per paper)
- |cos(theta)| factor is the projected-area correction; HPOP's built-in
  drag model is spherical (no projection), which over-applies drag when
  the sail is feathered.

Density-scaling factor multiplies rho(h) by a constant for the Fig. 7
sensitivity sweep (factors {0.25, 0.5, 1.0, 2.0, 4.0}).

Settings (PluginSettings):
    sail_area_m2           default 100.0
    mass_kg                default 10.0
    cd                     default 2.2
    sail_normal_eci_x/y/z  REQUIRED
    density_scaling_factor default 1.0
    sidecar_log_path       optional
"""

from __future__ import annotations

import math
from dataclasses import dataclass

R_EARTH_M = 6378136.3

# US Standard Atmosphere 1976, exponential model.
# Each row: (alt_floor_km, rho_at_floor_kg_m3, scale_height_km).
# Reused from C:\Users\Ian Poon\Documents\STK_ODTK 13\LEOsolarsailSIMS\Plugins\FlatPlateDrag.py
_ATM_TABLE = [
    (0,    1.225,     8.44),
    (25,   3.899e-2,  6.49),
    (50,   1.027e-3,  7.26),
    (75,   3.992e-5,  8.31),
    (100,  5.604e-7,  5.88),
    (150,  2.076e-9,  26.4),
    (200,  2.541e-10, 37.1),
    (250,  6.073e-11, 45.5),
    (300,  1.916e-11, 53.6),
    (400,  2.803e-12, 63.8),
    (500,  5.215e-13, 71.8),
    (600,  1.137e-13, 88.6),
    (700,  3.070e-14, 124.0),
    (800,  1.136e-14, 181.0),
    (900,  5.759e-15, 268.0),
    (1000, 3.561e-15, 408.0),
]


def density_us1976_kg_m3(altitude_m, scaling=1.0):
    """
    Piecewise-exponential US-1976 density [kg/m³] at given altitude [m],
    optionally multiplied by a constant `scaling`.

    Above the highest tabulated layer (1000 km), extrapolate using the
    last segment's scale height — never zero out, so the work integrals
    remain deterministic.
    """
    h_km = altitude_m / 1000.0
    if h_km <= 0:
        return _ATM_TABLE[0][1] * scaling

    for i in range(len(_ATM_TABLE) - 1):
        h0, rho0, H = _ATM_TABLE[i]
        h1 = _ATM_TABLE[i + 1][0]
        if h_km < h1:
            return rho0 * math.exp(-(h_km - h0) / H) * scaling

    h0, rho0, H = _ATM_TABLE[-1]
    return rho0 * math.exp(-(h_km - h0) / H) * scaling


def cos_theta_velocity(sail_normal_eci, v_eci):
    """cos(theta) where theta is angle between sail normal and inertial velocity."""
    vmag = math.sqrt(v_eci[0] ** 2 + v_eci[1] ** 2 + v_eci[2] ** 2)
    if vmag == 0:
        return 0.0
    return (
        sail_normal_eci[0] * v_eci[0]
        + sail_normal_eci[1] * v_eci[1]
        + sail_normal_eci[2] * v_eci[2]
    ) / vmag


def drag_acceleration_eci(
    r_sat_eci_m,
    v_sat_eci_m_s,
    sail_normal_eci,
    sail_area_m2,
    mass_kg,
    cd,
    density_scaling=1.0,
):
    """
    Flat-plate drag acceleration in ECI [m/s²].
    Returns (ax, ay, az). Atmosphere co-rotation neglected (paper convention).
    """
    r = math.sqrt(r_sat_eci_m[0] ** 2 + r_sat_eci_m[1] ** 2 + r_sat_eci_m[2] ** 2)
    altitude = r - R_EARTH_M
    rho = density_us1976_kg_m3(altitude, scaling=density_scaling)
    if rho <= 0.0:
        return (0.0, 0.0, 0.0)

    vmag = math.sqrt(
        v_sat_eci_m_s[0] ** 2 + v_sat_eci_m_s[1] ** 2 + v_sat_eci_m_s[2] ** 2
    )
    if vmag == 0:
        return (0.0, 0.0, 0.0)

    vhat = (v_sat_eci_m_s[0] / vmag, v_sat_eci_m_s[1] / vmag, v_sat_eci_m_s[2] / vmag)
    ct = abs(cos_theta_velocity(sail_normal_eci, v_sat_eci_m_s))
    A_proj = sail_area_m2 * ct

    a_mag = 0.5 * cd * rho * vmag * vmag * A_proj / mass_kg
    return (-a_mag * vhat[0], -a_mag * vhat[1], -a_mag * vhat[2])


# ============================================================================
# STK 13 HPOP plugin wrapper
# ============================================================================

@dataclass
class _Settings:
    sail_area_m2: float = 100.0
    mass_kg: float = 10.0
    cd: float = 2.2
    sail_normal_eci: tuple = (1.0, 0.0, 0.0)
    density_scaling_factor: float = 1.0
    sidecar_log_path: str = ""


def _read_settings(plugin_settings) -> _Settings:
    s = _Settings()

    def get(name, default=None):
        try:
            v = plugin_settings.GetProperty(name)
            return v if v not in (None, "") else default
        except Exception:
            return default

    s.sail_area_m2 = float(get("sail_area_m2", s.sail_area_m2))
    s.mass_kg = float(get("mass_kg", s.mass_kg))
    s.cd = float(get("cd", s.cd))
    nx = float(get("sail_normal_eci_x", s.sail_normal_eci[0]))
    ny = float(get("sail_normal_eci_y", s.sail_normal_eci[1]))
    nz = float(get("sail_normal_eci_z", s.sail_normal_eci[2]))
    norm = math.sqrt(nx * nx + ny * ny + nz * nz)
    if norm == 0:
        nx, ny, nz, norm = 1.0, 0.0, 0.0, 1.0
    s.sail_normal_eci = (nx / norm, ny / norm, nz / norm)
    s.density_scaling_factor = float(get("density_scaling_factor", s.density_scaling_factor))
    s.sidecar_log_path = str(get("sidecar_log_path", ""))
    return s


class FlatPlateDrag:
    """STK 13 HPOP Python force-model plugin for flat-plate drag."""

    def __init__(self):
        self._settings = _Settings()
        self._sidecar = None

    def Register(self, plugin_settings):
        self._settings = _read_settings(plugin_settings)
        if self._settings.sidecar_log_path:
            self._sidecar = open(self._settings.sidecar_log_path, "w", buffering=1)
            self._sidecar.write(
                "t_sec,altitude_km,rho_kg_m3,a_drag_x,a_drag_y,a_drag_z,cos_theta\n"
            )
        return 0

    def Initialize(self, scenario_root):
        return 0

    def Free(self):
        if self._sidecar:
            self._sidecar.close()
            self._sidecar = None
        return 0

    def Evaluate(self, time_sec, r_eci_m, v_eci_m_s):
        s = self._settings
        a = drag_acceleration_eci(
            r_eci_m,
            v_eci_m_s,
            s.sail_normal_eci,
            s.sail_area_m2,
            s.mass_kg,
            s.cd,
            density_scaling=s.density_scaling_factor,
        )
        if self._sidecar:
            r = math.sqrt(r_eci_m[0] ** 2 + r_eci_m[1] ** 2 + r_eci_m[2] ** 2)
            alt_km = (r - R_EARTH_M) / 1000.0
            rho = density_us1976_kg_m3(r - R_EARTH_M, scaling=s.density_scaling_factor)
            ct = cos_theta_velocity(s.sail_normal_eci, v_eci_m_s)
            self._sidecar.write(
                f"{time_sec:.6f},{alt_km:.4f},{rho:.6e},"
                f"{a[0]:.6e},{a[1]:.6e},{a[2]:.6e},{ct:.6f}\n"
            )
        return a


# ============================================================================
# Offline validation
# ============================================================================
if __name__ == "__main__":
    # Test 1: density at 700 km should match table value
    rho700 = density_us1976_kg_m3(700_000)
    print(f"[T1] rho(700 km)  = {rho700:.3e}  (table: 3.070e-14)")

    # Test 2: density scaling factor
    rho700_2x = density_us1976_kg_m3(700_000, scaling=2.0)
    print(f"[T2] rho×2 ratio  = {rho700_2x / rho700:.4f}  (expect 2.0)")

    # Test 3: density 50 km between table points decays exponentially
    rho725 = density_us1976_kg_m3(725_000)
    H_700_800 = 124.0  # scale height in [700,800) layer, km
    expected = 3.070e-14 * math.exp(-25.0 / H_700_800)
    print(f"[T3] rho(725 km)  = {rho725:.3e}  expected={expected:.3e}")

    # Test 4: drag at 700 km, sail normal aligned with velocity (max drag)
    r = (R_EARTH_M + 700_000.0, 0.0, 0.0)
    v = (0.0, 7500.0, 0.0)  # ~LEO velocity
    n_along_v = (0.0, 1.0, 0.0)
    a_max = drag_acceleration_eci(r, v, n_along_v, 100.0, 10.0, 2.2)
    a_max_mag = math.sqrt(sum(x * x for x in a_max))
    print(f"[T4] |a_drag| max-projection (n parallel v)   = {a_max_mag:.3e} m/s2")

    # Test 5: sail edge-on to velocity (n perpendicular to v): drag -> 0
    n_edge = (0.0, 0.0, 1.0)
    a_edge = drag_acceleration_eci(r, v, n_edge, 100.0, 10.0, 2.2)
    a_edge_mag = math.sqrt(sum(x * x for x in a_edge))
    print(f"[T5] |a_drag| edge-on (n perp v)              = {a_edge_mag:.3e} m/s2 (expect 0)")

    # Test 6: drag direction is -v̂
    n45 = (0.0, math.cos(math.radians(45)), math.sin(math.radians(45)))
    a45 = drag_acceleration_eci(r, v, n45, 100.0, 10.0, 2.2)
    # Direction should be (0,-1,0): pure -y
    print(f"[T6] drag direction sample = ({a45[0]:.3e}, {a45[1]:.3e}, {a45[2]:.3e})  "
          f"(expect ~(0, -X, 0))")

    # Test 7: 800 km vs 700 km magnitude ratio (rho ratio)
    a_800 = drag_acceleration_eci(
        (R_EARTH_M + 800_000.0, 0.0, 0.0), v, n_along_v, 100.0, 10.0, 2.2
    )
    a_800_mag = math.sqrt(sum(x * x for x in a_800))
    rho_ratio = density_us1976_kg_m3(800_000) / density_us1976_kg_m3(700_000)
    accel_ratio = a_800_mag / a_max_mag
    print(f"[T7] ratio drag(800)/drag(700) = {accel_ratio:.4f}  rho_ratio={rho_ratio:.4f} "
          "(should match)")
