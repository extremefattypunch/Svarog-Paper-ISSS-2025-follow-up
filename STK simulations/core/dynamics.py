"""
Equations of motion for the paper's force model, reusing the validated SRP
and drag plugin physics.

Force model (paper, Sections/dynmodel.tex):
- Central gravity + J2 only (degree 2, order 0)
- Flat-plate cos^2(alpha) SRP with binary cylindrical umbra (one-sided sail)
- US Standard Atmosphere 1976 piecewise-exponential drag with cos(theta)
  projected area; atmosphere co-rotation neglected
- No third-body, no higher-order gravity, no Sun/Moon perturbations.

State vector: y = [rx, ry, rz, vx, vy, vz]   (m, m/s) in ECI (Earth-centered
inertial, J2000 in practice — close enough to ICRF at LEO scales for the
paper's physics).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Tuple

# Reuse the validated plugin physics
from plugins.flatplate_srp_hpop import (
    R_EARTH_M as R_EARTH_M_SRP,
    srp_acceleration_eci,
)
from plugins.flatplate_drag_hpop import drag_acceleration_eci

# ---- Earth constants (matching STK / EGM96) ---------------------------------
MU_EARTH_M3_S2 = 3.986004418e14
R_EARTH_M = 6_378_136.3
J2 = 1.082_626_173e-3


# ---- Gravity --------------------------------------------------------------
def gravity_j2_eci(r_eci_m) -> Tuple[float, float, float]:
    """
    Central + J2 gravity acceleration in ECI [m/s^2].

    a = -mu/r^3 r  +  (3/2) mu J2 (R_e^2 / r^5) [
        x (5 z^2 / r^2 - 1),
        y (5 z^2 / r^2 - 1),
        z (5 z^2 / r^2 - 3) ]
    """
    x, y, z = r_eci_m
    r2 = x * x + y * y + z * z
    r = math.sqrt(r2)
    r3 = r2 * r
    r5 = r2 * r3
    mu_over_r3 = MU_EARTH_M3_S2 / r3
    ax_c = -mu_over_r3 * x
    ay_c = -mu_over_r3 * y
    az_c = -mu_over_r3 * z

    coef = 1.5 * MU_EARTH_M3_S2 * J2 * (R_EARTH_M ** 2) / r5
    z2_over_r2 = z * z / r2
    factor_xy = 5.0 * z2_over_r2 - 1.0
    factor_z = 5.0 * z2_over_r2 - 3.0
    ax_j2 = coef * x * factor_xy
    ay_j2 = coef * y * factor_xy
    az_j2 = coef * z * factor_z

    return (ax_c + ax_j2, ay_c + ay_j2, az_c + az_j2)


# ---- Configuration ---------------------------------------------------------
@dataclass
class SailConfig:
    sail_area_m2: float = 100.0
    mass_kg: float = 10.0
    cr: float = 1.7
    cd: float = 2.2
    density_scaling: float = 1.0           # Fig. 7 sweep variable
    disable_eclipse: bool = False          # Fig. 3 eclipse-off branch
    sail_normal_eci: Tuple[float, float, float] = (1.0, 0.0, 0.0)


@dataclass
class ForceLogger:
    """Optional per-step diagnostic log. Append-only ring of dicts."""
    enabled: bool = False
    records: list = field(default_factory=list)

    def log(self, t, r, v, a_g, a_srp, a_drag, eclipse_flag, cos_alpha):
        if not self.enabled:
            return
        self.records.append({
            "t": t,
            "r": tuple(r), "v": tuple(v),
            "a_g": tuple(a_g), "a_srp": tuple(a_srp), "a_drag": tuple(a_drag),
            "eclipse_flag": eclipse_flag, "cos_alpha": cos_alpha,
        })


# ---- The equation of motion ------------------------------------------------
def make_rhs(sail: SailConfig, sun_eci_at: Callable[[float], Tuple[float, float, float]],
             logger: ForceLogger = None):
    """
    Returns f(t, y) -> dy/dt for use with scipy.integrate.solve_ivp.

    `sun_eci_at(t)` returns Sun position in ECI [m] at time `t` (seconds since
    scenario epoch). Use core.sun_ephemeris.SunEphemeris for STK-backed Sun.
    """
    def rhs(t: float, y):
        r = (y[0], y[1], y[2])
        v = (y[3], y[4], y[5])

        a_g = gravity_j2_eci(r)
        r_sun = sun_eci_at(t)

        a_srp = srp_acceleration_eci(
            r, r_sun, sail.sail_normal_eci,
            sail.sail_area_m2, sail.mass_kg, sail.cr,
            disable_eclipse=sail.disable_eclipse,
        )
        a_drag = drag_acceleration_eci(
            r, v, sail.sail_normal_eci,
            sail.sail_area_m2, sail.mass_kg, sail.cd,
            density_scaling=sail.density_scaling,
        )

        ax = a_g[0] + a_srp[0] + a_drag[0]
        ay = a_g[1] + a_srp[1] + a_drag[1]
        az = a_g[2] + a_srp[2] + a_drag[2]

        if logger is not None and logger.enabled:
            from plugins.flatplate_srp_hpop import cos_alpha as _cos_alpha, in_umbra_cylindrical
            dx, dy, dz = r[0] - r_sun[0], r[1] - r_sun[1], r[2] - r_sun[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            rhat = (dx / dist, dy / dist, dz / dist)
            ca = _cos_alpha(sail.sail_normal_eci, rhat)
            ecl = (0 if sail.disable_eclipse else int(in_umbra_cylindrical(r, r_sun)))
            logger.log(t, r, v, a_g, a_srp, a_drag, ecl, ca)

        return [v[0], v[1], v[2], ax, ay, az]
    return rhs


# ---- Self-checks -----------------------------------------------------------
if __name__ == "__main__":
    # Test gravity at 700 km altitude on +X axis: should point in -X with
    # magnitude ~ mu / r^2
    r0 = (R_EARTH_M + 700_000.0, 0.0, 0.0)
    a = gravity_j2_eci(r0)
    a_mag = math.sqrt(sum(x * x for x in a))
    expected_central = MU_EARTH_M3_S2 / (r0[0] ** 2)
    print(f"[T1] gravity at 700km +X:  a={a}")
    print(f"     |a|={a_mag:.6e}  central={expected_central:.6e}")
    # J2 contribution at equatorial point with z=0:
    # az_j2 = (3/2) mu J2 (R_e^2 / r^5) * z * (5 z^2/r^2 - 3) = 0
    # ax_j2 = (3/2) mu J2 (R_e^2 / r^5) * x * (5*0 - 1) = -(3/2) mu J2 R_e^2 / r^4
    j2_x = -1.5 * MU_EARTH_M3_S2 * J2 * (R_EARTH_M ** 2) / (r0[0] ** 4)
    print(f"     ax J2 (analytic): {j2_x:.6e}    diff: {a[0] - (-expected_central) - j2_x:.3e}")

    # Test polar point: J2 should pull stronger toward Earth center
    r_pole = (0.0, 0.0, R_EARTH_M + 700_000.0)
    a_pole = gravity_j2_eci(r_pole)
    print(f"[T2] gravity at 700km +Z (pole): a={a_pole}")
    a_pole_mag = math.sqrt(sum(x * x for x in a_pole))
    print(f"     |a|={a_pole_mag:.6e} (central={expected_central:.6e})")
