"""
Fig 3 (eclipse causality) + Fig 9 (long-horizon element evolution) from the
offline engine. Features a representative GAIN case (800 km, in the reproduced
lobe) and the paper's 700 km anchor (drag-dominated) side by side, per the
honest qualitative-validation plan.
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

# representative reproduced GAIN case (from the 800 km Fig-2 lobe) and paper anchor
GAIN = dict(altitude_km=800.0, inc_deg=98.31, raan_deg=raan_from_ltdn(14.0,JD_EPOCH),
            pitch_deg=34.0, label="gain case (800 km, LTDN 14 h, pitch 34°)")
ANCHOR = dict(altitude_km=700.0, inc_deg=98.17, raan_deg=285.5,
              pitch_deg=24.8, label="paper anchor (700 km, LTDN 12.27 h, pitch 24.8°)")


def fig3():
    """Eclipse-on vs eclipse-off mean SMA, for the gain case and the anchor."""
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),sharey=False)
    for ax,cfg in zip(axes,(GAIN,ANCHOR)):
        for ecl_off,style,lab in ((False,"-","eclipse ON"),(True,"--","eclipse OFF")):
            c=SailCase(altitude_km=cfg["altitude_km"],inc_deg=cfg["inc_deg"],
                       raan_deg=cfg["raan_deg"],pitch_deg=cfg["pitch_deg"],
                       disable_eclipse=ecl_off,dt=30.0)
            r=propagate(c,30.0)
            t=r["node_t"]/86400.0; da=r["node_a"]-r["node_a"][0]
            ax.plot(t,da,style,lw=1.6,label=lab)
        ax.axhline(0,color="k",lw=0.5); ax.set_xlabel("time [days]")
        ax.set_ylabel("$\\Delta a$ (mean) [km]"); ax.set_title(cfg["label"],fontsize=9)
        ax.legend(fontsize=8)
    fig.suptitle("Fig 3 (offline): eclipse causally enables gain (sign of $\\Delta a$ flips)",fontsize=10)
    fig.tight_layout(); p=os.path.join(PDIR,"fig3_eclipse_causality.png")
    fig.savefig(p,dpi=140); plt.close(fig); print("wrote",p)


def _clip_reentry(r, hp_min=120.0):
    """Truncate the series at reentry (perigee altitude below hp_min)."""
    hp = r["node_hp"]
    idx = np.argmax(hp < hp_min) if np.any(hp < hp_min) else len(hp)
    if idx == 0 and not (len(hp) and hp[0] < hp_min):
        idx = len(hp)
    sl = slice(0, max(1, idx))
    return {k: (v[sl] if isinstance(v, np.ndarray) and v.ndim == 1 and len(v) == len(hp) else v)
            for k, v in r.items()}


def fig9():
    """75-day element evolution: gain-case transient + both-case apogee/perigee/e."""
    data = {}
    for name, cfg in (("GAIN", GAIN), ("ANCHOR", ANCHOR)):
        c=SailCase(altitude_km=cfg["altitude_km"],inc_deg=cfg["inc_deg"],
                   raan_deg=cfg["raan_deg"],pitch_deg=cfg["pitch_deg"],dt=30.0)
        data[name]=_clip_reentry(propagate(c,75.0))

    fig,axes=plt.subplots(2,2,figsize=(11,7))
    # (0,0): Delta a for the GAIN case only (its transient; the anchor reenters off-scale)
    g=data["GAIN"]; tg=g["node_t"]/86400.0; dag=g["node_a"]-g["node_a"][0]
    axes[0,0].plot(tg,dag,"C0",lw=1.6,label=GAIN["label"])
    imax=int(np.argmax(g["node_a"]))
    axes[0,0].plot(tg[imax],dag[imax],"k*",ms=12,
                   label=f"peak $\\Delta a$={dag[imax]:+.1f} km @ day {tg[imax]:.0f}")
    axes[0,0].axhline(0,color="k",lw=0.5); axes[0,0].legend(fontsize=7,loc="best")
    axes[0,0].set_title("$\\Delta a$ (mean) — reproduced GAIN case (transient, self-limiting)",fontsize=8.5)
    # (0,1),(1,0),(1,1): both cases
    for name,color in (("GAIN","C0"),("ANCHOR","C3")):
        d=data[name]; t=d["node_t"]/86400.0
        axes[0,1].plot(t,d["node_ha"],color,lw=1.4,label=(GAIN if name=="GAIN" else ANCHOR)["label"])
        axes[1,0].plot(t,d["node_hp"],color,lw=1.4)
        axes[1,1].plot(t,d["node_e"],color,lw=1.4)
    for ax,ttl,yl in ((axes[0,0],None,"$\\Delta a$ [km]"),
                      (axes[0,1],"apogee altitude (both cases; anchor reenters ~day 36)","$h_a$ [km]"),
                      (axes[1,0],"perigee altitude","$h_p$ [km]"),
                      (axes[1,1],"eccentricity","e")):
        if ttl: ax.set_title(ttl,fontsize=8.5)
        ax.set_xlabel("time [days]"); ax.set_ylabel(yl)
    axes[0,1].legend(fontsize=7,loc="best")
    fig.suptitle("Fig 9 (offline): 75-day evolution — transient apogee pumping (800 km gain) vs drag reentry (700 km anchor)",fontsize=9.5)
    fig.tight_layout(); p=os.path.join(PDIR,"fig9_elements.png")
    fig.savefig(p,dpi=140); plt.close(fig); print("wrote",p)


if __name__=="__main__":
    fig9(); fig3()
