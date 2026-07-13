"""
Offline reference propagator for the solar-sail problem (the paper's exact model,
which STK's built-in N-plate SRP cannot fully realize because Astrogator does not
couple the fixed-inertial attitude into the N-plate force model).

Force model (Sections/dynmodel.tex, with the paper's *reduced*/normal-directed SRP
that actually produces the eclipse-gated gain):
  - central + J2 gravity
  - N-plate flat-plate SRP along the sail normal (specular 0.70 -> C_r,eff = 1.7),
    binary cylindrical umbra, one-sided
  - US Standard 1976 piecewise-exponential drag, projected area A|cos theta_v|,
    no atmosphere co-rotation
  - inertially-fixed sail normal, pitch measured IN the orbital plane from the Sun

Fixed-step RK4. Mean semi-major axis is extracted by stroboscopic sampling at
ascending-node crossings (removes the +/-9 km J2 short-period cleanly), matching
what STK's Brouwer-Lyd mean provider does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .dynamics import gravity_j2_eci, MU_EARTH_M3_S2, R_EARTH_M
from .orbit_init import julian_date_from_ymdhms, sun_direction_eci, raan_from_ltdn
from .attitude import inertial_sail_normal
from plugins.flatplate_srp_hpop import (nplate_srp_acceleration_eci,
                                        NPLATE_CALIBRATION_PRIMARY,
                                        srp_acceleration_eci,
                                        in_umbra_cylindrical, cos_alpha, AU_M)
from plugins.flatplate_drag_hpop import drag_acceleration_eci, density_us1976_kg_m3

R_EARTH_KM = 6378.1363
JD_EPOCH = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)


@dataclass
class SailCase:
    altitude_km: float = 700.0
    inc_deg: float = 98.17
    raan_deg: float = 285.5
    pitch_deg: float = 24.8
    roll_deg: float = 0.0
    ecc: float = 1e-4
    area_m2: float = 100.0
    mass_kg: float = 10.0
    cr: float = 1.7
    cd: float = 2.2
    cd_scale: float = 1.0          # Fig-7 density sweep (drag ~ rho*Cd)
    disable_eclipse: bool = False  # Fig-3 eclipse-off branch
    srp_dir: str = "normal"        # "normal" (N-plate/paper reduced) or "sunline"
    drag_mode: str = "nplate"      # "nplate" (A|cos theta|) or "spherical" (const A)
    use_srp: bool = True           # disable SRP entirely (for the STK validation case)
    dt: float = 30.0

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


def _osc_a_km(s):
    r = math.sqrt(s[0]**2 + s[1]**2 + s[2]**2)
    v2 = s[3]**2 + s[4]**2 + s[5]**2
    return (-MU_EARTH_M3_S2 / (2 * (v2 / 2 - MU_EARTH_M3_S2 / r))) / 1000.0


def _osc_elements(s):
    """Osculating a[km], e, apogee/perigee altitude[km] from state (m, m/s)."""
    r = np.array(s[:3]); v = np.array(s[3:])
    rn = np.linalg.norm(r); vn2 = v.dot(v)
    a = -MU_EARTH_M3_S2 / (2 * (vn2 / 2 - MU_EARTH_M3_S2 / rn))
    h = np.cross(r, v)
    evec = (np.cross(v, h) / MU_EARTH_M3_S2) - r / rn
    e = np.linalg.norm(evec)
    ha = a * (1 + e) - R_EARTH_M
    hp = a * (1 - e) - R_EARTH_M
    return a / 1000.0, e, ha / 1000.0, hp / 1000.0


def propagate(case: SailCase, days: float, want_forces: bool = False):
    """
    Integrate `days` and return a dict with node-sampled mean series and (optionally)
    per-step force work. `want_forces` enables the SRP/drag power arrays for Figs 4/5.
    """
    cal = NPLATE_CALIBRATION_PRIMARY
    sun0 = sun_direction_eci(JD_EPOCH)
    n = inertial_sail_normal(sun0, case.raan_deg, case.inc_deg, case.pitch_deg, case.roll_deg)
    a_m = R_EARTH_M + case.altitude_km * 1e3
    r0, v0 = _kep_to_cart(a_m, case.ecc, case.inc_deg, case.raan_deg, 0.0, 0.0)
    s = [r0[0], r0[1], r0[2], v0[0], v0[1], v0[2]]
    dt = case.dt
    nstep = int(days * 86400.0 / dt)

    def sun_at(t):
        u = sun_direction_eci(JD_EPOCH + t / 86400.0)
        return (u[0]*AU_M, u[1]*AU_M, u[2]*AU_M)

    def srp_acc(r, rs):
        if not case.use_srp:
            return (0.0, 0.0, 0.0)
        if case.srp_dir == "sunline":
            return srp_acceleration_eci(r, rs, n, case.area_m2, case.mass_kg, case.cr,
                                        disable_eclipse=case.disable_eclipse)
        return nplate_srp_acceleration_eci(r, rs, n, case.area_m2, case.mass_kg, *cal,
                                           disable_eclipse=case.disable_eclipse)

    def drag_acc(r, v):
        if case.drag_mode == "spherical":
            # constant reference area (no cos-theta projection), attitude-independent
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
        asrp = srp_acc(r, rs)
        ad = drag_acc(r, v)
        return (v[0], v[1], v[2], ag[0]+asrp[0]+ad[0], ag[1]+asrp[1]+ad[1], ag[2]+asrp[2]+ad[2])

    node_t, node_a, node_e, node_ha, node_hp = [], [], [], [], []
    fhist = []  # optional per-step (t, P_srp, P_drag, cos_alpha, eclipse) for Figs 4/5
    prev_z = s[2]; t = 0.0
    for step in range(nstep + 1):
        # ascending-node crossing (z: - -> +): sample mean elements (interp weight ~1)
        if step > 0 and prev_z < 0.0 and s[2] >= 0.0:
            a_km, e, ha, hp = _osc_elements(s)
            node_t.append(t); node_a.append(a_km); node_e.append(e)
            node_ha.append(ha); node_hp.append(hp)
        prev_z = s[2]
        if want_forces:
            r = (s[0], s[1], s[2]); v = (s[3], s[4], s[5]); rs = sun_at(t)
            asrp = srp_acc(r, rs)
            ad = drag_acceleration_eci(r, v, n, case.area_m2, case.mass_kg, case.cd,
                                       density_scaling=case.cd_scale)
            dx, dy, dz = r[0]-rs[0], r[1]-rs[1], r[2]-rs[2]
            dn = math.sqrt(dx*dx+dy*dy+dz*dz); rhat = (dx/dn, dy/dn, dz/dn)
            ca = cos_alpha(n, rhat)
            ecl = 0 if case.disable_eclipse else int(in_umbra_cylindrical(r, rs))
            fhist.append((t, asrp[0]*v[0]+asrp[1]*v[1]+asrp[2]*v[2],
                       ad[0]*v[0]+ad[1]*v[1]+ad[2]*v[2], ca, ecl))
        # RK4 step
        k1 = acc(t, s); s2 = [s[j]+0.5*dt*k1[j] for j in range(6)]
        k2 = acc(t+0.5*dt, s2); s3 = [s[j]+0.5*dt*k2[j] for j in range(6)]
        k3 = acc(t+0.5*dt, s3); s4 = [s[j]+dt*k3[j] for j in range(6)]
        k4 = acc(t+dt, s4)
        s = [s[j]+(dt/6)*(k1[j]+2*k2[j]+2*k3[j]+k4[j]) for j in range(6)]
        t += dt

    out = dict(
        sail_normal=n,
        node_t=np.array(node_t), node_a=np.array(node_a), node_e=np.array(node_e),
        node_ha=np.array(node_ha), node_hp=np.array(node_hp),
    )
    if node_a:
        a0 = node_a[0]
        out["a0"] = a0
        out["da_max"] = float(np.max(out["node_a"]) - a0)
        out["t_at_max_d"] = float(node_t[int(np.argmax(out["node_a"]))] / 86400.0)
        out["da_final"] = float(node_a[-1] - a0)
    if want_forces:
        out["forces"] = np.array(fhist)
    return out


if __name__ == "__main__":
    # anchor gain check at both pitch signs
    for pitch in (24.8, -24.8, 0.0):
        c = SailCase(pitch_deg=pitch, dt=30.0)
        r = propagate(c, 14.0)
        print(f"pitch={pitch:+6.1f}: a0={r['a0']:.3f} da_max={r['da_max']:+.3f} km "
              f"@ day {r['t_at_max_d']:.2f}   da_final={r['da_final']:+.3f} km "
              f"({len(r['node_a'])} orbits)")
