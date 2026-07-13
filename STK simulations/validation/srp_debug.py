"""
Debug why STK's N-plate SRP applies ~zero force. Tests, at pitch=0 (max SRP):
  A) N-plate SRP with the .nplate file at its normal (space-containing) path
  B) N-plate SRP with the .nplate file copied to a space-free temp path
  C) Spherical SRP (Cr=1.7, area 100) as a control
Dumps each SRP function's config, and measures the applied SRP accel via
(SRP-only total accel) - (J2-only total accel) over the first minutes.
"""
from __future__ import annotations
import math, os, sys, tempfile, shutil
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from agi.stk13 import stkobjects as o
from agi.stk13.stkobjects import astrogator as astro
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs, _get_func, set_unit_prefs
from core.nplate_files import write_srp_nplate_file
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal, normal_to_quaternion_eci
from plugins.flatplate_srp_hpop import AU_M

EPOCH="1 Jan 2026 12:00:00.000"; DUR=1200.0
JD0=julian_date_from_ymdhms(2026,1,1,12,0,0)
SUN=sun_direction_eci(JD0)
N=inertial_sail_normal(SUN,285.5,98.17,0.0,0.0)   # pitch 0 -> n == sun, max SRP


def mkcase(name,use_srp):
    c=RunCase(name=name,altitude_km=700.0,inc_deg=98.17,raan_deg=285.5,sma_km=7078.137,
              ecc=1e-4,sail_normal_eci=N,epoch_iso=EPOCH,duration_sec=DUR,step_sec=10.0,
              sail=SailParams())
    return c


def accel_series(sat):
    stop=_add_seconds_to_iso(EPOCH,DUR)
    grp=sat.DataProviders.Item("Cartesian Acceleration").Group.Item("ICRF")
    ds=grp.ExecElements(EPOCH,stop,10.0,["Time","x","y","z"])
    d={}
    for i in range(ds.DataSets.Count):
        e=ds.DataSets.Item(i); d[e.ElementName]=list(e.GetValues())
    return d


def measure(root, srp_file, label, spherical=False):
    # SRP-only
    c=mkcase(f"dbg_{label}", True)
    sat,drv=build_satellite(root,c,sat_name="Sat",use_drag=False,use_srp=True,
                            nplate_dir=os.path.dirname(srp_file) if srp_file else None)
    # override the SRP function config for this test
    props=root.CurrentScenario.ComponentDirectory.GetComponents(2).GetFolder("Propagators")
    pf=props.Item("SailProp_Sat").PropagatorFunctions
    srp=_get_func(pf,"NPlate SRP")
    if spherical:
        pass  # handled by a separate control below
    else:
        srp.NPlateDefinitionFile=srp_file
    # dump SRP config
    print(f"\n--- {label} ---")
    for a in ("NPlateDefinitionFile","MeanFlux","Luminosity","SolarForceMethod","ShadowModel"):
        try: print(f"   SRP.{a} = {getattr(srp,a)!r}")
        except Exception as e: print(f"   SRP.{a}: {e}")
    try:
        nsp=srp.NPlateStochasticParameters
        print(f"   NPlateStochasticParameters.Count = {nsp.Count}  (>=1 groups => file parsed)")
        for i in range(nsp.Count): print(f"      group[{i}] = {nsp.Item(i).Name!r}")
    except Exception as e:
        print(f"   NPlateStochasticParameters: {e}")
    print(f"   file exists = {os.path.exists(srp_file)}  path={srp_file}")
    run_mcs(drv)
    asrp=accel_series(sat)
    # J2-only reference
    sat2,drv2=build_satellite(root,mkcase(f"dbgj2_{label}",False),sat_name="Sat2",
                              use_drag=False,use_srp=False)
    run_mcs(drv2)
    aj2=accel_series(sat2)
    n=min(len(asrp["x"]),len(aj2["x"]))
    mx=0.0
    for i in range(min(n,30)):
        dv=math.sqrt((asrp["x"][i]-aj2["x"][i])**2+(asrp["y"][i]-aj2["y"][i])**2+(asrp["z"][i]-aj2["z"][i])**2)
        mx=max(mx,dv)
    print(f"   >>> max |a_SRP|_STK (accel units) = {mx:.4e}   (expect ~7.75e-5 m/s^2 or 7.75e-8 km/s^2)")


def main():
    app=STKEngine.StartApplication(noGraphics=True); root=app.NewObjectRoot()
    try:
        root.NewScenario("SrpDbg"); set_unit_prefs(root)
        q=normal_to_quaternion_eci(N); print(f"pitch0 normal={N} quat={q}")
        # A) normal path (with spaces)
        f_spaces=write_srp_nplate_file(os.path.join(_ROOT,"results","_nplate","dbg_srp.nplate"),100.0)
        measure(root, f_spaces, "A: space path")
        # B) space-free temp path
        tmp=os.path.join(tempfile.gettempdir(),"nplate_nospace")
        os.makedirs(tmp,exist_ok=True)
        f_nospace=write_srp_nplate_file(os.path.join(tmp,"sail_srp.nplate"),100.0)
        measure(root, f_nospace, "B: no-space path")
        # C) spherical SRP control: full build, then swap NPlate SRP -> Spherical SRP
        print("\n--- C: spherical SRP control (Cr=1.7, area=100 via SpacecraftParameters) ---")
        c=mkcase("dbg_sph", True)
        sat,drv=build_satellite(root,c,sat_name="Sat",use_drag=False,use_srp=True)
        props=root.CurrentScenario.ComponentDirectory.GetComponents(2).GetFolder("Propagators")
        pf=props.Item("SailProp_Sat").PropagatorFunctions
        try: pf.Remove("NPlate SRP")
        except Exception as e: print("   remove NPlate:",e)
        pf.Add("Spherical SRP"); sp=_get_func(pf,"Spherical SRP")
        print(f"   Spherical MeanFlux={getattr(sp,'MeanFlux',None)!r} "
              f"SolarForceMethod={getattr(sp,'SolarForceMethod',None)!r}")
        # ensure SpacecraftParameters carry Cr/area
        init=drv.MainSequence.Item("Initial State"); spar=init.SpacecraftParameters
        print(f"   SpacecraftParameters Cr={spar.Cr} SRPArea={spar.SolarRadiationPressureArea} DryMass={spar.DryMass}")
        run_mcs(drv)
        asrp=accel_series(sat)
        sat2,drv2=build_satellite(root,mkcase("dbgj2_sph",False),sat_name="Sat2",use_drag=False,use_srp=False)
        run_mcs(drv2); aj2=accel_series(sat2)
        n=min(len(asrp["x"]),len(aj2["x"])); mx=0.0
        for i in range(min(n,30)):
            dv=math.sqrt((asrp["x"][i]-aj2["x"][i])**2+(asrp["y"][i]-aj2["y"][i])**2+(asrp["z"][i]-aj2["z"][i])**2)
            mx=max(mx,dv)
        print(f"   >>> max |a_SRP_spherical|_STK = {mx:.4e}  (expect ~7.75e-5 m/s^2 or 7.75e-8 km/s^2)")
    finally:
        app.ShutDown()


if __name__=="__main__":
    main()
