"""
Measure STK's actually-applied N-plate SRP acceleration at the anchor and compare
to the offline N-plate reference, to decide whether STK's SRP force is zero
(config bug) or present-but-doing-no-net-work (geometry).

Method: SRP-only total accel minus J2-only total accel, sampled over the first
orbit (before the two trajectories diverge) = STK's SRP accel vector.
"""
from __future__ import annotations
import math, os, sys
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from agi.stk13 import stkobjects as o
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal
from plugins.flatplate_srp_hpop import nplate_srp_acceleration_eci, NPLATE_CALIBRATION_PRIMARY, AU_M, cos_alpha

EPOCH="1 Jan 2026 12:00:00.000"; DUR=6000.0  # ~1 orbit
PITCH=float(sys.argv[1]) if len(sys.argv)>1 else 24.8
JD0=julian_date_from_ymdhms(2026,1,1,12,0,0)
SUN=sun_direction_eci(JD0); RSUN=(SUN[0]*AU_M,SUN[1]*AU_M,SUN[2]*AU_M)
N=inertial_sail_normal(SUN,285.5,98.17,PITCH,0.0)
print(f"pitch={PITCH} sail_normal_eci={N}  n.sun={sum(N[i]*SUN[i] for i in range(3)):.4f}")


def case(use_drag,use_srp):
    return RunCase(name=f"m_{use_drag}_{use_srp}",altitude_km=700.0,inc_deg=98.17,raan_deg=285.5,
                   sma_km=7078.137,ecc=1e-4,sail_normal_eci=N,epoch_iso=EPOCH,
                   duration_sec=DUR,step_sec=10.0,sail=SailParams())


def series(sat,prov,elems):
    stop=_add_seconds_to_iso(EPOCH,DUR)
    grp=sat.DataProviders.Item(prov).Group.Item("ICRF")
    ds=grp.ExecElements(EPOCH,stop,10.0,["Time"]+elems)
    out={}
    for i in range(ds.DataSets.Count):
        d=ds.DataSets.Item(i); out[d.ElementName]=list(d.GetValues())
    return out


def main():
    app=STKEngine.StartApplication(noGraphics=True); root=app.NewObjectRoot()
    try:
        root.NewScenario("MeasSRP")
        # SRP-only
        sat,drv=build_satellite(root,case(False,True),sat_name="Sat",use_drag=False,use_srp=True)
        run_mcs(drv)
        a_srp=series(sat,"Cartesian Acceleration",["x","y","z"])
        pos=series(sat,"Cartesian Position",["x","y","z"])
        # J2-only
        sat2,drv2=build_satellite(root,case(False,False),sat_name="Sat2",use_drag=False,use_srp=False)
        run_mcs(drv2)
        a_j2=series(sat2,"Cartesian Acceleration",["x","y","z"])
        n=min(len(a_srp["x"]),len(a_j2["x"]))
        print(f"{'t[s]':>6} {'|a_SRP|_STK':>12} {'|a_SRP|_offline':>16} {'cosA':>7} {'ecl?':>5}")
        maxstk=0.0
        for i in range(0,min(n,40),4):
            dax=a_srp["x"][i]-a_j2["x"][i]; day=a_srp["y"][i]-a_j2["y"][i]; daz=a_srp["z"][i]-a_j2["z"][i]
            mag_stk=math.sqrt(dax*dax+day*day+daz*daz)/1000.0  # km/s^2 -> ... STK accel units? check
            # STK Cartesian Acceleration is km/s^2; convert to m/s^2:
            mag_stk_ms2=math.sqrt(dax*dax+day*day+daz*daz)  # will interpret below
            r=(pos["x"][i]*1000.0,pos["y"][i]*1000.0,pos["z"][i]*1000.0)  # km->m
            a_off=nplate_srp_acceleration_eci(r,RSUN,N,100.0,10.0,*NPLATE_CALIBRATION_PRIMARY)
            mag_off=math.sqrt(sum(c*c for c in a_off))
            rhat=tuple((r[j]-RSUN[j]) for j in range(3)); rn=math.sqrt(sum(c*c for c in rhat)); rhat=tuple(c/rn for c in rhat)
            ca=cos_alpha(N,rhat)
            from plugins.flatplate_srp_hpop import in_umbra_cylindrical
            ecl=in_umbra_cylindrical(r,RSUN)
            maxstk=max(maxstk,mag_stk_ms2)
            print(f"{i*10:>6} {mag_stk_ms2:>12.4e} {mag_off:>16.4e} {ca:>7.3f} {str(ecl):>5}")
        print(f"\nmax |a_SRP|_STK over sampled window = {maxstk:.4e}  (units: STK accel diff)")
        print("offline peak expected ~6.4e-5 m/s^2 at cosA~0.9 (lit).")
        print("NOTE: if STK Cartesian Acceleration is in km/s^2, multiply STK col by 1000 for m/s^2.")
    finally:
        app.ShutDown()


if __name__=="__main__":
    main()
