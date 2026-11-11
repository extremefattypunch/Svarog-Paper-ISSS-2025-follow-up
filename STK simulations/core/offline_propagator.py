"""
Open-source reference propagator for the passive solar-sail problem.

This is the propagator that produces every quantitative result in the
manuscript (Sections 6-9).  It integrates the equations of motion of
Sections/dynmodel.tex directly in Cartesian ECI coordinates with a fixed-step
classical Runge-Kutta 4 scheme.

Force model
  - central gravity + J2 (degree 2, order 0)
  - solar radiation pressure on a single one-sided flat plate: the physical
    N-plate decomposition (absorbed + diffuse along the Sun->sat line, specular
    along the plate normal with a cos^2(alpha) law).  With rho_s = 0.70,
    rho_d = 0 the normal-incidence coefficient is C_r,eff = 1 + rho_s = 1.7.
    A "sunline" variant (force along the Sun line only) is retained because the
    manuscript demonstrates that it does no net orbit-averaged work.
  - binary cylindrical umbra gating the SRP
  - solar flux scaled by (1 AU / d_sun)^2 with d_sun from the low-precision
    analytic ephemeris (the epoch is near perihelion; the fixed-1-AU legacy
    behaviour is available with sun_distance="fixed_1au")
  - atmospheric drag: US Standard Atmosphere 1976 piecewise-exponential
    density, projected area A|cos theta_v| ("nplate") or constant area
    ("spherical"), no atmosphere co-rotation (geocentric altitude)
  - inertially fixed sail normal built at epoch from (LTAN -> RAAN, inclination,
    pitch measured in the orbital plane from the Sun line, roll about the Sun
    line)

Diagnostics
  Mean (secular) elements are recovered by stroboscopic sampling at ascending-
  node crossings, which removes the +/-9 km J2 short-period signature.  Between
  successive node crossings the propagator accumulates the SRP and drag specific
  work, the eclipsed fraction of the orbit, and the orbit-mean |F_T| and |F_N|
  of the SRP acceleration in the RTN frame.  Optional dense per-step histories
  (power, cos alpha, eclipse flag, RTN components) support the one-orbit figures.

Termination
  The run stops, and `reentry_day` is recorded, when the osculating perigee
  altitude falls below `reentry_alt_km` (default 120 km) or the geocentric
  altitude falls below 100 km.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .dynamics import gravity_j2_eci, MU_EARTH_M3_S2, R_EARTH_M
from .orbit_init import (julian_date_from_ymdhms, sun_direction_eci,
                         sun_distance_au, raan_from_ltan)
from .attitude import inertial_sail_normal
from plugins.flatplate_srp_hpop import (nplate_srp_acceleration_eci,
                                        NPLATE_CALIBRATION_PRIMARY,
                                        srp_acceleration_eci,
                                        in_umbra_cylindrical, cos_alpha, AU_M)
from plugins.flatplate_drag_hpop import drag_acceleration_eci, density_us1976_kg_m3

R_EARTH_KM = 6378.1363
JD_EPOCH = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)
EPOCH_ISO = "2026-01-01T12:00:00Z"


@dataclass
class SailCase:
    altitude_km: float = 800.0
    inc_deg: float = 98.31
    raan_deg: float = 312.045         # LTAN 14 h at the epoch (overridden if ltan_h given)
    ltan_h: float | None = None       # if set, RAAN is derived from it at JD_EPOCH
    pitch_deg: float = 34.0           # angle of the sail normal from the Sun line, in-plane
    roll_deg: float = 0.0             # rotation of the normal about the Sun line
    ecc: float = 1e-4
    area_m2: float = 100.0
    mass_kg: float = 10.0
    cr: float = 1.7                   # used only by the "sunline" SRP variant
    cd: float = 2.2
    cd_scale: float = 1.0             # multiplies the density (density-sensitivity sweep)
    disable_eclipse: bool = False     # eclipse-off branch
    srp_dir: str = "normal"           # "normal" (N-plate, production) or "sunline"
    drag_mode: str = "nplate"         # "nplate" (A|cos theta|) or "spherical" (constant A)
    use_srp: bool = True
    use_drag: bool = True
    sun_distance: str = "analytic"    # "analytic" (1/d^2 flux) or "fixed_1au"
    reentry_alt_km: float = 120.0     # stop when osculating perigee altitude drops below this
    dt: float = 10.0

    def __post_init__(self):
        if self.ltan_h is not None:
            self.raan_deg = raan_from_ltan(self.ltan_h, JD_EPOCH)

    @property
    def sma_km(self):
        return R_EARTH_KM + self.altitude_km


def _kep_to_cart(a_m, ecc, inc_deg, raan_deg, aop_deg, ta_deg):
    i, O = math.radians(inc_deg), math.radians(raan_deg)
    w, nu = math.radians(aop_deg), math.radians(ta_deg)
    p = a_m * (1 - ecc * ecc)
    r = p / (1 + ecc * math.cos(nu))
    r_pf = (r * math.cos(nu), r * math.sin(nu), 0.0)
    vf = math.sqrt(MU_EARTH_M3_S2 / p)
    v_pf = (-vf * math.sin(nu), vf * (ecc + math.cos(nu)), 0.0)
    cO, sO, ci, si, cw, sw = (math.cos(O), math.sin(O), math.cos(i),
                              math.sin(i), math.cos(w), math.sin(w))
    R = ((cO*cw - sO*sw*ci, -cO*sw - sO*cw*ci, sO*si),
         (sO*cw + cO*sw*ci, -sO*sw + cO*cw*ci, -cO*si),
         (sw*si, cw*si, ci))
    rot = lambda x: tuple(R[k][0]*x[0] + R[k][1]*x[1] + R[k][2]*x[2] for k in range(3))
    return rot(r_pf), rot(v_pf)


def _osc_elements(s):
    """Osculating a[km], e, apogee/perigee altitude[km], i[deg], RAAN[deg]."""
    r = np.array(s[:3]); v = np.array(s[3:])
    rn = np.linalg.norm(r); vn2 = v.dot(v)
    a = -MU_EARTH_M3_S2 / (2 * (vn2 / 2 - MU_EARTH_M3_S2 / rn))
    h = np.cross(r, v); hn = np.linalg.norm(h)
    evec = (np.cross(v, h) / MU_EARTH_M3_S2) - r / rn
    e = float(np.linalg.norm(evec))
    ha = a * (1 + e) - R_EARTH_M
    hp = a * (1 - e) - R_EARTH_M
    inc = math.degrees(math.acos(max(-1.0, min(1.0, h[2] / hn))))
    raan = math.degrees(math.atan2(h[0], -h[1])) % 360.0
    return a / 1000.0, e, ha / 1000.0, hp / 1000.0, inc, raan


def _rtn_components(r, v, acc):
    """Radial, transverse, normal components of `acc` in the local orbital frame."""
    rn = math.sqrt(r[0]**2 + r[1]**2 + r[2]**2)
    R = (r[0]/rn, r[1]/rn, r[2]/rn)
    hx = r[1]*v[2] - r[2]*v[1]; hy = r[2]*v[0] - r[0]*v[2]; hz = r[0]*v[1] - r[1]*v[0]
    hn = math.sqrt(hx*hx + hy*hy + hz*hz)
    N = (hx/hn, hy/hn, hz/hn)
    T = (N[1]*R[2] - N[2]*R[1], N[2]*R[0] - N[0]*R[2], N[0]*R[1] - N[1]*R[0])
    return (acc[0]*R[0] + acc[1]*R[1] + acc[2]*R[2],
            acc[0]*T[0] + acc[1]*T[1] + acc[2]*T[2],
            acc[0]*N[0] + acc[1]*N[1] + acc[2]*N[2])


def propagate(case: SailCase, days: float, want_forces: bool = False,
              force_stride: int = 1):
    """
    Integrate `days` of motion.  Returns a dict with:

      node_t, node_a, node_e, node_ha, node_hp, node_inc, node_raan
          mean (node-sampled) series [s, km, -, km, km, deg, deg]
      orb_W_srp, orb_W_drag           specific work accumulated over each orbit [J/kg]
      orb_ecl_frac                    eclipsed fraction of each orbit
      orb_FT_srp, orb_FN_srp          orbit-mean |F_T|, |F_N| of the SRP acceleration [m/s^2]
      cum_W_srp, cum_W_drag           cumulative specific work at each node [J/kg]
      a0, da_max, t_at_max_d, da_final, reentry_day, n_orbits, sail_normal
      forces (if want_forces): array of per-step rows
          [t, P_srp, P_drag, cos_alpha, eclipse, aR_srp, aT_srp, aN_srp, a_osc_km]
    """
    cal = NPLATE_CALIBRATION_PRIMARY
    sun0 = sun_direction_eci(JD_EPOCH)
    n = inertial_sail_normal(sun0, case.raan_deg, case.inc_deg, case.pitch_deg, case.roll_deg)
    a_m = R_EARTH_M + case.altitude_km * 1e3
    r0, v0 = _kep_to_cart(a_m, case.ecc, case.inc_deg, case.raan_deg, 0.0, 0.0)
    s = [r0[0], r0[1], r0[2], v0[0], v0[1], v0[2]]
    dt = case.dt
    nstep = int(round(days * 86400.0 / dt))
    fixed_1au = (case.sun_distance == "fixed_1au")

    def sun_at(t):
        jd = JD_EPOCH + t / 86400.0
        u = sun_direction_eci(jd)
        d = AU_M if fixed_1au else sun_distance_au(jd) * AU_M
        return (u[0]*d, u[1]*d, u[2]*d)

    def srp_acc(r, rs):
        if not case.use_srp:
            return (0.0, 0.0, 0.0)
        if case.srp_dir == "sunline":
            return srp_acceleration_eci(r, rs, n, case.area_m2, case.mass_kg, case.cr,
                                        disable_eclipse=case.disable_eclipse)
        return nplate_srp_acceleration_eci(r, rs, n, case.area_m2, case.mass_kg, *cal,
                                           disable_eclipse=case.disable_eclipse)

    def drag_acc(r, v):
        if not case.use_drag:
            return (0.0, 0.0, 0.0)
        if case.drag_mode == "spherical":
            rr = math.sqrt(r[0]**2 + r[1]**2 + r[2]**2)
            rho = density_us1976_kg_m3(rr - R_EARTH_M, scaling=case.cd_scale)
            vmag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
            if rho <= 0 or vmag == 0:
                return (0.0, 0.0, 0.0)
            amag = 0.5 * case.cd * rho * vmag * vmag * case.area_m2 / case.mass_kg
            return (-amag*v[0]/vmag, -amag*v[1]/vmag, -amag*v[2]/vmag)
        return drag_acceleration_eci(r, v, n, case.area_m2, case.mass_kg, case.cd,
                                     density_scaling=case.cd_scale)

    def acc(t, st):
        r = (st[0], st[1], st[2]); v = (st[3], st[4], st[5])
        ag = gravity_j2_eci(r); rs = sun_at(t)
        asrp = srp_acc(r, rs); ad = drag_acc(r, v)
        return (v[0], v[1], v[2], ag[0]+asrp[0]+ad[0], ag[1]+asrp[1]+ad[1], ag[2]+asrp[2]+ad[2])

    # node-sampled series
    node_t, node_a, node_e, node_ha, node_hp, node_inc, node_raan = [], [], [], [], [], [], []
    orb_W_srp, orb_W_drag, orb_ecl, orb_FT, orb_FN = [], [], [], [], []
    # per-orbit accumulators (reset at each ascending node)
    acc_Wsrp = acc_Wdrag = 0.0; acc_ecl = 0; acc_n = 0; acc_FT = acc_FN = 0.0
    Wsrp_total = Wdrag_total = 0.0
    fhist = []
    reentry_day = None
    prev_z = s[2]; t = 0.0
    for step in range(nstep + 1):
        r = (s[0], s[1], s[2]); v = (s[3], s[4], s[5]); rs = sun_at(t)
        asrp = srp_acc(r, rs); ad = drag_acc(r, v)
        P_srp = asrp[0]*v[0] + asrp[1]*v[1] + asrp[2]*v[2]
        P_drag = ad[0]*v[0] + ad[1]*v[1] + ad[2]*v[2]
        ecl = 0 if case.disable_eclipse else int(in_umbra_cylindrical(r, rs))
        aR, aT, aN = _rtn_components(r, v, asrp)
        # accumulate (left-rectangle rule; dt is small relative to the orbit)
        acc_Wsrp += P_srp * dt; acc_Wdrag += P_drag * dt
        Wsrp_total += P_srp * dt; Wdrag_total += P_drag * dt
        acc_ecl += ecl; acc_n += 1; acc_FT += abs(aT); acc_FN += abs(aN)

        if want_forces and (step % force_stride == 0):
            dx, dy, dz = r[0]-rs[0], r[1]-rs[1], r[2]-rs[2]
            dn = math.sqrt(dx*dx+dy*dy+dz*dz)
            ca = cos_alpha(n, (dx/dn, dy/dn, dz/dn))
            rn = math.sqrt(r[0]**2 + r[1]**2 + r[2]**2); vn2 = v[0]**2+v[1]**2+v[2]**2
            a_osc = (-MU_EARTH_M3_S2 / (2*(vn2/2 - MU_EARTH_M3_S2/rn))) / 1000.0
            fhist.append((t, P_srp, P_drag, ca, ecl, aR, aT, aN, a_osc))

        # ascending-node crossing (z: - -> +): sample mean elements, close the orbit
        if step > 0 and prev_z < 0.0 and s[2] >= 0.0:
            a_km, e, ha, hp, inc, raan = _osc_elements(s)
            node_t.append(t); node_a.append(a_km); node_e.append(e)
            node_ha.append(ha); node_hp.append(hp); node_inc.append(inc); node_raan.append(raan)
            orb_W_srp.append(acc_Wsrp); orb_W_drag.append(acc_Wdrag)
            orb_ecl.append(acc_ecl / max(1, acc_n))
            orb_FT.append(acc_FT / max(1, acc_n)); orb_FN.append(acc_FN / max(1, acc_n))
            acc_Wsrp = acc_Wdrag = 0.0; acc_ecl = 0; acc_n = 0; acc_FT = acc_FN = 0.0
            if hp < case.reentry_alt_km:
                reentry_day = t / 86400.0
                break
        prev_z = s[2]
        # geocentric altitude guard (between nodes)
        if (s[0]**2 + s[1]**2 + s[2]**2) < (R_EARTH_M + 100e3)**2:
            reentry_day = t / 86400.0
            break
        if step == nstep:
            break
        # RK4 step
        k1 = acc(t, s); s2 = [s[j]+0.5*dt*k1[j] for j in range(6)]
        k2 = acc(t+0.5*dt, s2); s3 = [s[j]+0.5*dt*k2[j] for j in range(6)]
        k3 = acc(t+0.5*dt, s3); s4 = [s[j]+dt*k3[j] for j in range(6)]
        k4 = acc(t+dt, s4)
        s = [s[j]+(dt/6)*(k1[j]+2*k2[j]+2*k3[j]+k4[j]) for j in range(6)]
        t += dt

    out = dict(
        sail_normal=n, raan_deg=case.raan_deg, ltan_h=case.ltan_h, dt=dt,
        node_t=np.array(node_t), node_a=np.array(node_a), node_e=np.array(node_e),
        node_ha=np.array(node_ha), node_hp=np.array(node_hp),
        node_inc=np.array(node_inc), node_raan=np.array(node_raan),
        orb_W_srp=np.array(orb_W_srp), orb_W_drag=np.array(orb_W_drag),
        orb_ecl_frac=np.array(orb_ecl), orb_FT_srp=np.array(orb_FT), orb_FN_srp=np.array(orb_FN),
        cum_W_srp=np.cumsum(orb_W_srp) if orb_W_srp else np.array([]),
        cum_W_drag=np.cumsum(orb_W_drag) if orb_W_drag else np.array([]),
        W_srp_total=Wsrp_total, W_drag_total=Wdrag_total,
        reentry_day=reentry_day, n_orbits=len(node_a), span_days=t / 86400.0,
    )
    if node_a:
        a0 = node_a[0]
        out["a0"] = a0
        out["da_max"] = float(np.max(out["node_a"]) - a0)
        out["t_at_max_d"] = float(node_t[int(np.argmax(out["node_a"]))] / 86400.0)
        out["da_final"] = float(node_a[-1] - a0)
        # value at the last node inside the first 14 days (nodes are ~100 min apart,
        # so this is within one orbit of t = 14 d); None if the run is shorter
        T14 = 14.0 * 86400.0
        if node_t[-1] >= T14 - 7200.0:
            out["da_at_14d"] = float(np.interp(min(T14, node_t[-1]), out["node_t"], out["node_a"]) - a0)
        else:
            out["da_at_14d"] = None
    else:
        out["a0"] = out["da_max"] = out["t_at_max_d"] = out["da_final"] = out["da_at_14d"] = None
    if want_forces:
        out["forces"] = np.array(fhist)
    return out


if __name__ == "__main__":
    for alt, inc, ltan, pitch in ((800.0, 98.31, 14.0, 34.0), (700.0, 98.17, 12.266, 24.8)):
        c = SailCase(altitude_km=alt, inc_deg=inc, ltan_h=ltan, pitch_deg=pitch, dt=30.0)
        r = propagate(c, 14.0)
        print(f"alt={alt:.0f} LTAN={ltan:.3f}h pitch={pitch:+.1f}: a0={r['a0']:.3f} "
              f"da_max={r['da_max']:+.3f} km @ day {r['t_at_max_d']:.2f}  "
              f"da_final={r['da_final']:+.3f} km  ({r['n_orbits']} orbits, reentry={r['reentry_day']})")
