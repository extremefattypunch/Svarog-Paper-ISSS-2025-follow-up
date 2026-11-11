"""
Parameter-space maps of the 14-day maximum semi-major-axis excursion,
Delta a_max,14d, over LTAN x sail pitch, at 800 km (production) and 700 km
(contrast).  Replaces the reduced-model Fig. 2 of the original submission.

Grid: LTAN 0..23.5 h in 0.5 h steps (48 values; the 24 h value is identical
to 0 h and is NOT repeated, so the periodic boundary is not double-counted),
pitch -90..+90 deg in 5 deg steps (37 values).  Negative pitch tilts the normal
the other way in the orbital plane; beyond +/-90 deg the one-sided sail is not
illuminated.  1776 cells per altitude.

Usage: python runners/rev_maps.py [alt_km ...]      (default: 800 700)
"""
from __future__ import annotations
import os, sys, time, json
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from runners.rev_common import save_json, fig_path, mpl, INC, DT_PROD, N_WORKERS, RESULTS
from core.offline_propagator import SailCase, propagate

DAYS = 14.0
LTANS = np.arange(0.0, 24.0, 0.5)             # 48
PITCHES = np.arange(-90.0, 90.0 + 1e-9, 5.0)  # 37


def one(args):
    i, j, alt, ltan, pitch = args
    c = SailCase(altitude_km=alt, inc_deg=INC[alt], ltan_h=float(ltan), pitch_deg=float(pitch), dt=DT_PROD)
    r = propagate(c, DAYS)
    return i, j, r["da_max"], r["da_final"], r["da_at_14d"], r["reentry_day"], r["W_srp_total"], r["W_drag_total"]


def run_alt(alt):
    cells = [(i, j, alt, LTANS[i], PITCHES[j]) for i in range(len(LTANS)) for j in range(len(PITCHES))]
    Zmax = np.zeros((len(PITCHES), len(LTANS))); Zfin = np.zeros_like(Zmax)
    Wsrp = np.zeros_like(Zmax); Wdrag = np.zeros_like(Zmax); reent = np.zeros_like(Zmax, dtype=bool)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        for k, (i, j, dmax, dfin, d14, rd, ws, wd) in enumerate(ex.map(one, cells, chunksize=8)):
            Zmax[j, i] = dmax if dmax is not None else np.nan
            Zfin[j, i] = (d14 if d14 is not None else dfin) if dfin is not None else np.nan
            Wsrp[j, i] = ws; Wdrag[j, i] = wd; reent[j, i] = rd is not None
            if k % 200 == 0:
                print(f"  {alt:.0f} km: {k}/{len(cells)} cells, {time.time()-t0:.0f}s")
    np.savez(os.path.join(RESULTS, f"map_{int(alt)}.npz"), Zmax=Zmax, Zfin=Zfin, Wsrp=Wsrp, Wdrag=Wdrag,
             reentered=reent, ltan=LTANS, pitch=PITCHES, alt=alt, days=DAYS, dt=DT_PROD)
    npos = int((Zmax > 0.0).sum()); pk = np.unravel_index(np.nanargmax(Zmax), Zmax.shape)
    summary = dict(altitude_km=alt, n_cells=int(Zmax.size), n_positive=npos,
                   frac_positive=npos / Zmax.size, peak_da_max_km=float(Zmax[pk]),
                   peak_ltan_h=float(LTANS[pk[1]]), peak_pitch_deg=float(PITCHES[pk[0]]),
                   min_da14_km=float(np.nanmin(Zfin)), dt_s=DT_PROD, days=DAYS,
                   wall_s=time.time() - t0)
    # connected positive regions (4-connectivity, periodic in LTAN)
    summary["lobes"] = lobes(Zmax, LTANS, PITCHES)
    print(f"{alt:.0f} km: {npos}/{Zmax.size} positive ({100*npos/Zmax.size:.1f}%), "
          f"peak {Zmax[pk]:.3f} km at LTAN {LTANS[pk[1]]:.1f} h, pitch {PITCHES[pk[0]]:.0f} deg; "
          f"{len(summary['lobes'])} lobe(s)")
    return summary, Zmax


def lobes(Z, ltans, pitches):
    """Label 4-connected positive regions with LTAN treated as periodic."""
    pos = Z > 0.0; lab = np.zeros(Z.shape, dtype=int); n = 0
    nP, nL = Z.shape
    for j in range(nP):
        for i in range(nL):
            if pos[j, i] and lab[j, i] == 0:
                n += 1; stack = [(j, i)]; lab[j, i] = n
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, xx = y + dy, (x + dx) % nL
                        if 0 <= yy < nP and pos[yy, xx] and lab[yy, xx] == 0:
                            lab[yy, xx] = n; stack.append((yy, xx))
    out = []
    for k in range(1, n + 1):
        m = lab == k; pk = np.unravel_index(np.argmax(np.where(m, Z, -np.inf)), Z.shape)
        ii = np.where(m.any(axis=0))[0]; jj = np.where(m.any(axis=1))[0]
        out.append(dict(cells=int(m.sum()), peak_km=float(Z[pk]), peak_ltan_h=float(ltans[pk[1]]),
                        peak_pitch_deg=float(pitches[pk[0]]),
                        ltan_cells=[float(ltans[i]) for i in ii], pitch_min=float(pitches[jj.min()]),
                        pitch_max=float(pitches[jj.max()])))
    return sorted(out, key=lambda d: -d["peak_km"])


def plot(summaries, maps):
    plt = mpl()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharey=True)
    vmax = max(np.nanmax(m) for m in maps.values()); vmax = max(vmax, 0.5)
    for ax, alt in zip(axes, (800.0, 700.0)):
        Z = maps[alt]
        # pcolormesh with cell edges; LTAN periodic -> edges 0..24
        le = np.append(LTANS, 24.0) - 0.25; pe = np.append(PITCHES, 95.0) - 2.5
        im = ax.pcolormesh(le, pe, Z, cmap="RdBu_r", vmin=-vmax, vmax=vmax, shading="flat")
        ax.set_xlabel("local time of ascending node, LTAN [h]")
        ax.set_title(f"{alt:.0f} km: $\\Delta a_{{\\max,14\\mathrm{{d}}}}$")
        s = summaries[alt]
        if s["n_positive"] > 0:
            ax.plot(s["peak_ltan_h"], s["peak_pitch_deg"], "k*", ms=11, mec="w", mew=0.6,
                    label=f"peak {s['peak_da_max_km']:.2f} km")
            ax.legend(loc="upper right")
        ax.set_xlim(-0.25, 23.75); ax.set_ylim(-92.5, 92.5)
    axes[0].set_ylabel("sail pitch from the Sun line [deg]")
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02); cb.set_label("$\\Delta a_{\\max,14\\mathrm{d}}$ [km]")
    p = fig_path("r_map_ltan_pitch.png"); fig.savefig(p, bbox_inches="tight"); plt.close(fig); print("wrote", p)


def main():
    alts = [float(a) for a in sys.argv[1:]] or [800.0, 700.0]
    summaries, maps = {}, {}
    for alt in alts:
        summaries[alt], maps[alt] = run_alt(alt)
    # keep previously computed altitudes (a single-altitude re-run must not drop the other)
    p = os.path.join(RESULTS, "maps_summary.json")
    if os.path.exists(p):
        with open(p) as f:
            old = json.load(f)
        for k, v in old.items():
            summaries.setdefault(float(k), v)
    for alt in (800.0, 700.0):
        q = os.path.join(RESULTS, f"map_{int(alt)}.npz")
        if alt not in maps and os.path.exists(q):
            d = np.load(q); maps[alt] = d["Zmax"]
            if alt not in summaries:   # summary lost (e.g. interrupted run): rebuild it from the file
                Zmax, Zfin = d["Zmax"], d["Zfin"]
                npos = int((Zmax > 0.0).sum()); pk = np.unravel_index(np.nanargmax(Zmax), Zmax.shape)
                summaries[alt] = dict(altitude_km=alt, n_cells=int(Zmax.size), n_positive=npos,
                                      frac_positive=npos / Zmax.size, peak_da_max_km=float(Zmax[pk]),
                                      peak_ltan_h=float(d["ltan"][pk[1]]), peak_pitch_deg=float(d["pitch"][pk[0]]),
                                      min_da14_km=float(np.nanmin(Zfin)), dt_s=float(d["dt"]), days=float(d["days"]),
                                      wall_s=None, lobes=lobes(Zmax, d["ltan"], d["pitch"]))
    save_json("maps_summary.json", {str(int(k)): v for k, v in summaries.items()})
    if 800.0 in maps and 700.0 in maps:
        plot(summaries, maps)


if __name__ == "__main__":
    main()
