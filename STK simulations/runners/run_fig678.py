"""
Fig 6 (roll sensitivity), Fig 7 (atmospheric-density sensitivity via Cd scaling),
Fig 8 (area-to-mass sensitivity) from the offline engine, at 700 and 800 km, at
the reproduced gain-case LTDN/pitch. Honest qualitative validation: shows the
sensitivity TRENDS (peak at zero roll, gain rising as density falls, gain rising
with A/m) even though absolute magnitudes are lower than the paper and 700 km is
drag-marginal.
"""
from __future__ import annotations
import os, sys, math
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from core.orbit_init import raan_from_ltdn

PDIR=os.path.join(_ROOT,"reproduced_figures"); os.makedirs(PDIR,exist_ok=True)
LTDN_GAIN=14.0; PITCH_GAIN=34.0; DT=60.0; DAYS=14.0


def _case(alt, **kw):
    inc=98.31 if alt>=750 else 98.17
    return SailCase(altitude_km=alt,inc_deg=inc,raan_deg=raan_from_ltdn(LTDN_GAIN,JD_EPOCH),
                    pitch_deg=PITCH_GAIN,dt=DT,**kw)


def _damax(args):
    kind,alt,x=args
    if kind=="roll":   c=_case(alt,roll_deg=x)
    elif kind=="dens": c=_case(alt,cd_scale=x)
    elif kind=="amr":  c=_case(alt,area_m2=x*10.0)   # A/m = area/mass, mass=10 -> area=10*(A/m)
    r=propagate(c,DAYS)
    return kind,alt,x,r.get("da_max",0.0)


def main():
    rolls=list(np.linspace(-45,45,19))
    dens=[0.25,0.5,1.0,2.0,4.0]
    amrs=[2.5,5,7.5,10,12.5,15,17.5,20,22.5]
    jobs=([("roll",a,x) for a in (700,800) for x in rolls]
          +[("dens",a,x) for a in (700,800) for x in dens]
          +[("amr",a,x) for a in (700,800) for x in amrs])
    res={}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for kind,alt,x,dm in ex.map(_damax,jobs):
            res.setdefault((kind,alt),[]).append((x,dm))
    for k in res: res[k].sort()

    def plot(kind,xlabel,title,fname,logx=False):
        fig,ax=plt.subplots(figsize=(7,4.3))
        for alt,c in ((700,"C3"),(800,"C0")):
            xy=res[(kind,alt)]; xs=[p[0] for p in xy]; ys=[p[1] for p in xy]
            ax.plot(xs,ys,"o-",color=c,lw=1.5,ms=4,label=f"{alt} km")
        if logx: ax.set_xscale("log")
        ax.axhline(0,color="k",lw=0.5); ax.set_xlabel(xlabel); ax.set_ylabel("$\\Delta a_{max,14d}$ [km]")
        ax.set_title(title,fontsize=9); ax.legend(fontsize=8)
        fig.tight_layout(); p=os.path.join(PDIR,fname); fig.savefig(p,dpi=140); plt.close(fig); print("wrote",p)

    plot("roll","roll offset [deg]",
         "Fig 6 (offline): roll sensitivity (peak at zero roll; 800 km broader)","fig6_roll.png")
    plot("dens","atmospheric density factor",
         "Fig 7 (offline): density sensitivity (gain rises as density falls)","fig7_density.png",logx=True)
    plot("amr","A/m [m$^2$/kg]",
         "Fig 8 (offline): area-to-mass sensitivity","fig8_amr.png")
    # print the numeric tables
    for kind in ("roll","dens","amr"):
        for alt in (700,800):
            print(f"{kind} {alt}km:", [(round(x,3),round(y,2)) for x,y in res[(kind,alt)]])


if __name__=="__main__":
    main()
