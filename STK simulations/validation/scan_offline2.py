"""
Clean (LTDN x pitch) gain scan using core.offline_propagator, to locate the gain
lobe and compare to the paper's Fig 2 (peak ~LTDN 12.27h, pitch 24.8; lobe LTDN
9-15h x pitch 0-43; ~10% of cells positive).
Usage: python validation/scan_offline2.py [days] [dt] [alt]
"""
from __future__ import annotations
import os, sys
_HERE=os.path.dirname(os.path.abspath(__file__)); _ROOT=os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0,_ROOT)
from concurrent.futures import ProcessPoolExecutor
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from core.orbit_init import raan_from_ltdn

DAYS=float(sys.argv[1]) if len(sys.argv)>1 else 14.0
DT=float(sys.argv[2]) if len(sys.argv)>2 else 60.0
ALT=float(sys.argv[3]) if len(sys.argv)>3 else 700.0
INC=98.31 if ALT>=750 else 98.17

LTDNS=[0,3,6,9,10.5,12.266,13.5,15,18,21]
PITCHES=[-45,-35,-24.8,-15,-5,0,5,15,24.8,35,45]


def one(args):
    ltdn,pitch=args
    raan=raan_from_ltdn(ltdn, JD_EPOCH)
    c=SailCase(altitude_km=ALT,inc_deg=INC,raan_deg=raan,pitch_deg=pitch,dt=DT)
    r=propagate(c,DAYS)
    return (ltdn,pitch,r.get("da_max",float("nan")),r.get("da_final",float("nan")))


def main():
    cells=[(l,p) for p in PITCHES for l in LTDNS]
    results={}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for ltdn,pitch,damax,dafin in ex.map(one, cells):
            results[(ltdn,pitch)]=(damax,dafin)
    print(f"Offline gain scan (clean): {DAYS}d dt={DT:.0f}s alt={ALT:.0f}km  "
          f"(Delta a_max mean, km; + = gain)")
    print("pitch\\LTDN " + "".join(f"{l:7.1f}" for l in LTDNS))
    npos=0
    for p in PITCHES:
        row=""
        for l in LTDNS:
            v=results[(l,p)][0]
            if v>0.05: npos+=1
            row+=f"{v:7.2f}"
        print(f"{p:7.1f}   {row}")
    # best cell
    best=max(results.items(), key=lambda kv: kv[1][0])
    print(f"\nBest: LTDN={best[0][0]} pitch={best[0][1]} da_max={best[1][0]:+.3f} km "
          f"da_final={best[1][1]:+.3f}")
    print(f"positive cells (>0.05 km): {npos}/{len(cells)}")


if __name__=="__main__":
    main()
