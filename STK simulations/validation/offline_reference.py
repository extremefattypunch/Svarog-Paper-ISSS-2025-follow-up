"""
Offline reference propagation of the gain anchor using the paper's exact model
(core/dynamics.py: J2 + cos^2a SRP + US-1976 drag, binary cylindrical umbra),
integrated with a fixed-step RK4 (scipy-free). Reports orbit-averaged ("mean")
semi-major-axis Delta-a_max, to cross-check the STK Astrogator N-plate result.

Usage:  python validation/offline_reference.py [days] [mode]
        mode in {full, srp, drag}   (default full)
"""
from __future__ import annotations
import math, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from core.dynamics import gravity_j2_eci, MU_EARTH_M3_S2, R_EARTH_M, SailConfig
from plugins.flatplate_srp_hpop import srp_acceleration_eci, AU_M
from plugins.flatplate_drag_hpop import drag_acceleration_eci
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal

DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 14.0
MODE = sys.argv[2] if len(sys.argv) > 2 else "full"

ALT_KM, INC, RAAN, ECC, PITCH = 700.0, 98.17, 285.5, 1e-4, 24.8
AREA, MASS, CR, CD = 100.0, 10.0, 1.7, 2.2
JD0 = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)
SUN_UNIT = sun_direction_eci(JD0)
NORMAL = inertial_sail_normal(SUN_UNIT, RAAN, INC, PITCH, 0.0)


def kep_to_cart(a_m, ecc, inc_deg, raan_deg, aop_deg, ta_deg, mu=MU_EARTH_M3_S2):
    i = math.radians(inc_deg); O = math.radians(raan_deg)
    w = math.radians(aop_deg); nu = math.radians(ta_deg)
    p = a_m * (1 - ecc * ecc); r = p / (1 + ecc * math.cos(nu))
    r_pf = (r * math.cos(nu), r * math.sin(nu), 0.0)
    vf = math.sqrt(mu / p); v_pf = (-vf * math.sin(nu), vf * (ecc + math.cos(nu)), 0.0)
    cO, sO = math.cos(O), math.sin(O); ci, si = math.cos(i), math.sin(i); cw, sw = math.cos(w), math.sin(w)
    R = ((cO*cw - sO*sw*ci, -cO*sw - sO*cw*ci, sO*si),
         (sO*cw + cO*sw*ci, -sO*sw + cO*cw*ci, -cO*si),
         (sw*si, cw*si, ci))
    rot = lambda x: tuple(R[k][0]*x[0]+R[k][1]*x[1]+R[k][2]*x[2] for k in range(3))
    return rot(r_pf), rot(v_pf)


def sun_at(t):
    jd = JD0 + t / 86400.0
    u = sun_direction_eci(jd)
    return (u[0]*AU_M, u[1]*AU_M, u[2]*AU_M)


def accel(t, s):
    r = (s[0], s[1], s[2]); v = (s[3], s[4], s[5])
    ag = gravity_j2_eci(r)
    rs = sun_at(t)
    asrp = (0.0, 0.0, 0.0) if MODE == "drag" else srp_acceleration_eci(
        r, rs, NORMAL, AREA, MASS, CR)
    adrag = (0.0, 0.0, 0.0) if MODE == "srp" else drag_acceleration_eci(
        r, v, NORMAL, AREA, MASS, CD)
    return (v[0], v[1], v[2], ag[0]+asrp[0]+adrag[0], ag[1]+asrp[1]+adrag[1], ag[2]+asrp[2]+adrag[2])


def osc_sma(s):
    r = math.sqrt(s[0]**2 + s[1]**2 + s[2]**2)
    v2 = s[3]**2 + s[4]**2 + s[5]**2
    energy = v2/2 - MU_EARTH_M3_S2/r
    return -MU_EARTH_M3_S2/(2*energy) / 1000.0  # km


def main():
    a_m = R_EARTH_M + ALT_KM*1e3
    r0, v0 = kep_to_cart(a_m, ECC, INC, RAAN, 0.0, 0.0)
    s = [r0[0], r0[1], r0[2], v0[0], v0[1], v0[2]]
    period = 2*math.pi*math.sqrt(a_m**3/MU_EARTH_M3_S2)
    dt = 30.0
    n = int(DAYS*86400.0/dt)
    win = max(1, int(round(period/dt)))  # one-orbit smoothing window

    a_hist = []
    t = 0.0
    for step in range(n+1):
        a_hist.append(osc_sma(s))
        # RK4
        k1 = accel(t, s)
        s2 = [s[j]+0.5*dt*k1[j] for j in range(6)]; k2 = accel(t+0.5*dt, s2)
        s3 = [s[j]+0.5*dt*k2[j] for j in range(6)]; k3 = accel(t+0.5*dt, s3)
        s4 = [s[j]+dt*k3[j] for j in range(6)]; k4 = accel(t+dt, s4)
        s = [s[j]+(dt/6)*(k1[j]+2*k2[j]+2*k3[j]+k4[j]) for j in range(6)]
        t += dt

    # orbit-average (centered moving average over one period) -> "mean" SMA
    mean = []
    half = win // 2
    for i in range(len(a_hist)):
        lo = max(0, i-half); hi = min(len(a_hist), i+half+1)
        mean.append(sum(a_hist[lo:hi])/(hi-lo))
    a0 = mean[0]
    damax = max(mean) - a0
    i_max = mean.index(max(mean))
    print(f"OFFLINE reference [{MODE}] {DAYS} d, dt={dt:.0f}s, osc-window={win} steps")
    print(f"  mean a[0]  = {a0:.4f} km   (osc a[0] = {a_hist[0]:.4f})")
    print(f"  mean a[-1] = {mean[-1]:.4f} km   (delta {mean[-1]-a0:+.4f} km)")
    print(f"  mean a_max = {max(mean):.4f} km   -> da_max = {damax:+.4f} km at t={i_max*dt/86400:.2f} d")
    print(f"  osc amplitude (first 2000 samples) = {max(a_hist[:2000])-min(a_hist[:2000]):.3f} km")


if __name__ == "__main__":
    main()
