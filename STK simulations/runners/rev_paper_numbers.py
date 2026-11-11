"""
Aggregate every number the revised manuscript quotes into one flat JSON
(results/revision/paper_numbers.json) and print it.  Each entry names the
result file it came from, so a quoted value can be traced in one step.

Usage: python runners/rev_paper_numbers.py
"""
from __future__ import annotations
import os, sys, json
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
import numpy as np
from runners.rev_common import RESULTS, PAPER_ROOT, save_json

OREKIT = os.path.join(PAPER_ROOT, "Orekit simulations", "results")
N = {}


def put(key, value, src):
    if isinstance(value, (np.floating, np.integer)): value = value.item()
    N[key] = dict(value=value, src=src)


def lj(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    # ---- maps ----------------------------------------------------------
    p = os.path.join(RESULTS, "maps_summary.json")
    if os.path.exists(p):
        ms = lj(p)
        for s in (ms if isinstance(ms, list) else ms.get("maps", ms.values())):
            a = int(s["altitude_km"])
            put(f"map{a}.n_cells", s["n_cells"], p); put(f"map{a}.n_positive", s["n_positive"], p)
            put(f"map{a}.frac_positive_pct", 100 * s["frac_positive"], p)
            put(f"map{a}.peak_km", s["peak_da_max_km"], p); put(f"map{a}.peak_ltan_h", s["peak_ltan_h"], p)
            put(f"map{a}.peak_pitch_deg", s["peak_pitch_deg"], p); put(f"map{a}.min_da14_km", s["min_da14_km"], p)
            put(f"map{a}.n_lobes", len(s.get("lobes", [])), p)
            for i, lb in enumerate(s.get("lobes", [])):
                for k, v in lb.items():
                    if isinstance(v, (int, float)): put(f"map{a}.lobe{i}.{k}", v, p)
    # ---- cases ---------------------------------------------------------
    p = os.path.join(RESULTS, "cases.json")
    if os.path.exists(p):
        c = lj(p)
        for name in ("gain", "neutral", "decay", "legacy700"):
            for k, v in c["cases"][name].items():
                if isinstance(v, (int, float)): put(f"case.{name}.{k}", v, p)
        put("case.drag_only_800_da14_km", c["cases"]["drag_only_800_da14_km"], p)
        for k, row in c["eclipse_causality_14d"].items():
            for kk, v in row.items():
                if isinstance(v, (int, float)): put(f"ecl14.{k}.{kk}", v, p)
        for k, row in c["long_horizon"].items():
            for kk, v in row.items():
                if isinstance(v, (int, float)): put(f"long.{k}.{kk}", v, p)
                elif isinstance(v, dict):
                    for k3, v3 in v.items():
                        if isinstance(v3, (int, float)): put(f"long.{k}.{kk}.{k3}", v3, p)
        for k, row in c["one_orbit"].items():
            for kk, v in row.items():
                if isinstance(v, (int, float)): put(f"orbit.{k}.{kk}", v, p)
    # ---- sensitivity ---------------------------------------------------
    p = os.path.join(RESULTS, "sensitivity.json")
    if os.path.exists(p):
        s = lj(p)
        for kind, alts in s["sweeps"].items():
            for alt, pts in alts.items():
                for pt in pts:
                    put(f"sens.{kind}.{alt}.x{pt['x']:g}.da_max_km", pt["da_max_km"], p)
    # ---- convergence ---------------------------------------------------
    p = os.path.join(RESULTS, "convergence.json")
    if os.path.exists(p):
        cv = lj(p)
        for r in cv["rows"]:
            put(f"conv.{int(r['altitude_km'])}.{r['config'][:9].strip().replace(' ', '_')}.dt{r['dt_s']:g}.da14_km", r["da_at_14d_km"], p)
            put(f"conv.{int(r['altitude_km'])}.{r['config'][:9].strip().replace(' ', '_')}.dt{r['dt_s']:g}.da_max_km", r["da_max_km"], p)
    # ---- STK -----------------------------------------------------------
    p = os.path.join(RESULTS, "stk_validation.json")
    if os.path.exists(p):
        sv = lj(p)
        put("stk.engine", sv["stk_engine"], p)
        for r in sv["rows"]:
            for k in ("stk_da_end_km", "opensource_da_end_km", "stk_da_max_km", "opensource_da_max_km", "max_abs_diff_km", "rms_diff_km",
                      "stk_srp_area_first_m2", "stk_drag_area_first_m2"):
                if r.get(k) is not None: put(f"stk.{r['name']}.{k}", r[k], p)
            if r.get("density_tabulation") and "ratio_mean" in r["density_tabulation"]:
                for k in ("ratio_mean", "ratio_min", "ratio_max", "stk_rho_first", "ours_rho_first", "h_min_km", "h_max_km"):
                    put(f"stk.{r['name']}.density.{k}", r["density_tabulation"][k], p)
    p = os.path.join(RESULTS, "stk_probe.json")
    if os.path.exists(p):
        sp = lj(p)
        for r in sp["drag"]: put(f"stkprobe.drag.{r['label'][:24].replace(' ', '_')}.ratio", r["ratio_to_opensource"], p)
        for r in sp["srp"]:
            if isinstance(r.get("srp_area"), dict): put(f"stkprobe.srp.{r['label'][:24].replace(' ', '_')}.area_first_m2", r["srp_area"]["first"], p)
            put(f"stkprobe.srp.{r['label'][:24].replace(' ', '_')}.da3d_km", r["da_km"], p)
    # ---- Orekit --------------------------------------------------------
    p = os.path.join(RESULTS, "orekit_map_compare.json")
    if os.path.exists(p):
        for k, v in lj(p).items():
            if isinstance(v, (int, float)): put(f"orekitmap.{k}", v, p)
            elif isinstance(v, dict):
                for kk, vv in v.items(): put(f"orekitmap.{k}.{kk}", vv, p)
    p = os.path.join(OREKIT, "v2_crossvalidation.json")
    if os.path.exists(p):
        for r in lj(p)["rows"]:
            tag = f"v2.{r['config'].replace(' ', '_').replace('+', 'p')}.{int(r['altitude_km'])}"
            for k in ("orekit_da14_node_km", "paper_da14_node_km", "max_abs_diff_km", "orekit_da14_orbitavg_km"): put(f"{tag}.{k}", r[k], p)
    p = os.path.join(OREKIT, "v6_drag_decomposition.json")
    if os.path.exists(p):
        rows = lj(p)["rows"]
        base = {int(r["altitude_km"]): r["da_node_km"] for r in rows if r["config"].startswith("baseline")}
        for r in rows:
            a = int(r["altitude_km"]); tag = f"v6.{a}.{r['config'][:28].replace(' ', '_')}"
            put(f"{tag}.da_km", r["da_node_km"], p); put(f"{tag}.ratio", r["da_node_km"] / base[a], p)
            if r.get("reentered"): put(f"{tag}.reentry_span_days", r["span_days"], p)
    p = os.path.join(OREKIT, "v7_eclipse_discontinuity.json")
    if os.path.exists(p):
        v7 = lj(p)
        for cfg, rows in v7["fixed_step"].items():
            for r in rows: put(f"v7.{cfg[:10].replace(' ', '_')}.dt{r['dt_s']:g}.da14_km", r["da_final_km"], p)
        for cfg, v in v7["reference"].items(): put(f"v7.{cfg[:10].replace(' ', '_')}.dp853_km", v, p)
        for cfg, v in v7["order"].items(): put(f"v7.{cfg[:10].replace(' ', '_')}.order", v, p)
    p = os.path.join(OREKIT, "v8_srp_crossvalidation.json")
    if os.path.exists(p):
        for r in lj(p)["rows"]:
            for k in ("paper_da_final_km", "orekit_paper_sun_da_final_km", "orekit_de440_da_final_km", "max_abs_diff_propagators_km", "max_abs_diff_ephemeris_km"):
                put(f"v8.{int(r['altitude_km'])}.{k}", r[k], p)
    p = os.path.join(OREKIT, "v9_analytic_drag.json")
    if os.path.exists(p):
        for r in lj(p)["rows"]:
            for k in ("analytic_da14_km", "propagated_da14_km", "rel_diff"): put(f"v9.{int(r['altitude_km'])}.{k}", r[k], p)
    for fn, pre in (("long_horizon.json", "oreklong"), ("eclipse_causality.json", "orekecl")):
        p = os.path.join(OREKIT, fn)
        if os.path.exists(p):
            for i, r in enumerate(lj(p)["rows"]):
                tag = f"{pre}.{int(r['altitude_km'])}" + (f".ecl{'off' if r.get('eclipse_off') else 'on'}" if "eclipse_off" in r else "")
                for k, v in r.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool): put(f"{tag}.{k}", v, p)
    p = os.path.join(OREKIT, "srp_power.json")
    if os.path.exists(p):
        for k, v in lj(p).items():
            if isinstance(v, (int, float)) and not k.startswith("manuscript"): put(f"orekpower.{k}", v, p)
    p = os.path.join(OREKIT, "v10_space_weather.json")
    if os.path.exists(p):
        for r in lj(p)["rows"]:
            tag = f"v10.{int(r['altitude_km'])}.{r['label'][:22].replace(' ', '_')}.srp{'on' if r['use_srp'] else 'off'}"
            put(f"{tag}.da_max_km", r["da_max_km"], p); put(f"{tag}.da14_km", r["da_final_km"], p)
            if r.get("reentered"): put(f"{tag}.reentry_span_days", r["span_days"], p)
    p = os.path.join(OREKIT, "v4_srp_attitude_coupling.json")
    if os.path.exists(p):
        d = lj(p)
        for k, v in d.items():
            if isinstance(v, (int, float)): put(f"v4.{k}", v, p)
    p = os.path.join(OREKIT, "v5_calibration_gate.json")
    if os.path.exists(p):
        d = lj(p)
        for k, v in d.items():
            if isinstance(v, (int, float)): put(f"v5.{k}", v, p)
    p = os.path.join(OREKIT, "v1_component_gates.json")
    if os.path.exists(p):
        d = lj(p)
        for k, v in d.items():
            if isinstance(v, (int, float)): put(f"v1.{k}", v, p)

    save_json("paper_numbers.json", N)
    w = max(len(k) for k in N)
    for k in sorted(N):
        v = N[k]["value"]
        print(f"{k:{w}s} = {v:.6g}" if isinstance(v, float) else f"{k:{w}s} = {v}")
    print(f"\n{len(N)} numbers -> results/revision/paper_numbers.json")


if __name__ == "__main__":
    main()
