"""
V1 -- component-level force gates: Orekit vs the paper's model, state by state.

This is the finest-grained test in the battery. Rather than compare propagated
trajectories (where every difference is entangled with every other), we sample a
real orbit at the gain-anchor geometry and, at each sampled state, evaluate

    gravity   Orekit NewtonianAttraction + J2OnlyPerturbation   vs  gravity_j2_eci
    drag      Orekit DragForce(US1976Atmosphere, N-plate)       vs  drag_acceleration_eci
    SRP       Orekit RadiationPressureModel(cyl. umbra, plate)  vs  nplate_srp_acceleration_eci
    eclipse   Orekit CylindricallyShadowedLightFluxModel        vs  in_umbra_cylindrical

The right-hand column is the paper's own code, imported from "STK simulations",
so any disagreement is a genuine inter-tool difference and not a transcription
error. Gate: max relative vector difference <= 1e-9 on every component, and zero
eclipse-flag disagreements away from the umbra boundary.

G5 is the test STK Astrogator failed. STK's N-plate SRP model reported an
effective Sun-facing area of zero for the inertially-fixed sail, so it produced
no SRP force at all. Here we verify that Orekit's N-plate *does* consume the
`FrameAlignedProvider` attitude, by checking that the plate normal recovered
from the propagated attitude equals the sail normal and that the SRP force
magnitude follows the expected A cos^2(alpha) law.

Run:  ./run.sh validation/v1_component_gates.py
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
from org.orekit.forces.gravity import NewtonianAttraction, J2OnlyPerturbation  # noqa: E402
from org.orekit.forces.drag import DragForce  # noqa: E402
from org.orekit.forces.radiation import (  # noqa: E402
    RadiationPressureModel, CylindricallyShadowedLightFluxModel,
)
from org.orekit.orbits import KeplerianOrbit, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402
from org.orekit.utils import PVCoordinates  # noqa: E402
from org.orekit.orbits import CartesianOrbit  # noqa: E402

from orekit_core.atmosphere import US1976Atmosphere  # noqa: E402
from orekit_core.attitude import fixed_inertial_attitude  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    MU_EARTH, R_EARTH, J2, K_REF, SAIL_AREA, SAIL_MASS, CD, ABSORPTION, SPECULAR,
    ANCHOR_RAAN_DEG, ANCHOR_PITCH_DEG, INC_700,
)
from orekit_core.propagation import (  # noqa: E402
    EME2000, T0, SUN, OrekitCase, build_propagator, keplerian_period,
)
from orekit_core.spacecraft import drag_plate, srp_plate  # noqa: E402

# --- the paper's own implementation -----------------------------------------
from core.dynamics import gravity_j2_eci  # noqa: E402
from plugins.flatplate_drag_hpop import drag_acceleration_eci  # noqa: E402
from plugins.flatplate_srp_hpop import (  # noqa: E402
    nplate_srp_acceleration_eci, srp_acceleration_eci, in_umbra_cylindrical,
    cos_alpha, AU_M, P_1AU_N_PER_M2,
)

GATE = 1e-9
RESULTS = os.path.join(ROOT, "results")


def _v(vec):
    return np.array([vec.getX(), vec.getY(), vec.getZ()])


def _reldiff(a, b):
    """Relative vector difference, guarding the both-zero case."""
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    den = max(np.linalg.norm(a), np.linalg.norm(b))
    if den == 0.0:
        return 0.0
    return float(np.linalg.norm(a - b) / den)


def sample_states(n_orbits=1.0, dt=30.0):
    """States along a real propagated orbit at the gain anchor."""
    case = OrekitCase(altitude_km=700.0, inc_deg=INC_700, raan_deg=ANCHOR_RAAN_DEG,
                      pitch_deg=ANCHOR_PITCH_DEG, dt=dt)
    prop, rec, state0, n = build_propagator(case)
    period = keplerian_period(case.sma_m)
    prop.propagate(T0, T0.shiftedBy(n_orbits * period))
    return case, n, np.array(rec.t), np.array(rec.x), np.array(rec.y), np.array(rec.z), \
        np.array(rec.vx), np.array(rec.vy), np.array(rec.vz)


def main():
    case, n_hat, t, x, y, z, vx, vy, vz = sample_states()
    attitude = fixed_inertial_attitude(n_hat, EME2000)
    print(f"sampled {len(t)} states over one orbit at the 700 km gain anchor")
    print(f"sail normal (ECI) = ({n_hat[0]:+.6f}, {n_hat[1]:+.6f}, {n_hat[2]:+.6f})")

    # ---- Orekit force models -------------------------------------------------
    newton = NewtonianAttraction(MU_EARTH)
    j2 = J2OnlyPerturbation(MU_EARTH, R_EARTH, J2, EME2000)
    atm = US1976Atmosphere(EME2000, corotating=False)
    drag = DragForce(atm, drag_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR))
    flux = CylindricallyShadowedLightFluxModel(float(K_REF), SUN, float(R_EARTH))
    srp = RadiationPressureModel(flux, srp_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR))
    p_newton = newton.getParameters(T0)
    p_j2 = j2.getParameters(T0)
    p_drag = drag.getParameters(T0)
    p_srp = srp.getParameters(T0)

    worst = dict(gravity=0.0, drag=0.0, srp=0.0)
    eclipse_mismatch = 0
    eclipse_boundary = 0
    attitude_err = 0.0
    srp_cos2_err = 0.0
    n_lit = 0

    for k in range(len(t)):
        date = T0.shiftedBy(float(t[k]))
        r = Vector3D(float(x[k]), float(y[k]), float(z[k]))
        v = Vector3D(float(vx[k]), float(vy[k]), float(vz[k]))
        orbit = CartesianOrbit(PVCoordinates(r, v), EME2000, date, MU_EARTH)
        st = SpacecraftState(orbit, attitude.getAttitude(orbit, date, EME2000)) \
            .withMass(SAIL_MASS)

        rt = (r.getX(), r.getY(), r.getZ())
        vt = (v.getX(), v.getY(), v.getZ())
        rs_v = SUN.getPosition(date, EME2000)
        rs = (rs_v.getX(), rs_v.getY(), rs_v.getZ())

        # G1 gravity
        a_ok = _v(newton.acceleration(st, p_newton)) + _v(j2.acceleration(st, p_j2))
        a_pp = np.array(gravity_j2_eci(rt))
        worst["gravity"] = max(worst["gravity"], _reldiff(a_ok, a_pp))

        # G2 drag
        a_ok = _v(drag.acceleration(st, p_drag))
        a_pp = np.array(drag_acceleration_eci(rt, vt, n_hat, SAIL_AREA, SAIL_MASS, CD))
        worst["drag"] = max(worst["drag"], _reldiff(a_ok, a_pp))

        # G3 SRP
        a_ok = _v(srp.acceleration(st, p_srp))
        a_pp = np.array(nplate_srp_acceleration_eci(rt, rs, n_hat, SAIL_AREA,
                                                    SAIL_MASS, ABSORPTION, SPECULAR, 0.0))
        worst["srp"] = max(worst["srp"], _reldiff(a_ok, a_pp))

        # G4 eclipse flag
        lit_ok = float(flux.getLightingRatio(st)) > 0.5
        lit_pp = not in_umbra_cylindrical(rt, rs)
        if lit_ok != lit_pp:
            # tolerate the single-sample boundary quantisation of a binary umbra
            ratio = float(flux.getLightingRatio(st))
            if 0.0 < ratio < 1.0:
                eclipse_boundary += 1
            else:
                eclipse_mismatch += 1

        # G5 attitude coupling (the STK failure mode)
        body_z_in_eci = _v(st.getAttitude().getRotation().applyInverseTo(Vector3D.PLUS_K))
        attitude_err = max(attitude_err, float(np.linalg.norm(body_z_in_eci - np.array(n_hat))))
        if lit_ok:
            n_lit += 1
            d = np.array(rt) - np.array(rs)
            rhat = d / np.linalg.norm(d)
            ca = cos_alpha(n_hat, rhat)
            if ca > 0.05:
                # specular part of the N-plate law, along -n_hat, magnitude
                # (P_local * A / m) * 2 * rho_s * cos^2 alpha
                p_local = P_1AU_N_PER_M2 * (AU_M / np.linalg.norm(d)) ** 2
                expect = p_local * SAIL_AREA / SAIL_MASS * 2.0 * SPECULAR * ca * ca
                got = float(np.linalg.norm(_v(srp.acceleration(st, p_srp)) -
                                           p_local * SAIL_AREA / SAIL_MASS * ABSORPTION * ca * rhat))
                srp_cos2_err = max(srp_cos2_err, abs(got - expect) / expect)

    # ---- G6: Sun ephemeris ---------------------------------------------------
    # The three force gates above are evaluated with a *shared* Sun position, so
    # they isolate the force law. In a propagated run the two tools use their own
    # Sun: Orekit reads DE-440, the paper uses a low-precision analytic (Meeus)
    # series. Quantify that residual modelling difference over the study window.
    from core.orbit_init import sun_direction_eci  # noqa: E402
    from orekit_core.attitude import JD_EPOCH  # noqa: E402

    ang_err = 0.0
    dist_err = 0.0
    for day in np.linspace(0.0, 75.0, 76):
        date = T0.shiftedBy(float(day) * 86400.0)
        s_ok = _v(SUN.getPosition(date, EME2000))
        u_ok = s_ok / np.linalg.norm(s_ok)
        u_pp = np.array(sun_direction_eci(JD_EPOCH + day))
        u_pp = u_pp / np.linalg.norm(u_pp)
        ang_err = max(ang_err, math.degrees(math.acos(max(-1.0, min(1.0, float(u_ok @ u_pp))))))
        dist_err = max(dist_err, abs(float(np.linalg.norm(s_ok)) - AU_M) / AU_M)

    report = dict(
        n_states=int(len(t)),
        sun_direction_max_angle_deg=float(ang_err),
        sun_distance_max_rel_diff=float(dist_err),
        sail_normal=[float(q) for q in n_hat],
        max_rel_diff_gravity=worst["gravity"],
        max_rel_diff_drag=worst["drag"],
        max_rel_diff_srp=worst["srp"],
        eclipse_flag_mismatches=int(eclipse_mismatch),
        eclipse_boundary_samples=int(eclipse_boundary),
        attitude_axis_error=float(attitude_err),
        srp_cos2_law_max_rel_err=float(srp_cos2_err),
        lit_samples=int(n_lit),
        gate=GATE,
    )
    report["pass"] = bool(
        worst["gravity"] <= GATE and worst["drag"] <= GATE and worst["srp"] <= GATE
        and eclipse_mismatch == 0 and attitude_err <= 1e-12
        and srp_cos2_err <= 1e-9
    )

    print("\n[V1] component gates (Orekit vs the paper's own force code)")
    print(f"  gravity  max rel diff : {report['max_rel_diff_gravity']:.3e}")
    print(f"  drag     max rel diff : {report['max_rel_diff_drag']:.3e}")
    print(f"  SRP      max rel diff : {report['max_rel_diff_srp']:.3e}")
    print(f"  eclipse flag mismatches: {eclipse_mismatch} "
          f"(boundary-quantisation samples: {eclipse_boundary})")
    print(f"  attitude axis error    : {attitude_err:.3e}  "
          f"(body +Z vs sail normal in ECI)")
    print(f"  SRP cos^2 law error    : {srp_cos2_err:.3e}  over {n_lit} lit samples")
    print(f"  -> {'PASS' if report['pass'] else 'FAIL'}  (gate {GATE:g})")
    print("\n[V1-G6] residual Sun-ephemeris difference over the 75-day window")
    print(f"  DE-440 vs analytic Sun direction, max angle : {ang_err:.4f} deg")
    print(f"  Sun distance vs the paper's fixed 1 AU, max : {dist_err*100:.3f} %")
    print("  (these are NOT controlled out in the propagated comparisons below)")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "v1_component_gates.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(f"  wrote {os.path.join(RESULTS, 'v1_component_gates.json')}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
