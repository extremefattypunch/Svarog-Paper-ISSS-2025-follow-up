"""
Representative cases for the revised manuscript (Sections 6-7), selected from
the 800 km map produced by rev_maps.py:

  gain     the map peak of Delta a_max,14d
  neutral  a cell with no positive excursion whose 14-day Delta a is closest to
           the drag-only decay (orbit-averaged SRP work ~ 0)
  decay    the cell with the most negative 14-day Delta a (eclipse removes the
           favourable SRP arc)

Runs and outputs (all at the production step DT_PROD):
  * 14-day eclipse on/off for the gain case and the legacy 700 km anchor
  * 75-day full-model histories for gain / neutral / decay (+ legacy anchor)
  * one-orbit dense SRP power and cumulative SRP work (eclipse on/off, and the
    Sun-line force variant) for the three cases
  * early-vs-late orbit-averaged work budgets (20% windows) and SRP RTN
    force-component drift (10% windows) for the gain case

Writes results/revision/cases.json and the Figures/r_*.png used by the paper.
"""
from __future__ import annotations
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from runners.rev_common import (save_json, load_json, fig_path, mpl, INC, DT_PROD, N_WORKERS,
                                RESULTS, ANCHOR700_OLD, orbit_period_s)
from core.offline_propagator import SailCase, propagate

LONG_DAYS = 75.0
MASS = 10.0


# ---------------------------------------------------------------------------
def select_cases():
    m = np.load(os.path.join(RESULTS, "map_800.npz"))
    Zmax, Zfin, ltan, pitch = m["Zmax"], m["Zfin"], m["ltan"], m["pitch"]
    # drag-only reference decay at 800 km over 14 d
    ref = propagate(SailCase(altitude_km=800.0, inc_deg=INC[800.0], ltan_h=14.0, pitch_deg=34.0,
                             use_srp=False, dt=DT_PROD), 14.0)
    drag_only_14d = ref["da_at_14d"]
    jg, ig = np.unravel_index(np.nanargmax(Zmax), Zmax.shape)
    # neutral: no positive excursion, 14-day change closest to the drag-only decay, with the
    # sail still substantially illuminated (|pitch| <= 45 deg) so that the SRP work is not
    # trivially zero -- an edge-on sail would be "neutral" for the wrong reason
    nogain = (Zmax <= 0.0) & ~np.isnan(Zfin) & (np.abs(pitch)[:, None] <= 45.0)
    score = np.where(nogain, np.abs(Zfin - drag_only_14d), np.inf)
    jn, in_ = np.unravel_index(np.argmin(score), score.shape)
    jd, id_ = np.unravel_index(np.nanargmin(np.where(np.isnan(Zfin), np.inf, Zfin)), Zfin.shape)
    cases = dict(
        gain=dict(altitude_km=800.0, inc_deg=INC[800.0], ltan_h=float(ltan[ig]), pitch_deg=float(pitch[jg]),
                  map_da_max_km=float(Zmax[jg, ig]), map_da14_km=float(Zfin[jg, ig])),
        neutral=dict(altitude_km=800.0, inc_deg=INC[800.0], ltan_h=float(ltan[in_]), pitch_deg=float(pitch[jn]),
                     map_da_max_km=float(Zmax[jn, in_]), map_da14_km=float(Zfin[jn, in_])),
        decay=dict(altitude_km=800.0, inc_deg=INC[800.0], ltan_h=float(ltan[id_]), pitch_deg=float(pitch[jd]),
                   map_da_max_km=float(Zmax[jd, id_]), map_da14_km=float(Zfin[jd, id_])),
        legacy700=dict(**ANCHOR700_OLD),
        drag_only_800_da14_km=drag_only_14d,
    )
    for k in ("gain", "neutral", "decay", "legacy700"):
        c = cases[k]
        print(f"{k:9s}: LTAN {c['ltan_h']:5.2f} h, pitch {c['pitch_deg']:+6.1f} deg"
              + (f", map da_max {c['map_da_max_km']:+.3f}, da14 {c['map_da14_km']:+.3f} km" if "map_da_max_km" in c else ""))
    return cases


def _geo(c):
    return dict(altitude_km=c["altitude_km"], inc_deg=c["inc_deg"], ltan_h=c["ltan_h"], pitch_deg=c["pitch_deg"])


# ---------------------------------------------------------------------------
def job(args):
    name, geo, days, kw, want_forces, stride, dt = args
    r = propagate(SailCase(dt=dt, **geo, **kw), days, want_forces=want_forces, force_stride=stride)
    return name, r


def summarise_long(r):
    t = r["node_t"] / 86400.0; a = r["node_a"]; a0 = a[0]
    ia = int(np.argmax(a)); iha = int(np.argmax(r["node_ha"])); ihp = int(np.argmin(r["node_hp"])); ie = int(np.argmax(r["node_e"]))
    n = len(a); w20 = max(1, int(round(0.2 * n))); w10 = max(1, int(round(0.1 * n)))
    Ws, Wd = r["orb_W_srp"], r["orb_W_drag"]; FT, FN = r["orb_FT_srp"], r["orb_FN_srp"]
    return dict(
        a0_km=float(a0), a_peak_km=float(a[ia]), t_peak_d=float(t[ia]), da_peak_km=float(a[ia] - a0),
        a_final_km=float(a[-1]), da_final_km=float(a[-1] - a0), span_days=float(r["span_days"]),
        reentry_day=r["reentry_day"], n_orbits=int(n),
        ha0_km=float(r["node_ha"][0]), ha_max_km=float(r["node_ha"][iha]), t_ha_max_d=float(t[iha]), ha_final_km=float(r["node_ha"][-1]),
        hp0_km=float(r["node_hp"][0]), hp_min_km=float(r["node_hp"][ihp]), t_hp_min_d=float(t[ihp]), hp_final_km=float(r["node_hp"][-1]),
        e0=float(r["node_e"][0]), e_max=float(r["node_e"][ie]), t_e_max_d=float(t[ie]), e_final=float(r["node_e"][-1]),
        W_srp_total_J_kg=float(Ws.sum()), W_drag_total_J_kg=float(Wd.sum()),
        W_total_J_kg=float(Ws.sum() + Wd.sum()),
        work_ratio=float(abs(Wd.sum()) / abs(Ws.sum())) if Ws.sum() != 0 else None,
        early_late=dict(
            window_orbits_20pct=int(w20), window_orbits_10pct=int(w10),
            mean_W_srp_early_J_kg_orbit=float(Ws[:w20].mean()), mean_W_srp_late_J_kg_orbit=float(Ws[-w20:].mean()),
            mean_W_drag_early_J_kg_orbit=float(Wd[:w20].mean()), mean_W_drag_late_J_kg_orbit=float(Wd[-w20:].mean()),
            mean_W_net_early_J_kg_orbit=float((Ws + Wd)[:w20].mean()), mean_W_net_late_J_kg_orbit=float((Ws + Wd)[-w20:].mean()),
            FT_early_m_s2=float(FT[:w10].mean()), FT_late_m_s2=float(FT[-w10:].mean()),
            FN_early_m_s2=float(FN[:w10].mean()), FN_late_m_s2=float(FN[-w10:].mean()),
            ecl_frac_early=float(r["orb_ecl_frac"][:w20].mean()), ecl_frac_late=float(r["orb_ecl_frac"][-w20:].mean()),
        ),
    )


def one_orbit_stats(F_on, F_off, F_sun=None):
    """F columns: t, P_srp, P_drag, cos_alpha, eclipse, aR, aT, aN, a_osc."""
    t = F_on[:, 0]; dt = np.diff(t, prepend=t[0] - (t[1] - t[0]))
    W_on = float(np.sum(F_on[:, 1] * dt)); W_off = float(np.sum(F_off[:, 1] * dt))
    m = F_on[:, 4] > 0.5
    sel = float(100.0 * np.mean(F_off[m, 1] < 0.0)) if m.any() else float("nan")
    harm = float(np.sum(np.where(F_off[m, 1] < 0, F_off[m, 1], 0.0) * dt[m])) if m.any() else 0.0
    benef = float(np.sum(np.where(F_off[m, 1] > 0, F_off[m, 1], 0.0) * dt[m])) if m.any() else 0.0
    out = dict(W_eclipse_on_J_kg=W_on, W_eclipse_off_J_kg=W_off, eclipse_fraction=float(m.mean()),
               sign_selectivity_pct=sel, suppressed_negative_work_J_kg=harm, suppressed_positive_work_J_kg=benef,
               span_min=float(t[-1] / 60.0))
    if F_sun is not None:
        out["W_sunline_force_eclipse_on_J_kg"] = float(np.sum(F_sun[:, 1] * dt))
    return out


# ---------------------------------------------------------------------------
def main():
    cases = select_cases()
    G, Nn, Dd, L = cases["gain"], cases["neutral"], cases["decay"], cases["legacy700"]
    P800 = orbit_period_s(800.0)

    jobs = [
        ("gain_14_on", _geo(G), 14.0, {}, False, 1, DT_PROD),
        ("gain_14_off", _geo(G), 14.0, dict(disable_eclipse=True), False, 1, DT_PROD),
        ("legacy_14_on", _geo(L), 14.0, {}, False, 1, DT_PROD),
        ("legacy_14_off", _geo(L), 14.0, dict(disable_eclipse=True), False, 1, DT_PROD),
        ("gain_75", _geo(G), LONG_DAYS, {}, False, 1, DT_PROD),
        ("neutral_75", _geo(Nn), LONG_DAYS, {}, False, 1, DT_PROD),
        ("decay_75", _geo(Dd), LONG_DAYS, {}, False, 1, DT_PROD),
        ("legacy_75", _geo(L), LONG_DAYS, {}, False, 1, DT_PROD),
        ("gain_75_off", _geo(G), LONG_DAYS, dict(disable_eclipse=True), False, 1, DT_PROD),
        ("gain_14_sunline", _geo(G), 14.0, dict(srp_dir="sunline"), False, 1, DT_PROD),
        ("gain_14_nosrp", _geo(G), 14.0, dict(use_srp=False), False, 1, DT_PROD),
    ]
    # one-orbit dense runs (1.05 orbit, dt = 2 s)
    for name, c in (("gain", G), ("neutral", Nn), ("decay", Dd)):
        d = 1.05 * P800 / 86400.0
        jobs += [(f"orb_{name}_on", _geo(c), d, {}, True, 1, 2.0),
                 (f"orb_{name}_off", _geo(c), d, dict(disable_eclipse=True), True, 1, 2.0)]
    jobs += [("orb_gain_sunline", _geo(G), 1.05 * P800 / 86400.0, dict(srp_dir="sunline"), True, 1, 2.0)]

    R = {}
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        for name, r in ex.map(job, jobs):
            R[name] = r; print("done", name)

    out = dict(dt_s=DT_PROD, long_days=LONG_DAYS, mass_kg=MASS, cases=cases)
    out["eclipse_causality_14d"] = {
        k: dict(da_max_km=R[k]["da_max"], da_at_14d_km=R[k]["da_at_14d"], da_final_km=R[k]["da_final"],
                t_at_max_d=R[k]["t_at_max_d"], reentry_day=R[k]["reentry_day"])
        for k in ("gain_14_on", "gain_14_off", "legacy_14_on", "legacy_14_off", "gain_14_sunline", "gain_14_nosrp")}
    out["long_horizon"] = {k: summarise_long(R[k]) for k in ("gain_75", "neutral_75", "decay_75", "legacy_75", "gain_75_off")}
    # one node-to-node orbit: the dense runs cover 1.05 P so the first ascending-node
    # crossing (at ~one nodal period) is always reached; truncate every series there
    def cut(F, tn):
        return F[F[:, 0] <= tn]
    out["one_orbit"] = {}
    for name in ("gain", "neutral", "decay"):
        tn = float(R[f"orb_{name}_on"]["node_t"][0])
        out["one_orbit"][name] = one_orbit_stats(cut(R[f"orb_{name}_on"]["forces"], tn), cut(R[f"orb_{name}_off"]["forces"], tn),
                                                 cut(R["orb_gain_sunline"]["forces"], tn) if name == "gain" else None)
        out["one_orbit"][name]["nodal_period_min"] = tn / 60.0
    save_json("cases.json", out)
    np.savez(os.path.join(RESULTS, "cases_series.npz"),
             **{f"{k}__{kk}": v for k, r in R.items() for kk, v in r.items() if isinstance(v, np.ndarray)})
    make_figures(R, cases, out)


# ---------------------------------------------------------------------------
def _label(c, name):
    return f"{name}: LTAN {c['ltan_h']:.1f} h, pitch {c['pitch_deg']:+.0f}°"


def make_figures(R, cases, out):
    plt = mpl()
    G, Nn, Dd, L = cases["gain"], cases["neutral"], cases["decay"], cases["legacy700"]

    # --- eclipse on/off, 14 d (gain 800 + legacy 700) -----------------------
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.5))
    for ax, (on, off, c, ttl) in zip(axes, (("gain_14_on", "gain_14_off", G, "800 km gain case"),
                                           ("legacy_14_on", "legacy_14_off", L, "700 km (original-submission anchor)"))):
        for k, st, lab in ((on, "-", "eclipse on"), (off, "--", "eclipse off")):
            r = R[k]; ax.plot(r["node_t"] / 86400, r["node_a"] - r["node_a"][0], st, lw=1.5, label=lab)
        ax.axhline(0, color="k", lw=0.5); ax.set_xlabel("time [days]"); ax.set_ylabel("$\\Delta a$ (mean) [km]")
        ax.set_title(f"{ttl}\nLTAN {c['ltan_h']:.1f} h, pitch {c['pitch_deg']:+.0f}°"); ax.legend()
    fig.tight_layout(); fig.savefig(fig_path("r_eclipse_onoff.png")); plt.close(fig)

    # --- one-orbit SRP power (3 cases) --------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    def cut(F, tn):
        return F[F[:, 0] <= tn]
    for ax, name, c in zip(axes, ("gain", "neutral", "decay"), (G, Nn, Dd)):
        tn = float(R[f"orb_{name}_on"]["node_t"][0])
        Fon, Foff = cut(R[f"orb_{name}_on"]["forces"], tn), cut(R[f"orb_{name}_off"]["forces"], tn)
        t = Fon[:, 0] / 60.0; ecl = Fon[:, 4]
        ax.plot(t, Foff[:, 1], "C1--", lw=1.1, label="no-eclipse reference")
        ax.plot(t, Fon[:, 1], "C0", lw=1.5, label="eclipse on")
        inb = False
        for i, f in enumerate(ecl):
            if f > 0.5 and not inb: s = t[i]; inb = True
            if (f <= 0.5 or i == len(ecl) - 1) and inb: ax.axvspan(s, t[i], color="0.85", zorder=0); inb = False
        ax.axhline(0, color="k", lw=0.5); ax.set_xlabel("time from ascending node [min]")
        ax.set_title(_label(c, name)); ax.set_xlim(0, t[-1])
    axes[0].set_ylabel("SRP specific power $\\mathbf{a}_{\\rm SRP}\\cdot\\mathbf{v}$ [W kg$^{-1}$]"); axes[0].legend(loc="lower left")
    fig.tight_layout(); fig.savefig(fig_path("r_srp_power.png")); plt.close(fig)

    # --- one-orbit cumulative SRP work (3 cases + Sun-line variant) ---------
    def cum(F):
        t = F[:, 0]; dt = np.diff(t, prepend=t[0] - (t[1] - t[0])); return np.cumsum(F[:, 1] * dt)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    for ax, name, c in zip(axes, ("gain", "neutral", "decay"), (G, Nn, Dd)):
        tn = float(R[f"orb_{name}_on"]["node_t"][0])
        Fon, Foff = cut(R[f"orb_{name}_on"]["forces"], tn), cut(R[f"orb_{name}_off"]["forces"], tn)
        t = Fon[:, 0] / 60.0
        Won, Woff = cum(Fon), cum(Foff)
        ax.plot(t, Won, "C0", lw=1.5, label=f"eclipse on (end {Won[-1]:+.0f} J/kg)")
        ax.plot(t, Woff, "C1--", lw=1.1, label=f"no eclipse (end {Woff[-1]:+.0f} J/kg)")
        if name == "gain":
            Ws = cum(cut(R["orb_gain_sunline"]["forces"], tn))
            ax.plot(t, Ws, "C2:", lw=1.3, label=f"Sun-line force, eclipse on (end {Ws[-1]:+.0f} J/kg)")
        ax.axhline(0, color="k", lw=0.5); ax.set_xlabel("time from ascending node [min]"); ax.set_title(_label(c, name)); ax.legend(loc="best")
    axes[0].set_ylabel("cumulative SRP specific work [J kg$^{-1}$]")
    fig.tight_layout(); fig.savefig(fig_path("r_cum_srp_work.png")); plt.close(fig)

    # --- 75-day elements (gain / neutral / decay) ---------------------------
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.4))
    for k, c, col, name in (("gain_75", G, "C0", "gain"), ("neutral_75", Nn, "C2", "neutral"), ("decay_75", Dd, "C3", "decay")):
        r = R[k]; t = r["node_t"] / 86400
        axes[0, 0].plot(t, r["node_a"] - r["node_a"][0], col, lw=1.4, label=_label(c, name))
        axes[0, 1].plot(t, r["node_ha"], col, lw=1.4); axes[1, 0].plot(t, r["node_hp"], col, lw=1.4); axes[1, 1].plot(t, r["node_e"], col, lw=1.4)
    g = R["gain_75"]; ia = int(np.argmax(g["node_a"]))
    axes[0, 0].plot(g["node_t"][ia] / 86400, g["node_a"][ia] - g["node_a"][0], "k*", ms=10,
                    label=f"gain-case peak {g['node_a'][ia]-g['node_a'][0]:+.2f} km, day {g['node_t'][ia]/86400:.1f}")
    axes[0, 0].axhline(0, color="k", lw=0.5); axes[0, 0].legend(fontsize=7)
    for ax, yl in ((axes[0, 0], "$\\Delta a$ (mean) [km]"), (axes[0, 1], "apogee altitude $h_a$ [km]"),
                   (axes[1, 0], "perigee altitude $h_p$ [km]"), (axes[1, 1], "eccentricity $e$")):
        ax.set_ylabel(yl); ax.set_xlabel("time [days]")
    fig.tight_layout(); fig.savefig(fig_path("r_elements_75d.png")); plt.close(fig)

    # --- cumulative work budget, gain case ----------------------------------
    r = R["gain_75"]; t = r["node_t"] / 86400
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(t, r["cum_W_srp"] / 1e3, "C0", lw=1.5, label="cumulative SRP work")
    ax.plot(t, r["cum_W_drag"] / 1e3, "C3", lw=1.5, label="cumulative drag work")
    ax.plot(t, (r["cum_W_srp"] + r["cum_W_drag"]) / 1e3, "k", lw=1.5, label="cumulative total")
    ax.axhline(0, color="k", lw=0.5); ax.set_xlabel("time [days]"); ax.set_ylabel("specific work [kJ kg$^{-1}$]")
    ax.set_title(_label(G, "gain case, 800 km")); ax.legend()
    fig.tight_layout(); fig.savefig(fig_path("r_cum_work_75d.png")); plt.close(fig)

    # --- early/late budget + FT/FN drift, gain case -------------------------
    el = out["long_horizon"]["gain_75"]["early_late"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    labels = ["SRP", "drag", "net"]
    early = [el["mean_W_srp_early_J_kg_orbit"], el["mean_W_drag_early_J_kg_orbit"], el["mean_W_net_early_J_kg_orbit"]]
    late = [el["mean_W_srp_late_J_kg_orbit"], el["mean_W_drag_late_J_kg_orbit"], el["mean_W_net_late_J_kg_orbit"]]
    x = np.arange(3); w = 0.36
    axes[0].bar(x - w / 2, early, w, label=f"early (first {el['window_orbits_20pct']} orbits)", color="C0")
    axes[0].bar(x + w / 2, late, w, label=f"late (last {el['window_orbits_20pct']} orbits)", color="C3")
    axes[0].axhline(0, color="k", lw=0.5); axes[0].set_xticks(x); axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("orbit-mean specific work [J kg$^{-1}$ orbit$^{-1}$]"); axes[0].legend(); axes[0].set_title("Orbit-averaged work budget")
    axes[1].plot(t, r["orb_FT_srp"] * 1e6, "C0", lw=1.3, label="orbit-mean $|a_T|$ (transverse)")
    axes[1].plot(t, r["orb_FN_srp"] * 1e6, "C3", lw=1.3, label="orbit-mean $|a_N|$ (normal)")
    axes[1].set_xlabel("time [days]"); axes[1].set_ylabel("SRP acceleration component [µm s$^{-2}$]"); axes[1].legend()
    axes[1].set_title("SRP projection drift (inertially fixed normal)")
    fig.tight_layout(); fig.savefig(fig_path("r_earlylate_ftfn.png")); plt.close(fig)
    print("figures written")


if __name__ == "__main__":
    main()
