"""
Figure 2 — LTDN x pitch heatmap of Delta a_max(14d) from the offline engine
(paper's exact model). Parallelized. Writes results/fig2/fig2_<alt>.npz and a PNG.

Usage: python runners/run_fig2_offline.py [alt_km] [n_ltdn] [n_pitch] [days] [dt]
"""
from __future__ import annotations
import os, sys
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from core.orbit_init import raan_from_ltdn

ALT=float(sys.argv[1]) if len(sys.argv)>1 else 800.0
NL=int(sys.argv[2]) if len(sys.argv)>2 else 25
NP=int(sys.argv[3]) if len(sys.argv)>3 else 25
DAYS=float(sys.argv[4]) if len(sys.argv)>4 else 14.0
DT=float(sys.argv[5]) if len(sys.argv)>5 else 60.0
INC=98.31 if ALT>=750 else 98.17

LTDNS=np.linspace(0.0, 24.0, NL)
PITCHES=np.linspace(0.0, 90.0, NP)


def one(args):
    i,j,ltdn,pitch=args
    raan=raan_from_ltdn(float(ltdn), JD_EPOCH)
    c=SailCase(altitude_km=ALT,inc_deg=INC,raan_deg=raan,pitch_deg=float(pitch),dt=DT)
    r=propagate(c,DAYS)
    return i,j,r.get("da_max",0.0)


def main():
    cells=[(i,j,LTDNS[i],PITCHES[j]) for i in range(NL) for j in range(NP)]
    Z=np.zeros((NP,NL))
    with ProcessPoolExecutor(max_workers=8) as ex:
        for i,j,dm in ex.map(one, cells):
            Z[j,i]=dm
    outdir=os.path.join(_ROOT,"results","fig2"); os.makedirs(outdir,exist_ok=True)
    np.savez(os.path.join(outdir,f"fig2_{int(ALT)}.npz"), Z=Z, ltdn=LTDNS, pitch=PITCHES, alt=ALT)
    npos=int((Z>0.05).sum()); peak=np.unravel_index(np.argmax(Z),Z.shape)
    print(f"alt={ALT:.0f} km: peak da_max={Z.max():.2f} km at LTDN={LTDNS[peak[1]]:.2f} h, "
          f"pitch={PITCHES[peak[0]]:.1f} deg; positive cells {npos}/{Z.size} ({100*npos/Z.size:.1f}%)")
    # plot
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,5))
    im=ax.pcolormesh(LTDNS,PITCHES,Z,shading="auto",cmap="RdBu_r",
                     vmin=-max(1.0,Z.max()),vmax=max(1.0,Z.max()))
    ax.set_xlabel("LTDN [h]"); ax.set_ylabel("sail pitch [deg]")
    ax.set_title(f"Fig 2 (offline): $\\Delta a_{{max,14d}}$ [km] at {int(ALT)} km")
    ax.plot(12.266,24.8,"k*",ms=13,label="paper anchor (12.27h, 24.8°)")
    ax.legend(loc="upper right",fontsize=8)
    fig.colorbar(im,ax=ax,label="$\\Delta a_{max}$ [km]")
    pdir=os.path.join(_ROOT,"reproduced_figures"); os.makedirs(pdir,exist_ok=True)
    out=os.path.join(pdir,f"fig2_heatmap_{int(ALT)}km.png")
    fig.tight_layout(); fig.savefig(out,dpi=140); print("wrote",out)


if __name__=="__main__":
    main()
