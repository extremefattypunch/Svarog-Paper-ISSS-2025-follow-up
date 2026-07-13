"""
Read STK's EFFECTIVE spacecraft/environment values during an N-plate propagation:
- Spacecraft Properties: SRPArea, RadPressureCoefficient, DragArea, Cd (STK derives
  these from the N-plate config -> tells us if the plate file is applied correctly).
- Environment: AtmosDensity (STK's US-1976 density at altitude -> drag magnitude).
"""
from __future__ import annotations
import os, sys
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal
from plugins.flatplate_drag_hpop import density_us1976_kg_m3

EPOCH="1 Jan 2026 12:00:00.000"; DUR=6000.0
JD0=julian_date_from_ymdhms(2026,1,1,12,0,0)
N=inertial_sail_normal(sun_direction_eci(JD0),285.5,98.17,24.8,0.0)


def av_series(sat, group, elems):
    stop=_add_seconds_to_iso(EPOCH,DUR)
    g=sat.DataProviders.Item("Astrogator Values").Group.Item(group)
    ds=g.ExecElements(EPOCH,stop,60.0,["Time"]+elems)
    out={}
    for i in range(ds.DataSets.Count):
        d=ds.DataSets.Item(i); out[d.ElementName]=list(d.GetValues())
    return out


def main():
    app=STKEngine.StartApplication(noGraphics=True); root=app.NewObjectRoot()
    try:
        root.NewScenario("Eff")
        c=RunCase(name="eff",altitude_km=700.0,inc_deg=98.17,raan_deg=285.5,sma_km=7078.137,
                  ecc=1e-4,sail_normal_eci=N,epoch_iso=EPOCH,duration_sec=DUR,step_sec=60.0,
                  sail=SailParams())
        sat,drv=build_satellite(root,c,sat_name="Sat",use_drag=True,use_srp=True)
        run_mcs(drv)
        sp=av_series(sat,"Spacecraft Properties",
                     ["SRPArea","RadPressureCoefficient","RadPressureArea","DragArea","Cd","Cr"])
        env=av_series(sat,"Environment",["AtmosDensity"])
        print("STK effective spacecraft properties (N-plate build):")
        for k in ("SRPArea","RadPressureCoefficient","RadPressureArea","DragArea","Cd","Cr"):
            v=sp.get(k,[])
            if v:
                print(f"   {k:22s} first={v[0]!r}  min={min(v):.4g} max={max(v):.4g}")
        dens=env.get("AtmosDensity",[])
        if dens:
            print(f"\nSTK AtmosDensity @~700 km: first={dens[0]:.4e} kg/m^3 "
                  f"(min {min(dens):.4e} max {max(dens):.4e})")
        print(f"paper/offline US-1976 density @700 km = {density_us1976_kg_m3(700e3):.4e} kg/m^3")
    finally:
        app.ShutDown()


if __name__=="__main__":
    main()
