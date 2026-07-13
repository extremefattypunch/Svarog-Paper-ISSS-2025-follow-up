"""
Measure per-orbit specific work (J/kg) of SRP (eclipse on/off) and drag at the
gain anchor, for the two attitude conventions (out-of-plane vs in-plane pitch).
Paper gain case: SRP ~ +790 J/kg/orbit, drag ~ -500 -> net ~ +290 -> gain.
"""
from __future__ import annotations
import math, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
from core.dynamics import gravity_j2_eci, MU_EARTH_M3_S2, R_EARTH_M
from plugins.flatplate_srp_hpop import (srp_acceleration_eci,
                                        nplate_srp_acceleration_eci,
                                        NPLATE_CALIBRATION_PRIMARY,
                                        in_umbra_cylindrical, AU_M)
from plugins.flatplate_drag_hpop import drag_acceleration_eci
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci, raan_from_ltdn
from core.attitude import inertial_sail_normal, orbit_normal_eci, _unit, _cross

INC, ECC, AREA, MASS, CR, CD, ALT = 98.17, 1e-4, 100.0, 10.0, 1.7, 2.2, 700.0
JD0 = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)
SRP_DIR = "sunline"


def n_outplane(rs, raan, pitch):
    return inertial_sail_normal(rs, raan, INC, pitch, 0.0)

def n_inplane(rs, raan, pitch):
    rs = _unit(rs); h = orbit_normal_eci(raan, INC); base = _unit(_cross(h, rs))
    p = math.radians(pitch)
    return _unit((math.cos(p)*rs[0]+math.sin(p)*base[0],
                  math.cos(p)*rs[1]+math.sin(p)*base[1],
                  math.cos(p)*rs[2]+math.sin(p)*base[2]))

def kep_to_cart(a_m, raan):
    i, O = math.radians(INC), math.radians(raan)
    p = a_m*(1-ECC*ECC); r = p/(1+ECC)
    r_pf=(r,0.0,0.0); vf=math.sqrt(MU_EARTH_M3_S2/p); v_pf=(0.0,vf*(ECC+1),0.0)
    ci,si=math.cos(i),math.sin(i); cO,sO=math.cos(O),math.sin(O)
    R=((cO,-sO*ci,sO*si),(sO,cO*ci,-cO*si),(0,si,ci))
    rot=lambda x: tuple(R[k][0]*x[0]+R[k][1]*x[1]+R[k][2]*x[2] for k in range(3))
    return rot(r_pf), rot(v_pf)


def one_orbit_work(ltdn, pitch, normal_fn):
    raan = raan_from_ltdn(ltdn, JD0)
    rs_unit = sun_direction_eci(JD0)
    rs = (rs_unit[0]*AU_M, rs_unit[1]*AU_M, rs_unit[2]*AU_M)
    n = normal_fn(rs_unit, raan, pitch)
    a_m = R_EARTH_M + ALT*1e3
    r0, v0 = kep_to_cart(a_m, raan)
    s = [r0[0],r0[1],r0[2],v0[0],v0[1],v0[2]]
    period = 2*math.pi*math.sqrt(a_m**3/MU_EARTH_M3_S2)
    dt = 2.0; nstep = int(period/dt)
    # SRP force model: "sunline" (paper implemented eq) or "normal" (N-plate specular)
    def srp_force(r, disable_ecl):
        if SRP_DIR == "normal":
            return nplate_srp_acceleration_eci(r, rs, n, AREA, MASS,
                                               *NPLATE_CALIBRATION_PRIMARY,
                                               disable_eclipse=disable_ecl)
        return srp_acceleration_eci(r, rs, n, AREA, MASS, CR, disable_eclipse=disable_ecl)
    Wsrp_on=Wsrp_off=Wdrag=0.0; ecl_tot=ecl_neg=0
    def acc(st):
        r=(st[0],st[1],st[2]); v=(st[3],st[4],st[5])
        ag=gravity_j2_eci(r)
        asrp=srp_force(r, False)
        ad=drag_acceleration_eci(r,v,n,AREA,MASS,CD)
        return (v[0],v[1],v[2],ag[0]+asrp[0]+ad[0],ag[1]+asrp[1]+ad[1],ag[2]+asrp[2]+ad[2])
    for _ in range(nstep):
        r=(s[0],s[1],s[2]); v=(s[3],s[4],s[5])
        asrp_on=srp_force(r, False)
        asrp_off=srp_force(r, True)
        ad=drag_acceleration_eci(r,v,n,AREA,MASS,CD)
        Wsrp_on += (asrp_on[0]*v[0]+asrp_on[1]*v[1]+asrp_on[2]*v[2])*dt
        Wsrp_off += (asrp_off[0]*v[0]+asrp_off[1]*v[1]+asrp_off[2]*v[2])*dt
        Wdrag += (ad[0]*v[0]+ad[1]*v[1]+ad[2]*v[2])*dt
        if in_umbra_cylindrical(r, rs):
            ecl_tot += 1
            if (asrp_off[0]*v[0]+asrp_off[1]*v[1]+asrp_off[2]*v[2]) < 0: ecl_neg += 1
        k1=acc(s); s2=[s[j]+0.5*dt*k1[j] for j in range(6)]; k2=acc(s2)
        s3=[s[j]+0.5*dt*k2[j] for j in range(6)]; k3=acc(s3)
        s4=[s[j]+dt*k3[j] for j in range(6)]; k4=acc(s4)
        s=[s[j]+(dt/6)*(k1[j]+2*k2[j]+2*k3[j]+k4[j]) for j in range(6)]
    sel = 100.0*ecl_neg/ecl_tot if ecl_tot else float("nan")
    return Wsrp_on, Wsrp_off, Wdrag, sel


print("Per-orbit specific work (J/kg) at anchor LTDN=12.266")
print("paper target: SRP_on ~ +790, drag ~ -500, net ~ +290 (gain); eclipse sel ~ 85.7%")
for SRP_DIR in ("sunline", "normal"):
    print(f"\n=== SRP force direction: {SRP_DIR} ===")
    for label, fn in (("out-of-plane", n_outplane), ("in-plane", n_inplane)):
        for pitch in (24.8, -24.8, 45.0, -35.3):
            globals()["SRP_DIR"] = SRP_DIR
            ws_on, ws_off, wd, sel = one_orbit_work(12.266, pitch, fn)
            print(f"  [{label:12s} pitch={pitch:+6.1f}] SRP_on={ws_on:+8.2f} SRP_off={ws_off:+8.2f} "
                  f"drag={wd:+8.2f} net_on={ws_on+wd:+8.2f} sel={sel:5.1f}%")
