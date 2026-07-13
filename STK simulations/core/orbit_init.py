"""
Initial orbital state utilities.

- SSO inclination per altitude (paper Table sso_inclinations)
- LTDN -> RAAN at epoch (paper convention)
- Sun direction at epoch (low-precision analytic; STK can override at runtime)
- Build Classical-element initial state for STK from (altitude, ltdn, epoch)

All angles in degrees externally; radians internally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Paper SSO inclinations (paramspace.tex / dynmodel.tex) for the altitudes
# used in this study. Linear interpolation for off-table altitudes.
SSO_INCLINATION_DEG = {
    600.0: 97.92,
    700.0: 98.04,   # paper uses 98.17 elsewhere — see note below
    800.0: 98.17,
    900.0: 98.31,
}
# NOTE: dynmodel.tex Table 2 reports i = 98.17° for the baseline 700 km
# case (this is the value used for the gain anchor). The 98.04 value above
# is from the SSO inclination table at 700 km (per the Explore agent's
# extraction); paramspace uses 98.17 for "near-Sun-synchronous" in this
# study. We honour the paper's explicit 98.17° for 700 km and 98.31°
# for 800 km when those altitudes are requested directly.
PAPER_INCLINATION_DEG = {
    700.0: 98.17,
    800.0: 98.31,
}

R_EARTH_KM = 6378.1363
MU_EARTH_KM3_S2 = 398600.4418


def sso_inclination(altitude_km: float) -> float:
    """Sun-synchronous inclination [deg] for the given altitude [km].

    Returns paper's explicit value when available; otherwise linearly
    interpolates the SSO table.
    """
    if altitude_km in PAPER_INCLINATION_DEG:
        return PAPER_INCLINATION_DEG[altitude_km]
    keys = sorted(SSO_INCLINATION_DEG.keys())
    if altitude_km <= keys[0]:
        return SSO_INCLINATION_DEG[keys[0]]
    if altitude_km >= keys[-1]:
        return SSO_INCLINATION_DEG[keys[-1]]
    for k0, k1 in zip(keys[:-1], keys[1:]):
        if k0 <= altitude_km <= k1:
            t = (altitude_km - k0) / (k1 - k0)
            return SSO_INCLINATION_DEG[k0] * (1 - t) + SSO_INCLINATION_DEG[k1] * t
    return SSO_INCLINATION_DEG[keys[-1]]


def julian_date_from_ymdhms(y, m, d, hh=0, mm=0, ss=0.0) -> float:
    """Standard Gregorian calendar -> Julian Date (UT)."""
    if m <= 2:
        y -= 1
        m += 12
    A = math.floor(y / 100)
    B = 2 - A + math.floor(A / 4)
    JD = (
        math.floor(365.25 * (y + 4716))
        + math.floor(30.6001 * (m + 1))
        + d + B - 1524.5
        + (hh + mm / 60.0 + ss / 3600.0) / 24.0
    )
    return JD


def sun_right_ascension_deg(jd: float) -> float:
    """Mean Sun right ascension [deg], low-precision (Meeus simplified)."""
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = math.radians(L) + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    # RA from ecliptic longitude
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    return ra % 360.0


def raan_from_ltdn(ltdn_hours: float, jd_epoch: float) -> float:
    """
    RAAN [deg] for a Sun-synchronous orbit with given LTDN at the epoch.

    Convention (cf. run_ltan_sso_solar_sail_pystk.py:120-127 in the prior
    attempt): for the descending node at local time `ltdn_hours`, the
    ascending node leads the Sun's RA by the offset corresponding to
    (ltdn - 12) h. Each hour of local time = 15° longitude.
    """
    sun_ra = sun_right_ascension_deg(jd_epoch)
    raan = (sun_ra + 15.0 * (ltdn_hours - 12.0)) % 360.0
    return raan


def sun_direction_eci(jd: float):
    """Unit vector from Earth toward Sun in ECI (J2000), low-precision."""
    n = jd - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360.0)
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    x = math.cos(lam)
    y = math.cos(eps) * math.sin(lam)
    z = math.sin(eps) * math.sin(lam)
    return (x, y, z)


@dataclass
class ClassicalState:
    sma_km: float
    ecc: float
    inc_deg: float
    raan_deg: float
    aop_deg: float
    ta_deg: float


def initial_classical_state(altitude_km: float, ltdn_hours: float, jd_epoch: float,
                            ecc: float = 1e-4) -> ClassicalState:
    """Build the paper's initial state from altitude + LTDN + epoch."""
    sma_km = R_EARTH_KM + altitude_km
    return ClassicalState(
        sma_km=sma_km,
        ecc=ecc,
        inc_deg=sso_inclination(altitude_km),
        raan_deg=raan_from_ltdn(ltdn_hours, jd_epoch),
        aop_deg=0.0,
        ta_deg=0.0,
    )


# ---------------------------------------------------------------------------
# Self-checks
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    JD = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)
    print(f"JD(2026-01-01 12:00 UT) = {JD:.5f}  (expect ~2461042.0)")
    sun_ra = sun_right_ascension_deg(JD)
    print(f"Sun RA at epoch        = {sun_ra:.3f} deg")
    raan_anchor = raan_from_ltdn(12.266, JD)
    print(f"RAAN @ LTDN 12.266 h   = {raan_anchor:.3f} deg  (paper anchor 285.5 deg)")
    raan_noon = raan_from_ltdn(12.0, JD)
    print(f"RAAN @ LTDN 12.000 h   = {raan_noon:.3f} deg  (should equal Sun RA)")
    print(f"i_SSO(700 km) = {sso_inclination(700):.2f} deg (paper 98.17)")
    print(f"i_SSO(800 km) = {sso_inclination(800):.2f} deg (paper 98.31)")
    s = initial_classical_state(700.0, 12.266, JD)
    print(f"Initial state (gain anchor): a={s.sma_km:.3f} km, e={s.ecc:g}, "
          f"i={s.inc_deg:.3f}, RAAN={s.raan_deg:.3f}, AoP={s.aop_deg}, TA={s.ta_deg}")
