"""
Goal-2 validation: cross-validate the open-source propagator against STK Astrogator.

Configuration where the result is attitude-independent (clean apples-to-apples):
  J2 gravity + spherical US-1976 drag, NO SRP, A/m = 10 m^2/kg, Cd = 2.2.
Compares the 14-day mean semi-major-axis decay Delta a(t) at 700 and 800 km.
Also a two-body/J2-only sanity case (mean SMA must be ~constant in both).

Writes reproduced_figures/validation_vs_stk.png and prints agreement metrics.
"""
from __future__ import annotations
import os, sys, math
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from core.orbit_init import raan_from_ltdn

EPOCH="1 Jan 2026 12:00:00.000"; DAYS=14.0; RE=6378.1363
RAAN=raan_from_ltdn(14.0, JD_EPOCH); PITCH=34.0


def _orbit_average(t, a, period):
    """Centered moving average over one orbital period (full windows only) ->
    energy-based mean SMA, removing the J2 short-period. Returns (t_trim, a_mean)."""
    dt = t[1]-t[0]; w = max(1, int(round(period/dt)))
    if w >= len(a): return t, a
    kern = np.ones(w)/w
    am = np.convolve(a, kern, mode="valid")
    tt = t[(w-1)//2 : (w-1)//2 + len(am)]
    return tt, am


def stk_mean_a(root, alt, use_drag):
    """STK ENERGY-based mean SMA: osculating Classical-Elements SMA, orbit-averaged.
    (Brouwer-Lyddane mean SMA is unreliable under drag — it is a conservative-theory
    mean — so we use the physically meaningful energy-based mean instead.)"""
    inc=98.31 if alt>=750 else 98.17
    n=(1.0,0.0,0.0)  # arbitrary; drag is spherical (attitude-independent), no SRP
    c=RunCase(name=f"val{int(alt)}",altitude_km=alt,inc_deg=inc,raan_deg=RAAN,
              sma_km=RE+alt,ecc=1e-4,sail_normal_eci=n,epoch_iso=EPOCH,
              duration_sec=DAYS*86400.0,step_sec=60.0,sail=SailParams())
    sat,drv=build_satellite(root,c,sat_name="Val",use_drag=use_drag,use_srp=False,
                            drag_model="spherical")
    run_mcs(drv)
    stop=_add_seconds_to_iso(EPOCH,DAYS*86400.0)
    grp=sat.DataProviders.Item("Classical Elements").Group.Item("ICRF")
    ds=grp.ExecElements(EPOCH,stop,60.0,["Time","Semi-major Axis"])
    a=None
    for i in range(ds.DataSets.Count):
        if ds.DataSets.Item(i).ElementName=="Semi-major Axis":
            a=np.array(ds.DataSets.Item(i).GetValues())
    t=np.arange(len(a))*60.0
    period=2*math.pi*math.sqrt((RE+alt)**3*1e9/3.986004418e14)  # km->m in a^3
    return _orbit_average(t,a,period)


def off_mean_a(alt, use_drag):
    inc=98.31 if alt>=750 else 98.17
    c=SailCase(altitude_km=alt,inc_deg=inc,raan_deg=RAAN,pitch_deg=PITCH,ecc=1e-4,
               use_srp=False,drag_mode="spherical",dt=30.0)
    # if no drag, temporarily zero it via cd=0
    if not use_drag: c.cd=0.0
    r=propagate(c,DAYS)
    return r["node_t"], r["node_a"]


def compare(root, alt, use_drag, label):
    ts,as_=stk_mean_a(root,alt,use_drag)
    to,ao=off_mean_a(alt,use_drag)
    da_stk=as_-as_[0]; da_off=ao-ao[0]
    # interpolate STK onto offline node times
    da_stk_i=np.interp(to,ts,da_stk)
    diff=da_off-da_stk_i
    print(f"[{label}] alt={alt:.0f} drag={use_drag}: "
          f"Delta a 14d  STK={da_stk[-1]:+.3f} km  offline={da_off[-1]:+.3f} km  "
          f"max|diff|={np.max(np.abs(diff)):.4f} km  rms={np.sqrt(np.mean(diff**2)):.4f} km "
          f"(offset a0: STK {as_[0]:.2f} vs off-node {ao[0]:.2f})")
    return dict(alt=alt,ts=ts,da_stk=da_stk,to=to,da_off=da_off,diff=diff,label=label)


def main():
    app=STKEngine.StartApplication(noGraphics=True); root=app.NewObjectRoot()
    root.NewScenario("Validation")
    res=[]
    try:
        res.append(compare(root,700.0,True,"J2+drag 700"))
        res.append(compare(root,800.0,True,"J2+drag 800"))
        res.append(compare(root,700.0,False,"J2-only 700 (sanity)"))
    finally:
        app.ShutDown()
    fig,axes=plt.subplots(1,2,figsize=(11,4.3))
    for r in res[:2]:
        axes[0].plot(r["ts"]/86400,r["da_stk"],lw=1.8,label=f"STK {int(r['alt'])} km")
        axes[0].plot(r["to"]/86400,r["da_off"],"--",lw=1.4,label=f"open-source {int(r['alt'])} km")
        axes[1].plot(r["to"]/86400,r["diff"],lw=1.4,label=f"{int(r['alt'])} km")
    axes[0].set_xlabel("time [days]"); axes[0].set_ylabel("$\\Delta a$ (mean) [km]")
    axes[0].set_title("J2 + spherical US-1976 drag: open-source vs STK",fontsize=9); axes[0].legend(fontsize=8)
    axes[1].axhline(0,color="k",lw=0.5); axes[1].set_xlabel("time [days]")
    axes[1].set_ylabel("$\\Delta a$ difference (open-source $-$ STK) [km]")
    axes[1].set_title("residual",fontsize=9); axes[1].legend(fontsize=8)
    fig.suptitle("Validation of the open-source propagator against STK Astrogator",fontsize=10)
    fig.tight_layout(); p=os.path.join(_ROOT,"reproduced_figures","validation_vs_stk.png")
    fig.savefig(p,dpi=140); print("wrote",p)


if __name__=="__main__":
    main()
