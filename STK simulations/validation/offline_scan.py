"""
Fast offline (LTDN x pitch) scan with the paper's exact model to locate the
gain lobe and compare it to the paper's Fig 2 (peak ~LTDN 12.27h, pitch 24.8 deg;
lobe LTDN 9-15h x pitch 0-43 deg). Diagnoses whether our geometry/attitude
convention reproduces the paper before trusting STK.

Usage: python validation/offline_scan.py [days] [dt] [pitch_sign]
"""
from __future__ import annotations
import math, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from core.dynamics import gravity_j2_eci, MU_EARTH_M3_S2, R_EARTH_M
from plugins.flatplate_srp_hpop import (nplate_srp_acceleration_eci,
                                        NPLATE_CALIBRATION_PRIMARY, AU_M)
from plugins.flatplate_drag_hpop import drag_acceleration_eci
from core.orbit_init import (julian_date_from_ymdhms, sun_direction_eci,
                             raan_from_ltdn)
from core.attitude import inertial_sail_normal

DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 14.0
DT = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
ALT = float(sys.argv[3]) if len(sys.argv) > 3 else 700.0
ECC, AREA, MASS, CR, CD = 1e-4, 100.0, 10.0, 1.7, 2.2
INC = 98.31 if ALT >= 750 else 98.17   # paper inclinations (700->98.17, 800->98.31)
JD0 = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)


def kep_to_cart(a_m, ecc, inc, raan, aop, ta):
    i, O, w, nu = map(math.radians, (inc, raan, aop, ta))
    p = a_m*(1-ecc*ecc); r = p/(1+ecc*math.cos(nu))
    r_pf = (r*math.cos(nu), r*math.sin(nu), 0.0)
    vf = math.sqrt(MU_EARTH_M3_S2/p); v_pf = (-vf*math.sin(nu), vf*(ecc+math.cos(nu)), 0.0)
    cO,sO,ci,si,cw,sw = math.cos(O),math.sin(O),math.cos(i),math.sin(i),math.cos(w),math.sin(w)
    R = ((cO*cw-sO*sw*ci,-cO*sw-sO*cw*ci,sO*si),(sO*cw+cO*sw*ci,-sO*sw+cO*cw*ci,-cO*si),(sw*si,cw*si,ci))
    rot = lambda x: tuple(R[k][0]*x[0]+R[k][1]*x[1]+R[k][2]*x[2] for k in range(3))
    return rot(r_pf), rot(v_pf)


def damax_mean(ltdn, pitch):
    raan = raan_from_ltdn(ltdn, JD0)
    n = inertial_sail_normal(sun_direction_eci(JD0), raan, INC, pitch, 0.0)
    a_m = R_EARTH_M + ALT*1e3
    r0, v0 = kep_to_cart(a_m, ECC, INC, raan, 0.0, 0.0)
    s = [r0[0],r0[1],r0[2],v0[0],v0[1],v0[2]]
    period = 2*math.pi*math.sqrt(a_m**3/MU_EARTH_M3_S2)
    win = max(1, int(round(period/DT)))
    def acc(t, st):
        r=(st[0],st[1],st[2]); v=(st[3],st[4],st[5])
        ag=gravity_j2_eci(r); jd=JD0+t/86400.0; u=sun_direction_eci(jd)
        rs=(u[0]*AU_M,u[1]*AU_M,u[2]*AU_M)
        asrp=nplate_srp_acceleration_eci(r,rs,n,AREA,MASS,*NPLATE_CALIBRATION_PRIMARY)
        ad=drag_acceleration_eci(r,v,n,AREA,MASS,CD)
        return (v[0],v[1],v[2],ag[0]+asrp[0]+ad[0],ag[1]+asrp[1]+ad[1],ag[2]+asrp[2]+ad[2])
    nstep=int(DAYS*86400.0/DT); t=0.0; ah=[]
    for _ in range(nstep+1):
        r=math.sqrt(s[0]**2+s[1]**2+s[2]**2); v2=s[3]**2+s[4]**2+s[5]**2
        ah.append(-MU_EARTH_M3_S2/(2*(v2/2-MU_EARTH_M3_S2/r))/1000.0)
        k1=acc(t,s); s2=[s[j]+0.5*DT*k1[j] for j in range(6)]; k2=acc(t+0.5*DT,s2)
        s3=[s[j]+0.5*DT*k2[j] for j in range(6)]; k3=acc(t+0.5*DT,s3)
        s4=[s[j]+DT*k3[j] for j in range(6)]; k4=acc(t+DT,s4)
        s=[s[j]+(DT/6)*(k1[j]+2*k2[j]+2*k3[j]+k4[j]) for j in range(6)]; t+=DT
    # non-overlapping per-orbit bin means (clean short-period removal, no edge bias)
    binmeans=[]
    for i in range(0, len(ah)-win, win):
        binmeans.append(sum(ah[i:i+win])/win)
    if not binmeans:
        return float("nan")
    a0=binmeans[0]
    return max(m-a0 for m in binmeans)


def main():
    ltdns = [0,3,6,9,10.5,12.266,13.5,15,18,21]
    pitches = [-35,-24.8,-10,0,10,24.8,35,45]
    print(f"Offline gain scan: {DAYS}d dt={DT:.0f}s  (Delta a_max mean, km; + = gain)")
    print("pitch\\LTDN " + "".join(f"{l:7.1f}" for l in ltdns))
    for p in pitches:
        row = []
        for l in ltdns:
            try:
                row.append(damax_mean(l, p))
            except Exception:
                row.append(float("nan"))
        mark = "".join(f"{v:7.2f}" for v in row)
        print(f"{p:7.1f}   {mark}")


if __name__ == "__main__":
    main()
