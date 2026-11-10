"""
V4 -- does the N-plate SRP model consume an inertially-fixed attitude?

This is the test STK Astrogator failed. For the passively oriented sail, STK's
built-in N-plate SRP model reported an effective Sun-facing area of zero, so it
produced no SRP force at all: an SRP-only propagation came out identical to a
J2-only one. The manuscript therefore had to validate the open-source SRP
implementation analytically rather than against a second tool.

Orekit's analogue of that configuration is a `FixedPanel` inside a
`BoxAndSolarArraySpacecraft`, driven by a `FrameAlignedProvider` -- the direct
counterpart of STK's `eProfileFixedInAxes` profile with a quaternion mapping
body +Z onto the sail normal. We check it three ways:

  A. Geometric  -- recover the plate normal from the propagated attitude and
     confirm it equals the frozen sail normal, so the projected Sun-facing area
     is A cos(alpha) and not zero.
  B. Pointwise  -- sweep the sail pitch from 0 to 90 degrees and confirm the SRP
     force follows the flat-plate law, vanishing only at true edge-on incidence.
  C. Propagated -- run 14 days with SRP only (no drag) at the gain anchor and
     confirm the mean semi-major axis departs from the J2-only reference. This
     is the exact comparison that came out null in STK.

Writes results/v4_srp_attitude_coupling.json and
reproduced_figures/orekit_srp_attitude.png.
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

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from org.hipparchus.geometry.euclidean.threed import Vector3D  # noqa: E402
from org.orekit.forces.radiation import (  # noqa: E402
    RadiationPressureModel, CylindricallyShadowedLightFluxModel,
)
from org.orekit.orbits import KeplerianOrbit, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402

from orekit_core.attitude import (  # noqa: E402
    fixed_inertial_attitude, sail_normal_eci, sun_unit_at_epoch,
)
from orekit_core.constants import (  # noqa: E402
    MU_EARTH, R_EARTH, K_REF, SAIL_AREA, SAIL_MASS, CD, ABSORPTION, SPECULAR,
    ANCHOR_RAAN_DEG, ANCHOR_PITCH_DEG, INC_700, P_1AU, AU,
)
from orekit_core.propagation import EME2000, T0, SUN, OrekitCase, propagate  # noqa: E402
from orekit_core.spacecraft import srp_plate  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "reproduced_figures")

ALT = 700.0
DAYS = 14.0


def _v(vec):
    return np.array([vec.getX(), vec.getY(), vec.getZ()])


def state_at_epoch(pitch_deg):
    n = sail_normal_eci(ANCHOR_RAAN_DEG, INC_700, pitch_deg)
    orbit = KeplerianOrbit(R_EARTH + ALT * 1e3, 1e-4, math.radians(INC_700),
                           0.0, math.radians(ANCHOR_RAAN_DEG), 0.0,
                           PositionAngleType.TRUE, EME2000, T0, MU_EARTH)
    att = fixed_inertial_attitude(n, EME2000)
    st = SpacecraftState(orbit, att.getAttitude(orbit, T0, EME2000)).withMass(SAIL_MASS)
    return st, np.array(n)


def main():
    flux = CylindricallyShadowedLightFluxModel(float(K_REF), SUN, float(R_EARTH))
    srp = RadiationPressureModel(flux, srp_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR))
    params = srp.getParameters(T0)

    # ---- A + B: pitch sweep -------------------------------------------------
    pitches, cosa, area_eff, force, expected = [], [], [], [], []
    max_normal_err = 0.0
    for deg in range(0, 91, 2):
        st, n = state_at_epoch(deg)
        # plate normal as Orekit itself sees it, recovered from the attitude
        n_orekit = _v(st.getAttitude().getRotation().applyInverseTo(Vector3D.PLUS_K))
        max_normal_err = max(max_normal_err, float(np.linalg.norm(n_orekit - n)))

        r = _v(st.getPVCoordinates(EME2000).getPosition())
        rs = _v(SUN.getPosition(T0, EME2000))
        d = r - rs
        dist = float(np.linalg.norm(d))
        rhat = d / dist
        ca = float(-(n_orekit @ rhat))          # cos(alpha), one-sided sail

        a = _v(srp.acceleration(st, params))
        p_local = P_1AU * (AU / dist) ** 2
        # flat-plate N-plate law with rho_d = 0
        a_expect = (p_local * SAIL_AREA / SAIL_MASS) * (
            ABSORPTION * max(ca, 0.0) * rhat - 2.0 * SPECULAR * max(ca, 0.0) ** 2 * n_orekit)

        pitches.append(deg)
        cosa.append(ca)
        # effective Sun-facing area as a flight-dynamics tool would report it
        area_eff.append(SAIL_AREA * max(ca, 0.0))
        force.append(float(np.linalg.norm(a)) * SAIL_MASS)
        expected.append(float(np.linalg.norm(a_expect)) * SAIL_MASS)

    pitches = np.array(pitches); area_eff = np.array(area_eff)
    force = np.array(force); expected = np.array(expected)
    law_err = float(np.max(np.abs(force - expected) / np.maximum(expected, 1e-30)))

    # Effective area at the anchor pitch, taken from the measured sweep rather
    # than restated as 100 cos(24.8 deg): the point is what Orekit produced.
    k_anchor = int(np.argmin(np.abs(pitches - ANCHOR_PITCH_DEG)))
    area_anchor_measured = float(area_eff[k_anchor])
    area_anchor_interp = float(np.interp(ANCHOR_PITCH_DEG, pitches, area_eff))

    print("[V4-A] plate normal recovered from the propagated attitude")
    print(f"  max |n_orekit - n_sail| over the pitch sweep : {max_normal_err:.3e}")
    print(f"  effective Sun-facing area at the anchor pitch "
          f"({ANCHOR_PITCH_DEG} deg): {area_anchor_interp:.3f} m^2 "
          f"(measured; nearest grid point {pitches[k_anchor]:.0f} deg -> "
          f"{area_anchor_measured:.3f} m^2)")
    print("  STK Astrogator reported effective SRPArea = 0 m^2 for this attitude")
    print("\n[V4-B] pointwise SRP force vs the flat-plate law")
    print(f"  max relative error over 0-90 deg pitch : {law_err:.3e}")
    print(f"  |F| at pitch 0  : {force[0]:.4e} N   (area {area_eff[0]:.1f} m^2)")
    print(f"  |F| at pitch 90 : {force[-1]:.4e} N   (area {area_eff[-1]:.1f} m^2)")

    # ---- C: propagated SRP-only vs J2-only ---------------------------------
    # Adaptive integration with eclipse event detection, per the policy set by
    # v7_eclipse_discontinuity.py: a fixed step over a discontinuous umbra
    # overstates the gain, and this is a gain number.
    base = dict(altitude_km=ALT, inc_deg=INC_700, raan_deg=ANCHOR_RAAN_DEG,
                pitch_deg=ANCHOR_PITCH_DEG, integrator="dp853", dt=30.0)
    r_j2 = propagate(OrekitCase(use_srp=False, use_drag=False, **base), DAYS)
    r_srp = propagate(OrekitCase(use_srp=True, use_drag=False, **base), DAYS)
    da_j2 = float(r_j2["node_a"][-1] - r_j2["node_a"][0])
    da_srp = float(r_srp["node_a"][-1] - r_srp["node_a"][0])
    swing_srp = float(np.max(r_srp["node_a"]) - np.min(r_srp["node_a"]))
    swing_j2 = float(np.max(r_j2["node_a"]) - np.min(r_j2["node_a"]))

    print("\n[V4-C] propagated 14 days, SRP only (no drag), at the 700 km gain anchor")
    print(f"  J2 only  : Delta a = {da_j2:+.4f} km   (peak-to-peak {swing_j2:.4f} km)")
    print(f"  J2 + SRP : Delta a = {da_srp:+.4f} km   (peak-to-peak {swing_srp:.4f} km)")
    print(f"  separation = {abs(da_srp - da_j2):.4f} km")
    print("  STK Astrogator: SRP-only propagation was identical to J2-only "
          "(no SRP force produced)")

    # ---- figure -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0))
    axes[0].plot(pitches, area_eff, lw=2.0, label="Orekit N-plate (this work)")
    axes[0].axhline(0.0, color="tab:red", lw=2.0, ls="--",
                    label="STK Astrogator N-plate (reported)")
    axes[0].axvline(ANCHOR_PITCH_DEG, color="0.5", lw=0.8, ls=":")
    axes[0].set_xlabel("sail pitch [deg]")
    axes[0].set_ylabel(r"effective Sun-facing area $A\cos\alpha$ [m$^2$]")
    axes[0].set_title("Attitude coupling of the N-plate SRP model", fontsize=9)
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    axes[1].plot(r_j2["node_t"] / 86400, r_j2["node_a"] - r_j2["node_a"][0],
                 lw=1.6, label=r"$J_2$ only")
    axes[1].plot(r_srp["node_t"] / 86400, r_srp["node_a"] - r_srp["node_a"][0],
                 lw=1.6, label=r"$J_2$ + N-plate SRP")
    axes[1].set_xlabel("time [days]")
    axes[1].set_ylabel(r"$\Delta a$ (mean) [km]")
    axes[1].set_title("SRP-only propagation, 700 km gain anchor", fontsize=9)
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    out = os.path.join(FIGS, "orekit_srp_attitude.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"\nwrote {out}")

    report = dict(
        max_normal_recovery_error=max_normal_err,
        srp_flat_plate_law_max_rel_err=law_err,
        effective_area_at_anchor_m2=area_anchor_interp,
        effective_area_at_anchor_analytic_m2=float(
            SAIL_AREA * math.cos(math.radians(ANCHOR_PITCH_DEG))),
        stk_effective_area_m2=0.0,
        force_N_at_pitch0=float(force[0]),
        force_N_at_pitch90=float(force[-1]),
        pitch_deg=[int(p) for p in pitches],
        effective_area_m2=[float(q) for q in area_eff],
        srp_force_N=[float(q) for q in force],
        propagated=dict(days=DAYS,
                        da_j2_only_km=da_j2, da_j2_plus_srp_km=da_srp,
                        separation_km=abs(da_srp - da_j2),
                        peak_to_peak_j2_km=swing_j2,
                        peak_to_peak_srp_km=swing_srp),
    )
    report["pass"] = bool(max_normal_err <= 1e-12 and law_err <= 1e-9
                          and abs(da_srp - da_j2) > 0.05)
    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, "v4_srp_attitude_coupling.json")
    with open(p, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {p}")
    print(f"\n-> {'PASS' if report['pass'] else 'FAIL'}: Orekit's N-plate SRP model "
          "does consume the inertially-fixed attitude")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
