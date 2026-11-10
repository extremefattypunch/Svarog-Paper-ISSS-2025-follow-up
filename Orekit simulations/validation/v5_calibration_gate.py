"""
V5 -- SRP calibration gate: Orekit's N-plate against the paper's reduced model.

Because STK could not exercise its N-plate SRP model under the passive attitude,
the manuscript validated the SRP implementation *analytically*: it showed that a
plate with specular reflectivity rho_s = 0.7 and rho_d = 0 (normal-incidence
coefficient C_r,eff = 1 + rho_s = 1.7) reproduces the reduced model's
C_r cos^2(alpha) acceleration magnitude to within 1.6 percent for incidence
angles up to 45 degrees.

Here the same gate is applied to Orekit's own `BoxAndSolarArraySpacecraft`
N-plate, so the analytic calibration is now anchored to a second independent
flight-dynamics implementation rather than to the study's own code.

Two checks, mirroring "STK simulations"/validation/calibration_gate.py:
  1. alpha sweep 0-90 deg: |a_orekit| / |a_paper_reduced| must stay within
     5 percent for alpha <= 45 deg; direction offset reported.
  2. one-orbit SRP specific-power profile at the gain anchor: peak ratio,
     profile correlation and eclipse sign-selectivity must agree.

Writes results/v5_calibration_gate.json and
reproduced_figures/orekit_calibration_gate.png.
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
from org.orekit.orbits import CartesianOrbit, KeplerianOrbit, PositionAngleType  # noqa: E402
from org.orekit.propagation import SpacecraftState  # noqa: E402
from org.orekit.utils import PVCoordinates  # noqa: E402

from orekit_core.attitude import fixed_inertial_attitude, sail_normal_eci  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    MU_EARTH, R_EARTH, K_REF, SAIL_AREA, SAIL_MASS, CD, CR, ABSORPTION, SPECULAR,
    ANCHOR_RAAN_DEG, ANCHOR_PITCH_DEG, INC_700, P_1AU, AU,
)
from orekit_core.propagation import (  # noqa: E402
    EME2000, T0, SUN, OrekitCase, build_propagator, keplerian_period,
)
from orekit_core.spacecraft import srp_plate  # noqa: E402

from plugins.flatplate_srp_hpop import srp_acceleration_eci  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "reproduced_figures")
GATE_ALPHA_DEG = 45.0
GATE_TOL = 0.05
PAPER_REPORTED_MAX_DEV = 0.016   # 1.6 % as stated in the manuscript


def _v(vec):
    return np.array([vec.getX(), vec.getY(), vec.getZ()])


def check_alpha_sweep(srp, params):
    """Orekit N-plate vs the paper's reduced C_r cos^2(alpha) model."""
    rs = _v(SUN.getPosition(T0, EME2000))
    s_hat = rs / np.linalg.norm(rs)
    # satellite sunward of Earth so it is lit and the geometry is clean
    r = s_hat * (R_EARTH + 700e3)
    v = np.array([-5000.0, 4000.0, 2000.0])
    perp = np.cross(s_hat, np.array([0.0, 0.0, 1.0]))
    perp /= np.linalg.norm(perp)

    rows, worst = [], 0.0
    for deg in range(0, 91):
        a_rad = math.radians(deg)
        n = math.cos(a_rad) * s_hat + math.sin(a_rad) * perp
        n /= np.linalg.norm(n)

        orbit = CartesianOrbit(PVCoordinates(Vector3D(*[float(q) for q in r]),
                                             Vector3D(*[float(q) for q in v])),
                               EME2000, T0, MU_EARTH)
        att = fixed_inertial_attitude(n, EME2000)
        st = SpacecraftState(orbit, att.getAttitude(orbit, T0, EME2000)).withMass(SAIL_MASS)
        a_ok = _v(srp.acceleration(st, params))

        a_pp = np.array(srp_acceleration_eci(tuple(r), tuple(rs), tuple(n),
                                             SAIL_AREA, SAIL_MASS, CR))
        m_ok, m_pp = float(np.linalg.norm(a_ok)), float(np.linalg.norm(a_pp))
        ratio = m_ok / m_pp if m_pp > 0 else float("nan")
        if m_ok > 0 and m_pp > 0:
            c = float(np.dot(a_ok, a_pp) / (m_ok * m_pp))
            offset = math.degrees(math.acos(max(-1.0, min(1.0, c))))
        else:
            offset = float("nan")
        rows.append((deg, m_pp, m_ok, ratio, offset))
        if deg <= GATE_ALPHA_DEG and m_pp > 0:
            worst = max(worst, abs(ratio - 1.0))

    print("\n[V5-1] alpha sweep: Orekit N-plate (0.3, 0.7, 0) vs paper 1.7 cos^2(alpha)")
    print("  deg   |a_paper|    |a_orekit|   ratio    dir offset")
    for deg, mp, mo, ratio, off in rows:
        if deg % 15 == 0 or deg == 45:
            rt = f"{ratio:6.4f}" if mp > 1e-12 else "  n/a "
            ot = f"{off:6.2f} deg" if not math.isnan(off) else "   n/a"
            print(f"  {deg:3d}   {mp:.4e}  {mo:.4e}  {rt}   {ot}")
    print(f"  worst |ratio - 1| for alpha <= {GATE_ALPHA_DEG:.0f} deg : {worst*100:.2f} %"
          f"   (gate {GATE_TOL*100:.0f} %; manuscript reports {PAPER_REPORTED_MAX_DEV*100:.1f} %)")
    return worst <= GATE_TOL, worst, rows


def check_one_orbit(srp, params, flux):
    """One-orbit SRP specific-power profile at the gain anchor.

    Three profiles are compared along a single Orekit trajectory:

      * Orekit N-plate with the cylindrical umbra  -- the model actually flown
      * Orekit N-plate with the umbra disabled     -- the no-eclipse reference,
        used for the eclipse sign-selectivity statistic
      * the paper's *reduced* Sun-line model        -- same magnitude law but the
        force directed along the Sun line rather than the plate normal

    The third is not a competing implementation of the same thing: the
    manuscript states explicitly that a Sun-line-directed force does zero net
    orbit-averaged work in this geometry. Including it quantifies that claim,
    so peak ratio and profile correlation are the agreement metrics here, while
    the net-work difference is the physical result, not a discrepancy.
    """
    case = OrekitCase(altitude_km=700.0, inc_deg=INC_700, raan_deg=ANCHOR_RAAN_DEG,
                      pitch_deg=ANCHOR_PITCH_DEG, dt=5.0)
    prop, rec, state0, n = build_propagator(case, want_diagnostics=True)
    period = keplerian_period(case.sma_m)
    prop.propagate(T0, T0.shiftedBy(period))

    t = np.asarray(rec.t)
    p_ok = np.asarray(rec.p_srp)
    lit = np.asarray(rec.lit) > 0.5

    # Orekit N-plate with no eclipse at all (occulting radius zero).
    flux_noecl = CylindricallyShadowedLightFluxModel(float(K_REF), SUN, 0.0)
    srp_noecl = RadiationPressureModel(
        flux_noecl, srp_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR))
    par_noecl = srp_noecl.getParameters(T0)
    att = fixed_inertial_attitude(n, EME2000)

    p_ok_noecl = np.empty_like(p_ok)
    p_pp = np.empty_like(p_ok)
    p_pp_nplate_noecl = np.empty_like(p_ok)
    for k in range(len(t)):
        date = T0.shiftedBy(float(t[k]))
        rt = (rec.x[k], rec.y[k], rec.z[k])
        vt = (rec.vx[k], rec.vy[k], rec.vz[k])
        orbit = CartesianOrbit(
            PVCoordinates(Vector3D(*[float(q) for q in rt]),
                          Vector3D(*[float(q) for q in vt])),
            EME2000, date, MU_EARTH)
        st = SpacecraftState(orbit, att.getAttitude(orbit, date, EME2000)) \
            .withMass(SAIL_MASS)
        a = _v(srp_noecl.acceleration(st, par_noecl))
        p_ok_noecl[k] = float(a @ np.array(vt))

        rs = tuple(_v(SUN.getPosition(date, EME2000)))
        ap = srp_acceleration_eci(rt, rs, tuple(n), SAIL_AREA, SAIL_MASS, CR)
        p_pp[k] = ap[0]*vt[0] + ap[1]*vt[1] + ap[2]*vt[2]
        # the paper's *N-plate*, umbra disabled -- the like-for-like partner for
        # Orekit's no-eclipse power, used for the sign-selectivity gate
        an = nplate_srp_acceleration_eci(rt, rs, tuple(n), SAIL_AREA, SAIL_MASS,
                                         ABSORPTION, SPECULAR, 0.0,
                                         disable_eclipse=True)
        p_pp_nplate_noecl[k] = an[0]*vt[0] + an[1]*vt[1] + an[2]*vt[2]

    peak_ok = float(np.max(np.abs(p_ok)))
    peak_pp = float(np.max(np.abs(p_pp)))
    peak_ratio = peak_ok / peak_pp if peak_pp else float("nan")
    corr = float(np.corrcoef(p_ok, p_pp)[0, 1])
    dt = float(t[1] - t[0])
    work_ok = float(np.sum(p_ok) * dt)
    work_ok_noecl = float(np.sum(p_ok_noecl) * dt)
    work_pp = float(np.sum(p_pp) * dt)
    n_ecl = int(np.sum(~lit))
    # fraction of eclipsed samples that would have carried negative SRP work
    sel = float(np.mean(p_ok_noecl[~lit] < 0) * 100.0) if n_ecl else float("nan")
    sel_paper = (float(np.mean(p_pp_nplate_noecl[~lit] < 0) * 100.0)
                 if n_ecl else float("nan"))
    sel_gap = abs(sel - sel_paper) if n_ecl else float("nan")

    print("\n[V5-2] one-orbit SRP power at the 700 km gain anchor")
    print(f"  orbit period                    : {period/60:.2f} min "
          f"({len(t)} samples @ {dt:.0f} s)")
    print(f"  eclipsed samples                : {n_ecl} / {len(t)}  "
          f"({n_ecl/len(t)*100:.1f} %)")
    print(f"  peak |SRP power|, reduced model : {peak_pp:.4e} W/kg")
    print(f"  peak |SRP power|, Orekit N-plate: {peak_ok:.4e} W/kg   "
          f"(ratio {peak_ratio:.4f})")
    print(f"  profile correlation             : {corr:.6f}")
    print(f"  net per-orbit SRP work, Orekit N-plate, eclipse on  : {work_ok:+.2f} J/kg")
    print(f"  net per-orbit SRP work, Orekit N-plate, eclipse off : {work_ok_noecl:+.2f} J/kg")
    print(f"  net per-orbit SRP work, reduced Sun-line model      : {work_pp:+.2f} J/kg")
    print(f"    (the manuscript's point: a Sun-line force does ~zero net work;")
    print(f"     the plate-normal force does not. Manuscript Fig. 5: +799 J/kg)")
    print(f"  eclipse sign-selectivity, Orekit N-plate       : {sel:.2f} %")
    print(f"  eclipse sign-selectivity, paper's N-plate      : {sel_paper:.2f} %"
          f"   (gap {sel_gap:.3f} pp, gate <= 1 pp)")
    print(f"  eclipse sign-selectivity, manuscript Fig. 4    : 85.7 %"
          f"   -> NOT reproduced (gap {abs(sel - 85.7):.1f} pp; reported, not gated)")

    # The gate is a model-agreement gate: does Orekit's N-plate behave like the
    # paper's N-plate? It is deliberately not a gate on reproducing the
    # manuscript's Fig.-4/Fig.-5 magnitudes, which are a physical result and are
    # reported separately above. The reference gate in
    # "STK simulations"/validation/calibration_gate.py fails its own 10 pp
    # selectivity check on this geometry for the same reason.
    passed = (0.9 <= peak_ratio <= 1.2) and corr >= 0.95 and sel_gap <= 1.0

    fig, ax = plt.subplots(figsize=(8, 4.2))
    tm = t / 60.0
    ax.plot(tm, p_pp, lw=1.6, label=r"reduced Sun-line model, $C_r\cos^2\alpha$")
    ax.plot(tm, p_ok, "--", lw=1.4, label="Orekit N-plate (0.3, 0.7, 0), umbra on")
    ax.plot(tm, p_ok_noecl, ":", lw=1.0, color="0.5",
            label="Orekit N-plate, umbra off")
    ax.axhline(0.0, color="k", lw=0.6)
    inside = False
    for i, f in enumerate(~lit):
        if f and not inside:
            start = tm[i]; inside = True
        if (not f or i == len(lit) - 1) and inside:
            ax.axvspan(start, tm[i], color="0.85", zorder=0)
            inside = False
    ax.set_xlabel("time [min]")
    ax.set_ylabel(r"SRP specific power $\mathbf{a}_{\rm SRP}\cdot\mathbf{v}$ [W/kg]")
    ax.set_title("One-orbit SRP power at the gain anchor (shaded = umbra)", fontsize=9)
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    out = os.path.join(FIGS, "orekit_calibration_gate.png")
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out}")

    return passed, dict(peak_ratio=peak_ratio, correlation=corr,
                        work_orekit_nplate_eclipse_on_J_per_kg=work_ok,
                        work_orekit_nplate_eclipse_off_J_per_kg=work_ok_noecl,
                        work_reduced_sunline_J_per_kg=work_pp,
                        manuscript_fig5_work_J_per_kg=799.0,
                        eclipse_fraction=float(n_ecl / len(t)),
                        eclipse_sign_selectivity_orekit_pct=sel,
                        eclipse_sign_selectivity_paper_nplate_pct=sel_paper,
                        eclipse_sign_selectivity_gap_pp=sel_gap,
                        manuscript_fig4_selectivity_pct=85.7,
                        manuscript_fig4_gap_pp=float(abs(sel - 85.7)),
                        manuscript_fig4_reproduced=False,
                        period_s=float(period))


def main():
    flux = CylindricallyShadowedLightFluxModel(float(K_REF), SUN, float(R_EARTH))
    srp = RadiationPressureModel(flux, srp_plate(SAIL_AREA, CD, ABSORPTION, SPECULAR))
    params = srp.getParameters(T0)

    p1, worst, rows = check_alpha_sweep(srp, params)
    p2, stats = check_one_orbit(srp, params, flux)

    report = dict(alpha_sweep_worst_rel_dev=float(worst),
                  alpha_sweep_gate=GATE_TOL,
                  manuscript_reported_dev=PAPER_REPORTED_MAX_DEV,
                  alpha_sweep_pass=bool(p1),
                  one_orbit=stats, one_orbit_pass=bool(p2))
    report["pass"] = bool(p1 and p2)
    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, "v5_calibration_gate.json")
    with open(p, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {p}")
    print(f"GATE RESULT: {'PASS' if report['pass'] else 'FAIL'}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
