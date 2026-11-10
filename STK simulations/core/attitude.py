"""
Inertial sail-normal construction.

Convention (matches Sections/physicalmech.tex:53 — "beta is the constant pitch
angle measured from the Sun line"):

  At epoch t0, given:
    r_sun_eci  : Earth->Sun unit vector at t0 (ECI)
    h_eci      : orbit angular-momentum unit vector at t0 (ECI), from
                 (RAAN, inclination)
    pitch_deg  : angle between sail normal and the Sun line  [0, 180]
    roll_deg   : rotation of the sail normal about the Sun line, taking it
                 out of the (r_sun, h) meridional plane [Fig. 6 sweep]

  Construction:
    1. base_perp = unit(h - (h . r_sun) r_sun)       (component of h
       perpendicular to Sun line)
    2. n_pitched = cos(pitch) r_sun + sin(pitch) base_perp     (in plane)
    3. n_rolled  = Rodrigues rotation of n_pitched about r_sun by roll
    4. The resulting unit vector is then "frozen" in ECI for the entire
       propagation (paper attitude treatment is "inertially fixed").

This produces the right behaviour at the limit cases:
  - pitch=0:  n = r_sun  (sail facing Sun directly, max SRP)
  - pitch=90: n perpendicular to r_sun  (sail edge-on, no SRP)
  - pitch=180: n = -r_sun (sail back to Sun, no one-sided SRP)
  - roll=0:  n stays in the meridional plane
  - roll=90: n rotated 90 deg about Sun line, still at angle pitch from Sun
"""

from __future__ import annotations

import math


def _unit(v):
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if n == 0:
        return (1.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def orbit_normal_eci(raan_deg: float, inc_deg: float):
    """
    Orbit angular-momentum unit vector in ECI from (RAAN, inclination).

    For a Keplerian orbit with right ascension Ω and inclination i, the
    orbit normal in ECI is:
        h_hat = (sin(i) sin(Ω), -sin(i) cos(Ω), cos(i)).
    """
    O = math.radians(raan_deg)
    i = math.radians(inc_deg)
    return (math.sin(i) * math.sin(O), -math.sin(i) * math.cos(O), math.cos(i))


def rodrigues_rotate(v, axis_unit, angle_rad):
    """Rotate vector v about axis_unit (must be unit) by angle_rad (right-hand)."""
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    k = axis_unit
    kxv = _cross(k, v)
    kdv = _dot(k, v)
    return (
        v[0] * c + kxv[0] * s + k[0] * kdv * (1 - c),
        v[1] * c + kxv[1] * s + k[1] * kdv * (1 - c),
        v[2] * c + kxv[2] * s + k[2] * kdv * (1 - c),
    )


def inertial_sail_normal(
    r_sun_eci_unit,
    raan_deg: float,
    inc_deg: float,
    pitch_deg: float,
    roll_deg: float = 0.0,
):
    """
    Construct the inertially-fixed sail normal in ECI.

    Pitch tilts the normal away from the Sun line WITHIN THE ORBITAL PLANE, so
    the SRP force (which acts along the sail normal for a specular/N-plate sail)
    acquires an along-track component. This is the energy-pumping geometry of the
    paper's reduced model (a_SRP = a0 cos^2(beta) n_hat): without an in-plane
    tilt the SRP work over an orbit cancels (the eclipse sits on the work-cycle
    zero-crossing) and no gain is possible. Verified against per-orbit SRP-work
    diagnostics in validation/work_probe.py.

    base = unit(r_sun x h) is the in-plane direction perpendicular to the Sun
    line; +pitch tilts the normal toward it. `roll` then rotates the normal about
    the Sun line, taking it out of the orbital plane (Fig. 6 roll sweep).
    Returns a unit 3-tuple.
    """
    rs = _unit(r_sun_eci_unit)
    h = orbit_normal_eci(raan_deg, inc_deg)

    # In-plane direction perpendicular to the Sun line (lies in the orbit plane
    # because it is perpendicular to the orbit normal h).
    base = _unit(_cross(rs, h))
    # Degenerate case: orbit pole points at the Sun (never for a polar SSO).
    if base == (1.0, 0.0, 0.0) and abs(_dot(rs, (1.0, 0.0, 0.0))) > 0.99:
        tmp = (0.0, 1.0, 0.0)
        base = _unit((tmp[0] - _dot(tmp, rs) * rs[0],
                      tmp[1] - _dot(tmp, rs) * rs[1],
                      tmp[2] - _dot(tmp, rs) * rs[2]))

    p = math.radians(pitch_deg)
    n_pitched = (
        math.cos(p) * rs[0] + math.sin(p) * base[0],
        math.cos(p) * rs[1] + math.sin(p) * base[1],
        math.cos(p) * rs[2] + math.sin(p) * base[2],
    )

    if roll_deg != 0.0:
        return _unit(rodrigues_rotate(n_pitched, rs, math.radians(roll_deg)))
    return _unit(n_pitched)


def normal_to_quaternion_eci(n_eci_unit, body_axis=(0.0, 0.0, 1.0)):
    """
    Quaternion (w, x, y, z) that rotates `body_axis` (default body +Z)
    onto `n_eci_unit` in the inertial frame. Used to set
    eVeProfile.eProfileFixedInAxes orientation in STK.

    Smallest-arc rotation from body_axis to n_eci_unit:
        axis  = body_axis x n
        angle = acos(body_axis . n)
        q = (cos(angle/2), sin(angle/2) * axis_unit)
    """
    b = _unit(body_axis)
    n = _unit(n_eci_unit)
    d = _dot(b, n)
    # Numerical guard
    d = max(-1.0, min(1.0, d))

    if d > 0.9999999:
        return (1.0, 0.0, 0.0, 0.0)
    if d < -0.9999999:
        # 180-deg rotation: choose any axis perpendicular to b
        if abs(b[0]) < 0.9:
            perp = _unit((1.0 - b[0] * b[0], -b[0] * b[1], -b[0] * b[2]))
        else:
            perp = _unit((-b[1] * b[0], 1.0 - b[1] * b[1], -b[1] * b[2]))
        return (0.0, perp[0], perp[1], perp[2])

    axis = _unit(_cross(b, n))
    angle = math.acos(d)
    s = math.sin(angle / 2)
    return (math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s)


# ---------------------------------------------------------------------------
# Self-checks
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Minimal sanity checks; full validation requires the orbit_init module.
    rs = (1.0, 0.0, 0.0)               # Sun on +X
    raan = 90.0
    inc = 98.17
    h = orbit_normal_eci(raan, inc)
    print(f"orbit_normal(RAAN=90, i=98.17) = {h}  (expect roughly (sin i, 0, cos i))")

    n0 = inertial_sail_normal(rs, raan, inc, pitch_deg=0.0)
    print(f"pitch=0   n={n0}  (expect ~Sun direction (1,0,0))")
    n90 = inertial_sail_normal(rs, raan, inc, pitch_deg=90.0)
    cosa = _dot(n90, rs)
    print(f"pitch=90  n={n90}  cos(alpha)={cosa:.6f} (expect 0)")
    n180 = inertial_sail_normal(rs, raan, inc, pitch_deg=180.0)
    print(f"pitch=180 n={n180}  cos(alpha)={_dot(n180, rs):.6f} (expect -1)")

    n24p8 = inertial_sail_normal(rs, raan, inc, pitch_deg=24.8)
    print(f"pitch=24.8 n={n24p8}  cos(alpha)={_dot(n24p8, rs):.6f} "
          f"(expect cos(24.8) ~ {math.cos(math.radians(24.8)):.6f})")

    # Roll: at pitch=24.8 and roll=90, normal should still be at 24.8 from Sun
    n_rolled = inertial_sail_normal(rs, raan, inc, pitch_deg=24.8, roll_deg=90.0)
    cosa_rolled = _dot(n_rolled, rs)
    print(f"pitch=24.8 roll=90, cos(alpha)={cosa_rolled:.6f} (should still be {math.cos(math.radians(24.8)):.6f})")

    # Quaternion that maps body +Z to n
    q = normal_to_quaternion_eci(n24p8)
    print(f"q for pitch=24.8 normal: (w,x,y,z)={q}")
