"""
Fig 4 (per-orbit SRP specific power with eclipse shading) and Fig 5 (cumulative
SRP work, eclipse ON vs OFF) for the reproduced gain case, showing that eclipse
gates out the negative-work arc.
"""
from __future__ import annotations
import os, sys
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from core.orbit_init import raan_from_ltdn

PDIR=os.path.join(_ROOT,"reproduced_figures"); os.makedirs(PDIR,exist_ok=True)
GAIN=dict(altitude_km=800.0,inc_deg=98.31,raan_deg=raan_from_ltdn(14.0,JD_EPOCH),pitch_deg=34.0)
ORBIT_S=6200.0  # ~1 orbit at 800 km


def one_orbit(disable_eclipse):
    c=SailCase(disable_eclipse=disable_eclipse,dt=5.0,**GAIN)
    r=propagate(c,ORBIT_S/86400.0,want_forces=True)
    return r["forces"]  # columns: t, P_srp, P_drag, cos_alpha, eclipse


def main():
    F_on=one_orbit(False); F_off=one_orbit(True)
    t=F_on[:,0]/60.0; Psrp_on=F_on[:,1]; Psrp_off=F_off[:,1]; ecl=F_on[:,4]
    # sign-selectivity: fraction of eclipsed samples whose no-eclipse SRP power < 0
    m=ecl>0.5
    sel=100.0*np.mean(Psrp_off[m]<0) if m.any() else float("nan")

    # Fig 4: SRP power vs time, eclipse shaded
    fig,ax=plt.subplots(figsize=(8,4.3))
    ax.plot(t,Psrp_off,"C1--",lw=1.2,label="SRP power, no-eclipse reference")
    ax.plot(t,Psrp_on,"C0",lw=1.6,label="SRP power, eclipse ON")
    ax.axhline(0,color="k",lw=0.5)
    inb=False
    for i,f in enumerate(ecl):
        if f>0.5 and not inb: s=t[i]; inb=True
        if (f<=0.5 or i==len(ecl)-1) and inb: ax.axvspan(s,t[i],color="0.85",zorder=0); inb=False
    ax.set_xlabel("time [min]"); ax.set_ylabel("SRP specific power $a_{SRP}\\cdot v$ [W/kg]")
    ax.set_title(f"Fig 4 (offline): eclipse (shaded) removes the negative-work arc "
                 f"({sel:.0f}% of eclipsed samples are would-be negative)",fontsize=8.5)
    ax.legend(fontsize=8,loc="best"); fig.tight_layout()
    p=os.path.join(PDIR,"fig4_srp_power.png"); fig.savefig(p,dpi=140); plt.close(fig); print("wrote",p)

    # Fig 5: cumulative SRP work, eclipse ON vs OFF
    def cum(F):
        tt=F[:,0]; P=F[:,1]; W=np.zeros_like(P)
        W[1:]=np.cumsum(0.5*(P[1:]+P[:-1])*np.diff(tt)); return W
    W_on=cum(F_on); W_off=cum(F_off)
    fig,ax=plt.subplots(figsize=(8,4.3))
    ax.plot(t,W_on,"C0",lw=1.6,label=f"eclipse ON  (end {W_on[-1]:+.0f} J/kg)")
    ax.plot(t,W_off,"C1--",lw=1.4,label=f"no-eclipse  (end {W_off[-1]:+.0f} J/kg)")
    ax.axhline(0,color="k",lw=0.5)
    ax.set_xlabel("time [min]"); ax.set_ylabel("cumulative SRP work [J/kg]")
    ax.set_title("Fig 5 (offline): one-orbit cumulative SRP work — eclipse flips the sign to net positive",fontsize=8.5)
    ax.legend(fontsize=8,loc="best"); fig.tight_layout()
    p=os.path.join(PDIR,"fig5_cum_work.png"); fig.savefig(p,dpi=140); plt.close(fig); print("wrote",p)
    print(f"selectivity={sel:.1f}%  W_on_end={W_on[-1]:+.1f}  W_off_end={W_off[-1]:+.1f} J/kg")


if __name__=="__main__":
    main()
