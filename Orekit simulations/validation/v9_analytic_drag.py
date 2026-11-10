"""
V9 -- a propagator-free check on the drag decay.

The cross-validation in V2 shows Orekit and the open-source propagator agreeing
on a 14-day decay of -84.04 km at 700 km, where STK reported -7 km. But those
two propagators share the density tabulation, the integrator and the step, so
their agreement establishes that they evaluate the same arithmetic rather than
that the arithmetic is right. This script supplies the missing leg: a check that
uses no propagator at all.

For a near-circular orbit the secular decay follows directly from the energy
balance. With specific energy E = -mu/(2a) and drag power
a_drag . v = -(1/2) rho C_D (A/m) v^3,

    da/dt = -(2 a^2 / mu) * (1/2) rho C_D (A/m) v^3 = -rho C_D (A/m) sqrt(mu a),

using v^2 = mu/a. Integrating that one-line ordinary differential equation with
the same density table, from the same initial altitude, gives an independent
estimate of the 14-day decay.

Two questions are then answered:

  1. Does the propagated -84 km follow from the elementary theory? If it does,
     the propagators are not the source of the STK disagreement.
  2. What density would STK's -7 km require? Comparing that with the density STK
     itself reported at the same state tests whether STK's own numbers are
     mutually consistent.

Writes results/v9_analytic_drag.json.
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orekit_core.orekit_setup import boot, ROOT  # noqa: E402

boot()

from orekit_core.constants import MU_EARTH, R_EARTH, SAIL_AREA, SAIL_MASS, CD  # noqa: E402
from plugins.flatplate_drag_hpop import density_us1976_kg_m3  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
DAYS = 14.0
AOVERM = SAIL_AREA / SAIL_MASS          # 10 m^2/kg
STK_DA_700 = -7.0                       # km, reported
STK_DENSITY_700 = 3.2e-14               # kg/m^3, reported at the same state
PROPAGATED = {700.0: -84.040310, 800.0: -21.897976}   # from results/v2


def decay(alt0_km, days=DAYS, density_scale=1.0, steps_per_day=96):
    """Integrate da/dt = -rho C_D (A/m) sqrt(mu a) with RK4."""
    a = R_EARTH + alt0_km * 1e3
    dt = 86400.0 / steps_per_day
    n = int(days * steps_per_day)

    def f(a_):
        rho = density_us1976_kg_m3(a_ - R_EARTH, scaling=density_scale)
        return -rho * CD * AOVERM * math.sqrt(MU_EARTH * a_)

    for _ in range(n):
        k1 = f(a)
        k2 = f(a + 0.5 * dt * k1)
        k3 = f(a + 0.5 * dt * k2)
        k4 = f(a + dt * k3)
        a += (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return (a - (R_EARTH + alt0_km * 1e3)) / 1000.0


def scale_for_target(alt0_km, target_km, lo=1e-4, hi=2.0):
    """Density multiplier that reproduces a given 14-day decay (bisection)."""
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if decay(alt0_km, density_scale=mid) > target_km:   # too little decay
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def main():
    rows = []
    print(f"Propagator-free secular decay, A/m = {AOVERM:.0f} m^2/kg, "
          f"C_D = {CD}, {DAYS:.0f} days\n")
    for alt in (700.0, 800.0):
        an = decay(alt)
        prop = PROPAGATED[alt]
        rows.append(dict(altitude_km=alt, analytic_da14_km=an,
                         propagated_da14_km=prop,
                         rel_diff=abs(an - prop) / abs(prop)))
        print(f"  {alt:.0f} km : analytic {an:+8.3f} km   "
              f"propagated {prop:+8.3f} km   "
              f"difference {abs(an-prop)/abs(prop)*100:5.1f} %")

    print("\nThe analytic estimate omits eccentricity growth and the node-sampling")
    print("convention, which is where the residual few per cent sits. It uses no")
    print("propagator, so it is independent of both tools.\n")

    # What density would STK's endpoint require?
    s = scale_for_target(700.0, STK_DA_700)
    rho_ref = density_us1976_kg_m3(700e3)
    rho_needed = rho_ref * s
    print(f"To reproduce STK's {STK_DA_700:+.0f} km at 700 km the density would have")
    print(f"to be scaled by {s:.4f}, i.e. rho(700 km) = {rho_needed:.3e} kg/m^3.")
    print(f"  tabulated value          : {rho_ref:.3e} kg/m^3  "
          f"({rho_ref/rho_needed:.1f}x higher)")
    print(f"  density STK itself read back at that state : "
          f"{STK_DENSITY_700:.3e} kg/m^3  ({STK_DENSITY_700/rho_needed:.1f}x higher)")
    print("\nSo STK's reported decay is inconsistent with STK's own reported density")
    print("by roughly an order of magnitude, independently of either propagator.")

    report = dict(days=DAYS, area_over_mass=AOVERM, cd=CD, rows=rows,
                  stk_da14_km=STK_DA_700,
                  stk_reported_density=STK_DENSITY_700,
                  density_scale_to_match_stk=s,
                  density_implied_by_stk_decay=rho_needed,
                  tabulated_density_700km=rho_ref,
                  ratio_tabulated_to_implied=rho_ref / rho_needed,
                  ratio_stk_reported_to_implied=STK_DENSITY_700 / rho_needed)
    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, "v9_analytic_drag.json")
    with open(p, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
