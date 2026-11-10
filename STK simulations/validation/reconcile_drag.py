"""
Pin down the ~10x drag discrepancy between the offline propagator and STK for the
spherical US-1976 case: read STK's effective density, drag area, Cd, mass, and
speed at epoch, compute STK's implied drag acceleration, and compare to offline.
"""
from __future__ import annotations
import os, sys, math
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.orbit_init import raan_from_ltdn
from core.offline_propagator import JD_EPOCH
from plugins.flatplate_drag_hpop import density_us1976_kg_m3

EPOCH="1 Jan 2026 12:00:00.000"; RE=6378.1363
RAAN=raan_from_ltdn(14.0, JD_EPOCH)


def av(sat, group, elem):
    stop=_add_seconds_to_iso(EPOCH,600.0)
    g=sat.DataProviders.Item("Astrogator Values").Group.Item(group)
    ds=g.ExecElements(EPOCH,stop,60.0,["Time",elem])
    for i in range(ds.DataSets.Count):
        if ds.DataSets.Item(i).ElementName==elem: return list(ds.DataSets.Item(i).GetValues())[0]
    return None


def main():
    app=STKEngine.StartApplication(noGraphics=True); root=app.NewObjectRoot()
    try:
        root.NewScenario("Recon")
        c=RunCase(name="recon",altitude_km=700.0,inc_deg=98.17,raan_deg=RAAN,sma_km=RE+700,
                  ecc=1e-4,sail_normal_eci=(1.0,0.0,0.0),epoch_iso=EPOCH,
                  duration_sec=600.0,step_sec=60.0,sail=SailParams())
        sat,drv=build_satellite(root,c,sat_name="R",use_drag=True,use_srp=False,drag_model="spherical")
        # read effective spacecraft params BEFORE run
        init=drv.MainSequence.Item("Initial State"); sp=init.SpacecraftParameters
        print(f"SpacecraftParameters set: DryMass={sp.DryMass} DragArea={sp.DragArea} Cd={sp.Cd}")
        run_mcs(drv)
        dens_stk=av(sat,"Environment","AtmosDensity")     # units? (km-based -> kg/km^3)
        darea=av(sat,"Spacecraft Properties","DragArea")
        cd=av(sat,"Spacecraft Properties","Cd")
        # speed at epoch
        stop=_add_seconds_to_iso(EPOCH,120.0)
        gv=sat.DataProviders.Item("Cartesian Velocity").Group.Item("ICRF")
        dv=gv.ExecElements(EPOCH,stop,60.0,["Time","x","y","z"])
        vx=vy=vz=0.0
        for i in range(dv.DataSets.Count):
            nm=dv.DataSets.Item(i).ElementName; val=list(dv.DataSets.Item(i).GetValues())[0]
            if nm=="x": vx=val
            elif nm=="y": vy=val
            elif nm=="z": vz=val
        v_kms=math.sqrt(vx*vx+vy*vy+vz*vz); v_ms=v_kms*1000.0
        mass=sp.DryMass
        # STK density interpretation options
        dens_kgm3_A=dens_stk*1e-9   # if reported in kg/km^3
        dens_kgm3_B=dens_stk        # if reported in kg/m^3
        offline_dens=density_us1976_kg_m3(700e3)
        print(f"\nSTK AtmosDensity raw = {dens_stk:.4e}")
        print(f"  -> as kg/km^3: {dens_kgm3_A:.4e} kg/m^3 ; as kg/m^3: {dens_kgm3_B:.4e}")
        print(f"offline US-1976 density @700km = {offline_dens:.4e} kg/m^3")
        print(f"STK DragArea={darea} m^2  Cd={cd}  DryMass={mass} kg  v={v_ms:.1f} m/s")
        # implied drag accel using STK density (option A) and STK area/cd/mass
        for lbl,rho in (("STK dens as kg/km^3",dens_kgm3_A),("STK dens as kg/m^3",dens_kgm3_B)):
            a_stk=0.5*cd*rho*v_ms*v_ms*(darea/mass)
            print(f"  implied a_drag ({lbl}) = {a_stk:.4e} m/s^2")
        a_off=0.5*2.2*offline_dens*v_ms*v_ms*(100.0/10.0)
        print(f"  offline a_drag = {a_off:.4e} m/s^2")
    finally:
        app.ShutDown()


if __name__=="__main__":
    main()
