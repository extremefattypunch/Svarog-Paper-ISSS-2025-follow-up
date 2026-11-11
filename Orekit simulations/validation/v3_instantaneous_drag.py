"""
V3 -- instantaneous drag and density at a matched state.

The manuscript's most quoted drag number is a *pointwise* one: at a matched
state near 700 km the instantaneous drag acceleration computed from STK's
reported density, drag area, drag coefficient and mass agreed with the
open-source value to within about 4 percent (both roughly
1.9e-5 m s^-2, with density near 3.1e-14 kg m^-3), yet the propagated 14-day
decay differed by nearly an order of magnitude.

This script reproduces that pointwise check for Orekit at both study altitudes
and both drag geometries (spherical reference area and the N-plate A|cos theta|
projection), so the same table can be filled in for a third tool.

Writes results/v3_instantaneous_drag.json.
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

from org.hipparchus.geometry.euclidean.threed import Vector3D  # noqa: E402
from org.orekit.forces.drag import DragForce  # noqa: E402
from org.orekit.orbits import KeplerianOrbit, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402

from orekit_core.atmosphere import US1976Atmosphere  # noqa: E402
from orekit_core.attitude import fixed_inertial_attitude, raan_for_ltdn, sail_normal_eci  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    MU_EARTH, R_EARTH, SAIL_AREA, SAIL_MASS, CD, REPRO_PITCH_DEG, inclination_for,
)
from orekit_core.propagation import EME2000, T0  # noqa: E402
from orekit_core.spacecraft import drag_plate, spherical_drag  # noqa: E402

from plugins.flatplate_drag_hpop import (  # noqa: E402
    density_us1976_kg_m3, drag_acceleration_eci,
)

# Values reported for STK 13 / Astrogator in this repository (not re-run here).
STK_DENSITY_700 = 3.2e-14        # kg m^-3
STK_ACCEL_700 = 1.9e-5           # m s^-2, from STK's density/area/Cd/mass
PAPER_ACCEL_700 = 1.9e-5

RESULTS = os.path.join(ROOT, "results")
LTDN = 14.0
RAAN = raan_for_ltdn(LTDN)


def matched_state(alt_km):
    """Epoch state of the study orbit at the given altitude (true anomaly 0)."""
    inc = inclination_for(alt_km)
    n = sail_normal_eci(RAAN, inc, REPRO_PITCH_DEG)
    orbit = KeplerianOrbit(R_EARTH + alt_km * 1e3, 1e-4, math.radians(inc),
                           0.0, math.radians(RAAN), 0.0, PositionAngleType.TRUE,
                           EME2000, T0, MU_EARTH)
    att = fixed_inertial_attitude(n, EME2000)
    st = SpacecraftState(orbit, att.getAttitude(orbit, T0, EME2000)).withMass(SAIL_MASS)
    return st, n


def layer_continuity():
    """How continuous is the piecewise-exponential fit at its layer boundaries?

    Each layer is (floor altitude, density at that floor, scale height). If the
    fit were constructed to join up, extrapolating layer i from its own floor to
    the floor of layer i+1 with layer i's scale height would reproduce layer
    i+1's anchor density. It does not: the tabulation used here is discontinuous
    at every boundary. That matters because the study altitudes sit exactly on
    two of those boundaries.
    """
    from plugins.flatplate_drag_hpop import _ATM_TABLE as table  # noqa: E402

    rows = []
    for i in range(len(table) - 1):
        h0, rho0 = table[i][0], table[i][1]
        h1, rho1 = table[i + 1][0], table[i + 1][1]
        # the revised table is interpolated log-linearly between nodes, so the
        # value approached from below is the node value itself: jump ratio 1.
        extrap = density_us1976_kg_m3(h1 * 1e3 - 1e-6)
        rows.append(dict(floor_km=h0, next_floor_km=h1,
                         anchor_density=rho1, extrapolated_density=extrap,
                         jump_ratio=extrap / rho1))
    return rows


def main():
    atm = US1976Atmosphere(EME2000, corotating=False)

    cont = layer_continuity()
    in_range = [r for r in cont if r["floor_km"] >= 200]
    worst = max(abs(r["jump_ratio"] - 1.0) for r in in_range)
    n_disc = sum(1 for r in cont if abs(r["jump_ratio"] - 1.0) > 0.02)
    print(f"[V3] layer continuity of the piecewise-exponential density fit")
    print(f"  boundaries discontinuous by more than 2 %: {n_disc}/{len(cont)}")
    print(f"  worst jump above 200 km: {worst*100:.1f} %")

    rows = []
    for alt in (700.0, 800.0):
        st, n = matched_state(alt)
        pv = st.getPVCoordinates(EME2000)
        r, v = pv.getPosition(), pv.getVelocity()
        rt = (r.getX(), r.getY(), r.getZ())
        vt = (v.getX(), v.getY(), v.getZ())
        geocentric_alt = r.getNorm() - R_EARTH

        rho_ok = float(atm.getDensity(T0, r, EME2000))
        rho_pp = density_us1976_kg_m3(geocentric_alt)

        # The paper's 16-segment piecewise-exponential fit is not continuous at
        # the layer boundaries: each layer anchors rho at its own floor with its
        # own scale height. At 700 km the jump is sizeable, and the study orbit
        # (e = 1e-4, true anomaly 0) sits just *below* the boundary, so the
        # sampled density belongs to the layer underneath. Report both so the
        # comparison against STK's quoted figure is not misread.
        rho_ref = density_us1976_kg_m3(alt * 1e3)
        rho_just_below = density_us1976_kg_m3(alt * 1e3 - 1.0)
        layer_jump = rho_just_below / rho_ref

        cos_theta = abs(float(np.dot(np.array(n), np.array(vt)) / np.linalg.norm(vt)))

        out = dict(altitude_km=alt,
                   geocentric_altitude_km=float(geocentric_alt / 1e3),
                   speed_m_s=float(v.getNorm()),
                   density_orekit=rho_ok,
                   density_paper=rho_pp,
                   density_at_reference_altitude=float(rho_ref),
                   density_layer_discontinuity_ratio=float(layer_jump),
                   cos_theta=cos_theta)

        for mode, sensitive in (("spherical", spherical_drag(SAIL_AREA, CD)),
                                ("nplate", drag_plate(SAIL_AREA, CD))):
            force = DragForce(atm, sensitive)
            a = force.acceleration(st, force.getParameters(T0))
            a_ok = float(a.getNorm())
            if mode == "spherical":
                a_pp = 0.5 * CD * rho_pp * v.getNorm() ** 2 * SAIL_AREA / SAIL_MASS
            else:
                a_pp = float(np.linalg.norm(
                    drag_acceleration_eci(rt, vt, n, SAIL_AREA, SAIL_MASS, CD)))
            out[f"accel_orekit_{mode}"] = a_ok
            out[f"accel_paper_{mode}"] = a_pp
            out[f"rel_diff_{mode}"] = abs(a_ok - a_pp) / a_pp if a_pp else 0.0

        if alt == 700.0:
            out["density_stk_reported"] = STK_DENSITY_700
            out["accel_stk_reported"] = STK_ACCEL_700
            out["density_rel_diff_vs_stk"] = abs(rho_ok - STK_DENSITY_700) / STK_DENSITY_700
            out["density_ref_rel_diff_vs_stk"] = abs(rho_ref - STK_DENSITY_700) / STK_DENSITY_700
        rows.append(out)

        print(f"\n[V3] {alt:.0f} km  (geocentric altitude {out['geocentric_altitude_km']:.3f} km, "
              f"speed {out['speed_m_s']:.1f} m/s, |cos theta| = {cos_theta:.4f})")
        print(f"  density    Orekit {rho_ok:.4e}   open-source {rho_pp:.4e} kg/m^3")
        print(f"  density at the reference altitude ({alt:.0f}.000 km) : {rho_ref:.4e} kg/m^3")
        print(f"  US-1976 table discontinuity across the {alt:.0f} km layer floor : "
              f"x{layer_jump:.3f}")
        if alt == 700.0:
            print(f"             STK (reported) {STK_DENSITY_700:.4e} kg/m^3   "
                  f"-> Orekit differs by {out['density_rel_diff_vs_stk']*100:.1f} % at the "
                  f"sampled state, {out['density_ref_rel_diff_vs_stk']*100:.1f} % at "
                  f"{alt:.0f}.000 km")
        for mode in ("spherical", "nplate"):
            print(f"  |a_drag| {mode:9s} Orekit {out[f'accel_orekit_{mode}']:.4e}   "
                  f"open-source {out[f'accel_paper_{mode}']:.4e} m/s^2   "
                  f"rel diff {out[f'rel_diff_{mode}']:.2e}")
        if alt == 700.0:
            print(f"  |a_drag| STK (reported, spherical) {STK_ACCEL_700:.4e} m/s^2")

    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, "v3_instantaneous_drag.json")
    with open(p, "w") as f:
        json.dump(dict(ltdn_h=LTDN, raan_deg=RAAN, pitch_deg=REPRO_PITCH_DEG,
                       rows=rows, layer_continuity=cont,
                       n_discontinuous_boundaries=n_disc,
                       n_boundaries=len(cont),
                       worst_jump_above_200km=worst), f, indent=2)
    print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
