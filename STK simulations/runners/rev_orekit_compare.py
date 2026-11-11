"""
Cell-by-cell comparison of the 800 km LTAN x pitch map computed by the
open-source propagator (RK4, 10 s; results/revision/map_800.npz) with the same
map computed by Orekit (DP853 + eclipse events;
../Orekit simulations/results/gain_lobe_800.npz) on the identical grid.

Writes results/revision/orekit_map_compare.json and Figures/r_map_orekit_compare.png.
"""
from __future__ import annotations
import os, sys, json
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
import numpy as np
from runners.rev_common import RESULTS, PAPER_ROOT, save_json, fig_path, mpl

OREKIT = os.path.join(PAPER_ROOT, "Orekit simulations", "results")


def load_orekit(alt):
    d = np.load(os.path.join(OREKIT, f"gain_lobe_{alt}.npz"))
    key = "ltan" if "ltan" in d.files else "ltdn"
    return d["Z"], d[key], d["pitch"]


def main():
    m = np.load(os.path.join(RESULTS, "map_800.npz"))
    Zp, lt, pt = m["Zmax"], m["ltan"], m["pitch"]
    Zo, lto, pto = load_orekit(800)
    same_grid = Zo.shape == Zp.shape and np.allclose(lto, lt) and np.allclose(pto, pt)
    out = dict(same_grid=bool(same_grid), grid=dict(n_ltan=int(len(lt)), n_pitch=int(len(pt))))
    if not same_grid:
        # the Orekit grid may be a subset of the Python grid (e.g. every 2nd LTAN and pitch):
        # compare on the common cells only
        il = [int(np.argmin(np.abs(lt - v))) for v in lto]; jp = [int(np.argmin(np.abs(pt - v))) for v in pto]
        if max(abs(lt[i] - v) for i, v in zip(il, lto)) > 1e-6 or max(abs(pt[j] - v) for j, v in zip(jp, pto)) > 1e-6:
            raise SystemExit("Orekit grid is not a subset of the Python grid; re-run the Orekit lobe on a compatible grid")
        Zp = Zp[np.ix_(jp, il)]; lt, pt = lto, pto
        out["grid"] = dict(n_ltan=int(len(lt)), n_pitch=int(len(pt)), note="Orekit grid is a subset of the 48x37 Python grid; compared on the common cells")
    ok = np.isfinite(Zo) & np.isfinite(Zp)
    d = Zo[ok] - Zp[ok]
    pos_p, pos_o = Zp > 0, Zo > 0
    out.update(
        n_cells=int(ok.sum()), n_positive_opensource=int(pos_p[ok].sum()), n_positive_orekit=int(pos_o[ok].sum()),
        sign_agreement_frac=float(np.mean(pos_p[ok] == pos_o[ok])),
        peak_opensource_km=float(np.nanmax(Zp)), peak_orekit_km=float(np.nanmax(Zo)),
        peak_cell_opensource=dict(ltan_h=float(lt[np.unravel_index(np.nanargmax(Zp), Zp.shape)[1]]),
                                  pitch_deg=float(pt[np.unravel_index(np.nanargmax(Zp), Zp.shape)[0]])),
        peak_cell_orekit=dict(ltan_h=float(lto[np.unravel_index(np.nanargmax(Zo), Zo.shape)[1]]),
                              pitch_deg=float(pto[np.unravel_index(np.nanargmax(Zo), Zo.shape)[0]])),
        diff_mean_km=float(d.mean()), diff_rms_km=float(np.sqrt(np.mean(d ** 2))), diff_max_abs_km=float(np.max(np.abs(d))),
        diff_rms_positive_cells_km=float(np.sqrt(np.mean((Zo - Zp)[ok & pos_p] ** 2))) if (ok & pos_p).any() else None,
        n_failed_orekit=int(np.sum(~np.isfinite(Zo))),
    )
    for k, v in out.items():
        print(f"{k}: {v}")
    save_json("orekit_map_compare.json", out)

    plt = mpl()
    lim = max(1.0, float(np.nanmax(np.abs(np.concatenate([Zp.ravel(), Zo.ravel()])))))
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.9), constrained_layout=True)
    for ax, Z, ttl in zip(axes[:2], (Zp, Zo), ("open-source propagator (RK4, 10 s)", "Orekit (DP853 + eclipse events)")):
        im = ax.pcolormesh(lt, pt, Z, shading="nearest", cmap="RdBu_r", vmin=-lim, vmax=lim)
        ax.contour(lt, pt, Z, levels=[0.0], colors="k", linewidths=0.7)
        ax.set_title(ttl); ax.set_xlabel("LTAN [h]")
    axes[0].set_ylabel("sail pitch [deg]"); fig.colorbar(im, ax=axes[:2].tolist(), label=r"$\Delta a_{\max,14\mathrm{d}}$ [km]", shrink=0.9)
    D = Zo - Zp; dl = float(np.nanmax(np.abs(D)))
    im2 = axes[2].pcolormesh(lt, pt, D, shading="nearest", cmap="PuOr", vmin=-dl, vmax=dl)
    axes[2].set_title("Orekit $-$ open-source"); axes[2].set_xlabel("LTAN [h]")
    fig.colorbar(im2, ax=axes[2], label="difference [km]", shrink=0.9)
    fig.savefig(fig_path("r_map_orekit_compare.png")); plt.close(fig)
    print("figure written")


if __name__ == "__main__":
    main()
