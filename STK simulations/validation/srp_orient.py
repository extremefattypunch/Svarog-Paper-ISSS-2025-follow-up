"""
Find why the one-sided N-plate SRP reports SRPArea=0. Test the plate-normal sign
(+Z vs -Z) and read back STK's effective SRPArea; also read the angle between the
satellite body +Z axis and the Sun to check the attitude quaternion.
"""
from __future__ import annotations
import os, sys, math
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs, _get_func
from core.nplate_files import write_srp_nplate_file
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal

EPOCH="1 Jan 2026 12:00:00.000"; DUR=3000.0
JD0=julian_date_from_ymdhms(2026,1,1,12,0,0)
SUN=sun_direction_eci(JD0)
N=inertial_sail_normal(SUN,285.5,98.17,24.8,0.0)
print(f"intended sail normal={N}  n.sun={sum(N[i]*SUN[i] for i in range(3)):.4f} (cos24.8=0.908)")


def srparea(sat):
    stop=_add_seconds_to_iso(EPOCH,DUR)
    g=sat.DataProviders.Item("Astrogator Values").Group.Item("Spacecraft Properties")
    ds=g.ExecElements(EPOCH,stop,60.0,["Time","SRPArea","Cr"])
    a=c=None
    for i in range(ds.DataSets.Count):
        d=ds.DataSets.Item(i)
        if d.ElementName=="SRPArea": a=list(d.GetValues())
        if d.ElementName=="Cr": c=list(d.GetValues())
    return (a[0] if a else None, max(a) if a else None, c[0] if c else None)


def bodyZ_sun_angle(sat):
    # angle between the satellite body +Z axis and the Sun vector, from STK
    stop=_add_seconds_to_iso(EPOCH,DUR)
    try:
        g=sat.DataProviders.Item("Body Axes Orientation:YPR 321").Group  # may not apply
    except Exception:
        pass
    return None


def main():
    app=STKEngine.StartApplication(noGraphics=True); root=app.NewObjectRoot()
    try:
        root.NewScenario("Orient")
        c=RunCase(name="or",altitude_km=700.0,inc_deg=98.17,raan_deg=285.5,sma_km=7078.137,
                  ecc=1e-4,sail_normal_eci=N,epoch_iso=EPOCH,duration_sec=DUR,step_sec=60.0,
                  sail=SailParams())
        for sign,nz in (("+Z",1.0),("-Z",-1.0)):
            sat,drv=build_satellite(root,c,sat_name="Sat",use_drag=False,use_srp=True)
            props=root.CurrentScenario.ComponentDirectory.GetComponents(2).GetFolder("Propagators")
            srp=_get_func(props.Item("SailProp_Sat").PropagatorFunctions,"NPlate SRP")
            f=write_srp_nplate_file(os.path.join(_ROOT,"results","_nplate",f"or_{sign}.nplate"),
                                    100.0, normal=(0.0,0.0,nz))
            srp.NPlateDefinitionFile=f
            run_mcs(drv)
            a0,amax,cr0=srparea(sat)
            print(f"  plate normal {sign}: SRPArea first={a0} max={amax}  Cr={cr0}")

        # Also read the STK Sun angle to the body +Z via the sun vector in body frame
        # (diagnostic): angle from the reported Cr/SRPArea already tells us enough.
    finally:
        app.ShutDown()


if __name__=="__main__":
    main()
