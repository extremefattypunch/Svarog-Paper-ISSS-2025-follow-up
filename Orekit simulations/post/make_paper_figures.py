"""
Build the manuscript figures for the Orekit validation.

Produces three composite figures and copies them into the manuscript's
`Figures/` directory:

  orekit_crossvalidation.png  cross-validation against Orekit: propagated mean
                              SMA, the residual against the open-source
                              propagator, and the SRP attitude-coupling test
                              that STK could not pass
  orekit_diagnosis.png        what the inter-tool differences actually are:
                              drag modelling choices isolated one at a time, and
                              the step-size sensitivity of an eclipse-gated force
  orekit_reproduction.png     independent reproduction of the gain regime:
                              LTDN x pitch lobe, one-orbit SRP power, and the
                              75-day transient

Series that are cheap to recompute are recomputed; the 75-day propagations and
the sweep grids are read from results/.

Usage: ./run.sh post/make_paper_figures.py
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orekit_core.orekit_setup import boot, ROOT  # noqa: E402

boot()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from orekit_core.attitude import raan_for_ltdn  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    ANCHOR_LTDN_H, ANCHOR_PITCH_DEG, ANCHOR_RAAN_DEG, REPRO_LTDN_H,
    REPRO_PITCH_DEG, INC_700, INC_800, SAIL_AREA,
)
from orekit_core.propagation import (  # noqa: E402
    OrekitCase, propagate, build_propagator, keplerian_period, T0,
)

from core.offline_propagator import SailCase, propagate as propagate_paper  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "reproduced_figures")
PAPER_FIGS = os.path.join(os.path.dirname(os.path.dirname(ROOT)),
                          "Svarog-Paper-ISSS-2025-follow-up", "Figures")
if not os.path.isdir(PAPER_FIGS):
    PAPER_FIGS = os.path.join(os.path.dirname(ROOT), "Figures")

DAYS = 14.0
DT = 30.0
LTDN = 14.0
RAAN = raan_for_ltdn(LTDN)
PITCH = REPRO_PITCH_DEG
STK_DA_700 = -7.0            # km, 14-day mean SMA decay reported for STK
STK_J2_BAR = 0.05            # km, STK's quoted J2-only agreement

plt.rcParams.update({
    "font.size": 8.5,
    "axes.titlesize": 9,
    "axes.labelsize": 8.5,
    "legend.fontsize": 7,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "axes.grid": True,
    "grid.alpha": 0.25,
})


def _load(name):
    with open(os.path.join(RESULTS, name)) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Figure 1 -- cross-validation
# ---------------------------------------------------------------------------
def figure_crossvalidation():
    print("building orekit_crossvalidation.png")
    series = {}
    for alt in (700.0, 800.0):
        for use_drag in (True, False):
            case = OrekitCase(altitude_km=alt, raan_deg=RAAN, pitch_deg=PITCH,
                              use_srp=False, use_drag=use_drag,
                              drag_mode="spherical", dt=DT)
            ok = propagate(case, DAYS)
            c = SailCase(altitude_km=alt, inc_deg=(INC_800 if alt >= 750 else INC_700),
                         raan_deg=RAAN, pitch_deg=PITCH, ecc=1e-4,
                         use_srp=False, drag_mode="spherical", dt=DT)
            if not use_drag:
                c.cd = 0.0
            pp = propagate_paper(c, DAYS)
            series[(alt, use_drag)] = (ok, pp)

    v4 = _load("v4_srp_attitude_coupling.json")

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))
    colours = {700.0: "tab:blue", 800.0: "tab:red"}

    # (a) propagated mean SMA, J2 + spherical drag
    ax = axes[0]
    for alt in (700.0, 800.0):
        ok, pp = series[(alt, True)]
        ax.plot(pp["node_t"] / 86400, pp["node_a"] - pp["node_a"][0], "-",
                lw=2.6, color=colours[alt], alpha=0.45)
        ax.plot(ok["node_t"] / 86400, ok["node_a"] - ok["node_a"][0], "--",
                lw=1.3, color=colours[alt])
    ax.plot([DAYS], [STK_DA_700], "k*", ms=12, zorder=5)
    ax.annotate("STK, 700 km\n(reported)", xy=(DAYS, STK_DA_700),
                xytext=(-58, 14), textcoords="offset points", fontsize=7,
                ha="center", arrowprops=dict(arrowstyle="-", lw=0.6, color="k"))
    ax.set_xlabel("time [days]")
    ax.set_ylabel(r"$\Delta a$ (mean) [km]")
    ax.set_title(r"(a) $J_2$ + spherical US-1976 drag", loc="left")
    handles = [Line2D([], [], color="0.35", lw=2.6, alpha=0.6, label="open-source"),
               Line2D([], [], color="0.35", lw=1.3, ls="--", label="Orekit"),
               Line2D([], [], color=colours[700.0], lw=2, label="700 km"),
               Line2D([], [], color=colours[800.0], lw=2, label="800 km"),
               Line2D([], [], color="k", marker="*", ls="", ms=8, label="STK endpoint")]
    ax.legend(handles=handles, loc="lower left", ncol=1)

    # (b) residual, log scale
    ax = axes[1]
    for alt in (700.0, 800.0):
        for use_drag, style in ((True, "-"), (False, ":")):
            ok, pp = series[(alt, use_drag)]
            d_ok = np.interp(pp["node_t"], ok["node_t"],
                             ok["node_a"] - ok["node_a"][0])
            resid = np.abs((pp["node_a"] - pp["node_a"][0]) - d_ok)
            lab = f"{int(alt)} km, " + (r"$J_2$+drag" if use_drag else r"$J_2$ only")
            ax.semilogy(pp["node_t"][1:] / 86400, np.maximum(resid[1:], 1e-16),
                        style, lw=1.3, color=colours[alt], label=lab)
    ax.axhline(STK_J2_BAR, color="k", ls="--", lw=1.1)
    ax.text(0.35, STK_J2_BAR * 1.5, "STK's quoted $J_2$ agreement (0.05 km)",
            fontsize=6.8, va="bottom")
    ax.axhline(abs(STK_DA_700 - (-84.04)), color="0.35", ls="-.", lw=1.1)
    ax.text(0.35, abs(STK_DA_700 + 84.04) * 1.25,
            "STK$-$open-source drag gap (77 km)", fontsize=6.8, va="bottom")
    ax.set_xlabel("time [days]")
    ax.set_ylabel(r"$|\Delta a_{\rm open-source} - \Delta a_{\rm Orekit}|$ [km]")
    ax.set_title("(b) residual against Orekit", loc="left")
    ax.legend(loc="center right")
    ax.set_ylim(1e-13, 3e2)

    # (c) SRP attitude coupling
    ax = axes[2]
    pitches = np.array(v4["pitch_deg"])
    area = np.array(v4["effective_area_m2"])
    ax.plot(pitches, area, lw=2.0, color="tab:green", label="Orekit N-plate")
    ax.axhline(0.0, color="tab:red", lw=2.0, ls="--",
               label="STK Astrogator N-plate (reported)")
    ax.axvline(ANCHOR_PITCH_DEG, color="0.5", lw=0.8, ls=":")
    ax.annotate(f"{v4['effective_area_at_anchor_m2']:.1f} m$^2$ at the\n"
                f"anchor pitch ({ANCHOR_PITCH_DEG}$^\\circ$)",
                xy=(ANCHOR_PITCH_DEG, v4["effective_area_at_anchor_m2"]),
                xytext=(18, -6), textcoords="offset points", fontsize=7,
                arrowprops=dict(arrowstyle="->", lw=0.6))
    ax.set_xlabel("sail pitch [deg]")
    ax.set_ylabel(r"effective Sun-facing area $A\cos\alpha$ [m$^2$]")
    ax.set_title("(c) attitude coupling of the N-plate SRP model", loc="left")
    ax.legend(loc="upper right")
    ax.set_ylim(-6, 108)

    fig.tight_layout()
    out = os.path.join(FIGS, "orekit_crossvalidation.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 2 -- diagnosis
# ---------------------------------------------------------------------------
def figure_diagnosis():
    print("building orekit_diagnosis.png")
    v6 = _load("v6_drag_decomposition.json")
    v7 = _load("v7_eclipse_discontinuity.json")

    short = {
        "baseline (US-1976, geocentric, no co-rotation)": "paper convention",
        "co-rotating atmosphere": "+ co-rotation",
        "geodetic altitude": "+ geodetic altitude",
        "co-rotating + geodetic": "+ both",
        "Harris-Priester (Orekit built-in)": "Harris-Priester",
        "NRLMSISE-00 (Orekit built-in)": "NRLMSISE-00",
    }
    order = list(short)
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.1))

    ax = axes[0]
    width = 0.38
    idx = np.arange(len(order))
    for k, (alt, colour) in enumerate(((700.0, "tab:blue"), (800.0, "tab:red"))):
        vals = []
        for cfg in order:
            row = next((r for r in v6["rows"]
                        if r["altitude_km"] == alt and r["config"] == cfg), None)
            vals.append(row["da_node_km"] if row else np.nan)
        bars = ax.bar(idx + (k - 0.5) * width, vals, width, color=colour,
                      label=f"{int(alt)} km")
        for cfg, b, v in zip(order, bars, vals):
            row = next((r for r in v6["rows"]
                        if r["altitude_km"] == alt and r["config"] == cfg), None)
            if row and row.get("reentered"):
                ax.text(b.get_x() + b.get_width() / 2, v, "reentry",
                        ha="center", va="top", fontsize=6, rotation=90)
    ax.axhline(STK_DA_700, color="k", ls="--", lw=1.2)
    ax.text(len(order) - 0.4, STK_DA_700, "STK, 700 km (reported)",
            fontsize=7, ha="right", va="bottom")
    ax.set_xticks(idx)
    ax.set_xticklabels([short[c] for c in order], rotation=28, ha="right")
    ax.set_ylabel(r"14-day $\Delta a$ (mean) [km]")
    ax.set_title("(a) drag modelling choices, isolated one at a time", loc="left")
    ax.legend(loc="lower left")

    ax = axes[1]
    ref = v7["reference_da_max_km"]
    styles = {"full model (eclipse-gated SRP)": ("tab:purple", "o-"),
              "SRP with umbra disabled": ("tab:orange", "s-"),
              "drag only, no SRP": ("tab:gray", "^-")}
    for label, rows in v7["fixed_step"].items():
        colour, marker = styles.get(label, ("k", "o-"))
        ax.plot([r["dt_s"] for r in rows], [r["da_max_km"] for r in rows],
                marker, color=colour, lw=1.4, ms=4, label=label)
    ax.axhline(ref, color="k", ls="--", lw=1.2,
               label="DP853 + eclipse events (converged)")
    ax.axvline(30.0, color="0.6", lw=0.8, ls=":")
    ax.annotate("step used by the\nopen-source propagator", xy=(30.0, ref),
                xytext=(6, 26), textcoords="offset points", fontsize=6.8,
                arrowprops=dict(arrowstyle="->", lw=0.6))
    ax.set_xscale("log")
    ax.set_xlabel("fixed integration step [s]")
    ax.set_ylabel(r"14-day $\Delta a_{\max}$ [km]")
    ax.set_title("(b) step-size sensitivity at 800 km", loc="left")
    ax.legend(loc="best")

    fig.tight_layout()
    out = os.path.join(FIGS, "orekit_diagnosis.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 3 -- reproduction of the gain regime
# ---------------------------------------------------------------------------
def figure_reproduction():
    print("building orekit_reproduction.png")
    grid = np.load(os.path.join(RESULTS, "gain_lobe_800.npz"))
    Z, ltdn, pitch = grid["Z"], grid["ltdn"], grid["pitch"]

    # one-orbit SRP power (cheap to recompute)
    def one_orbit(disable_eclipse):
        case = OrekitCase(altitude_km=800.0, inc_deg=INC_800,
                          raan_deg=raan_for_ltdn(REPRO_LTDN_H),
                          pitch_deg=REPRO_PITCH_DEG,
                          disable_eclipse=disable_eclipse, dt=5.0)
        prop, rec, st0, n = build_propagator(case, want_diagnostics=True)
        period = keplerian_period(case.sma_m)
        prop.propagate(T0, T0.shiftedBy(period))
        return (np.asarray(rec.t), np.asarray(rec.p_srp),
                np.asarray(rec.lit) > 0.5, period)

    t_on, p_on, lit_on, period = one_orbit(False)
    t_off, p_off, _, _ = one_orbit(True)

    lh = _load("long_horizon.json")
    cache = os.path.join(RESULTS, "long_horizon_series.npz")
    if os.path.exists(cache):
        s = np.load(cache)
        lt_g, la_g, lt_a, la_a = s["t_gain"], s["a_gain"], s["t_anchor"], s["a_anchor"]
    else:
        def run_long(kw):
            r = propagate(OrekitCase(integrator="dp853", dt=30.0, **kw), 75.0)
            hp = r["node_hp"]
            below = np.nonzero(hp < 120.0)[0]
            end = int(below[0]) if len(below) else len(hp)
            sl = slice(0, max(1, end))
            return r["node_t"][sl] / 86400.0, r["node_a"][sl]
        lt_g, la_g = run_long(dict(altitude_km=800.0, inc_deg=INC_800,
                                   raan_deg=raan_for_ltdn(REPRO_LTDN_H),
                                   pitch_deg=REPRO_PITCH_DEG))
        lt_a, la_a = run_long(dict(altitude_km=700.0, inc_deg=INC_700,
                                   raan_deg=ANCHOR_RAAN_DEG,
                                   pitch_deg=ANCHOR_PITCH_DEG))
        np.savez(cache, t_gain=lt_g, a_gain=la_g, t_anchor=lt_a, a_anchor=la_a)

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))

    ax = axes[0]
    lim = max(1.0, float(np.nanmax(np.abs(Z))))
    im = ax.pcolormesh(ltdn, pitch, Z, shading="auto", cmap="RdBu_r",
                       vmin=-lim, vmax=lim)
    ax.plot(ANCHOR_LTDN_H, ANCHOR_PITCH_DEG, "k*", ms=11)
    peak = np.unravel_index(np.nanargmax(Z), Z.shape)
    ax.plot(ltdn[peak[1]], pitch[peak[0]], "ko", ms=6, mfc="none", mew=1.4)
    ax.set_xlabel("LTDN [h]")
    ax.set_ylabel("sail pitch [deg]")
    ax.set_title(r"(a) 14-day $\Delta a_{\max}$ at 800 km", loc="left")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label(r"$\Delta a_{\max}$ [km]")
    ax.legend(handles=[Line2D([], [], color="k", marker="*", ls="", ms=9,
                              label="reduced-model anchor"),
                       Line2D([], [], color="k", marker="o", ls="", ms=6,
                              mfc="none", label="Orekit peak")],
              loc="upper right", framealpha=0.85)

    ax = axes[1]
    tm = t_on / 60.0
    ax.plot(tm, p_on, lw=1.6, color="tab:blue", label="eclipse ON")
    ax.plot(t_off / 60.0, p_off, "--", lw=1.2, color="0.4",
            label="no-eclipse reference")
    ax.axhline(0, color="k", lw=0.6)
    inside, labelled = False, False
    for i, dark in enumerate(~lit_on):
        if dark and not inside:
            start = tm[i]; inside = True
        if (not dark or i == len(lit_on) - 1) and inside:
            ax.axvspan(start, tm[i], color="0.85", zorder=0,
                       label=None if labelled else "umbra")
            labelled, inside = True, False
    ax.set_xlabel("time [min]")
    ax.set_ylabel(r"$\mathbf{a}_{\rm SRP}\!\cdot\!\mathbf{v}$ [W/kg]")
    ax.set_title("(b) one-orbit SRP specific power", loc="left")
    ax.legend(loc="lower left")

    ax = axes[2]
    ax.plot(lt_g, la_g - la_g[0], lw=1.6, color="tab:blue",
            label=f"gain case (800 km, LTDN {REPRO_LTDN_H:g} h, "
                  f"pitch {REPRO_PITCH_DEG:g}$^\\circ$)")
    ax.plot(lt_a, la_a - la_a[0], lw=1.6, color="tab:red",
            label="anchor (700 km, LTDN 12.27 h, pitch 24.8$^\\circ$)")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("time [days]")
    ax.set_ylabel(r"$\Delta a$ (mean) [km]")
    ax.set_title("(c) 75-day transient", loc="left")
    ax.legend(loc="lower left")

    fig.tight_layout()
    out = os.path.join(FIGS, "orekit_reproduction.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main():
    os.makedirs(FIGS, exist_ok=True)
    produced = [figure_crossvalidation(), figure_diagnosis(), figure_reproduction()]
    print()
    for p in produced:
        dest = os.path.join(PAPER_FIGS, os.path.basename(p))
        shutil.copyfile(p, dest)
        print(f"wrote {p}\n  -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
