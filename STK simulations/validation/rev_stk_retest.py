"""
Revision re-test of the STK Astrogator cross-validation (Reviewer 1 major 3,
Reviewer 2 major 2/3).

A. Drag: re-run the attitude-independent validation configuration (J2 +
   spherical US-1976 drag, no SRP) at 700 and 800 km and READ BACK the
   effective spacecraft properties (drag area, Cd, mass) and the atmospheric
   density STK actually applied, so the -7 km vs -84 km discrepancy of the
   original submission can be attributed.  If an input did not take, set it
   explicitly and re-run.
B. SRP attitude coupling: build the N-plate SRP case (no drag) and read back
   STK's effective SRP area under (i) the eProfileFixedInAxes profile used in
   the submission, (ii) every other inertial-type attitude profile the build
   exposes, and (iii) a Sun-tracking plate type if the plate-file grammar
   accepts one.  The 2-day J2+SRP mean-SMA response tells whether any SRP
   force was applied at all.
C. Record exact versions.

Writes results/revision/stk_retest.json.  Needs the FlexNet server on
1055@localhost (see ../STK_Setup_Documentation.md) and ANSYSLMD_LICENSE_FILE.
"""
from __future__ import annotations
import os, sys, math, json, time, traceback
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
os.environ.setdefault("ANSYSLMD_LICENSE_FILE", "1055@localhost")
import numpy as np
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs, NPLATE_DIR
from core.attitude import inertial_sail_normal, normal_to_quaternion_eci
from core.orbit_init import sun_direction_eci, raan_from_ltan
from core.offline_propagator import SailCase, propagate, JD_EPOCH
from plugins.flatplate_drag_hpop import density_us1976_kg_m3

EPOCH = "1 Jan 2026 12:00:00.000"; RE = 6378.1363
LTAN, PITCH = 14.0, 34.0
RAAN = raan_from_ltan(LTAN, JD_EPOCH)
OUT = os.path.join(_ROOT, "results", "revision", "stk_retest.json")
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)


def orbit_average(t, a, period):
    dt = t[1] - t[0]; w = max(1, int(round(period / dt)))
    if w >= len(a): return t, a
    am = np.convolve(a, np.ones(w) / w, mode="valid")
    return t[(w - 1) // 2:(w - 1) // 2 + len(am)], am


def classical_sma(sat, days, step=60.0):
    stop = _add_seconds_to_iso(EPOCH, days * 86400.0)
    grp = sat.DataProviders.Item("Classical Elements").Group.Item("ICRF")
    ds = grp.ExecElements(EPOCH, stop, step, ["Time", "Semi-major Axis"])
    for i in range(ds.DataSets.Count):
        if ds.DataSets.Item(i).ElementName == "Semi-major Axis":
            a = np.array(ds.DataSets.Item(i).GetValues(), dtype=float)
    t = np.arange(len(a)) * step
    return t, a


def av_series(sat, group, elems, days, step=60.0):
    """Astrogator Values provider, element by element (unknown names skipped)."""
    stop = _add_seconds_to_iso(EPOCH, days * 86400.0)
    out = {}
    try:
        g = sat.DataProviders.Item("Astrogator Values").Group.Item(group)
    except Exception as e:
        log(f"   (no Astrogator Values/{group}: {e})"); return out
    for el in elems:
        try:
            ds = g.ExecElements(EPOCH, stop, step, ["Time", el])
            for i in range(ds.DataSets.Count):
                d = ds.DataSets.Item(i)
                if d.ElementName == el:
                    v = np.array(d.GetValues(), dtype=float); out[el] = dict(first=float(v[0]), min=float(v.min()), max=float(v.max()), mean=float(v.mean()))
        except Exception:
            pass
    return out


def sp_readback(sat):
    """Values the Initial State segment holds after our assignments."""
    sp = sat.Propagator.MainSequence.Item("Initial State").SpacecraftParameters
    names = [m for m in dir(sp) if not m.startswith("_")]
    vals = {}
    for n in ("DryMass", "Mass", "Cd", "Cr", "DragArea", "SolarRadiationPressureArea", "RadiationPressureArea",
              "SRPArea", "RadiationPressureCoefficient", "K1", "K2", "FuelMass"):
        if n in names:
            try: vals[n] = getattr(sp, n)
            except Exception as e: vals[n] = f"<{e}>"
    return names, vals


def case(alt, days, name, disable_eclipse=False):
    inc = 98.31 if alt >= 750 else 98.17
    n = inertial_sail_normal(sun_direction_eci(JD_EPOCH), RAAN, inc, PITCH, 0.0)
    return RunCase(name=name, altitude_km=alt, inc_deg=inc, raan_deg=RAAN, sma_km=RE + alt, ecc=1e-4,
                   sail_normal_eci=n, epoch_iso=EPOCH, duration_sec=days * 86400.0, step_sec=60.0,
                   sail=SailParams(), disable_eclipse=disable_eclipse), n


def offline_spherical(alt, days):
    inc = 98.31 if alt >= 750 else 98.17
    r = propagate(SailCase(altitude_km=alt, inc_deg=inc, raan_deg=RAAN, pitch_deg=PITCH, use_srp=False,
                           drag_mode="spherical", dt=10.0), days)
    return r["da_at_14d"] if days >= 14 else r["da_final"]


def main():
    from agi.stk13.stkengine import STKEngine
    from agi.stk13 import stkobjects as o
    import agi.stk13 as agi
    res = dict(versions={}, A_drag=[], B_srp=[], log=LOG)
    app = STKEngine.StartApplication(noGraphics=True); root = app.NewObjectRoot()
    try:
        root.NewScenario("RevRetest")
        try: res["versions"]["stk_engine"] = str(root.ExecuteCommand("GetSTKVersion /").Item(0))
        except Exception as e: res["versions"]["stk_engine"] = f"<{e}>"
        res["versions"]["python"] = sys.version.split()[0]
        res["versions"]["agi_stk13_package"] = getattr(agi, "__version__", "n/a")
        log("versions:", res["versions"])

        # ---------------- A. spherical drag read-back ----------------------
        for alt in (700.0, 800.0):
            c, n = case(alt, 14.0, f"drag{int(alt)}")
            sat, drv = build_satellite(root, c, sat_name=f"Drag{int(alt)}", use_drag=True, use_srp=False, drag_model="spherical")
            names, before = sp_readback(sat)
            log(f"[A {alt:.0f}] SpacecraftParameters members: {names}")
            log(f"[A {alt:.0f}] values as built: {before}")
            t0 = time.time(); run_mcs(drv); wall = time.time() - t0
            t, a = classical_sma(sat, 14.0)
            period = 2 * math.pi * math.sqrt((RE + alt) ** 3 * 1e9 / 3.986004418e14)
            tt, am = orbit_average(t, a, period)
            da_stk = float(am[-1] - am[0])
            props = av_series(sat, "Spacecraft Properties", ["DragArea", "Cd", "Cr", "SRPArea", "RadPressureArea", "RadPressureCoefficient", "Mass", "DryMass", "TotalMass"], 14.0)
            env = av_series(sat, "Environment", ["AtmosDensity", "Density"], 14.0)
            da_off = offline_spherical(alt, 14.0)
            rho_tab = density_us1976_kg_m3(alt * 1e3)
            row = dict(altitude_km=alt, da14_stk_km=da_stk, da14_opensource_km=da_off, ratio_stk_over_opensource=da_stk / da_off if da_off else None,
                       spacecraft_params_as_built=before, effective_props=props, environment=env, tabulated_density=rho_tab, wall_s=wall)
            # implied ballistic coefficient if STK's density equals the table: ratio * (Cd A/m = 22)
            row["implied_CdA_over_m_if_table_density"] = 22.0 * row["ratio_stk_over_opensource"] if row["ratio_stk_over_opensource"] else None
            log(f"[A {alt:.0f}] STK da14={da_stk:+.3f} km | open-source {da_off:+.3f} km | ratio {row['ratio_stk_over_opensource']:.3f}")
            log(f"[A {alt:.0f}] effective props: {props}")
            log(f"[A {alt:.0f}] environment: {env}  (table rho={rho_tab:.3e})")
            res["A_drag"].append(row)

            # A2: force-set the spacecraft parameters explicitly and re-run
            try:
                sp = sat.Propagator.MainSequence.Item("Initial State").SpacecraftParameters
                set_log = {}
                for nm, val in (("DryMass", 10.0), ("Cd", 2.2), ("DragArea", 100.0), ("Cr", 1.7), ("SRPArea", 100.0)):
                    if nm in names:
                        try: setattr(sp, nm, val); set_log[nm] = getattr(sp, nm)
                        except Exception as e: set_log[nm] = f"<{e}>"
                log(f"[A2 {alt:.0f}] explicit set -> {set_log}")
                run_mcs(drv)
                t, a = classical_sma(sat, 14.0); tt, am = orbit_average(t, a, period)
                da2 = float(am[-1] - am[0]); props2 = av_series(sat, "Spacecraft Properties", ["DragArea", "Cd", "Mass", "DryMass", "TotalMass"], 14.0)
                log(f"[A2 {alt:.0f}] after explicit set: STK da14={da2:+.3f} km (open-source {da_off:+.3f}); props {props2}")
                res["A_drag"].append(dict(altitude_km=alt, variant="explicit spacecraft parameters", set=set_log, da14_stk_km=da2, da14_opensource_km=da_off, effective_props=props2))
            except Exception as e:
                log(f"[A2 {alt:.0f}] failed: {e}")

        # ---------------- B. N-plate SRP attitude coupling -----------------
        c, n = case(800.0, 2.0, "srp800")
        q = normal_to_quaternion_eci(n)
        profiles = [m for m in dir(o.AgEVeProfile) if m.startswith("eProfile") and not m.startswith("_")]
        log(f"[B] attitude profile enum members: {profiles}")
        sun0 = sun_direction_eci(JD_EPOCH)
        log(f"[B] intended normal {tuple(round(x,4) for x in n)}, cos(alpha)={sum(a*b for a,b in zip(n,sun0)):.4f} (expect cos 34 deg = 0.829)")

        def srp_trial(label, configure):
            try:
                sat, drv = build_satellite(root, c, sat_name="Srp", use_drag=False, use_srp=True)
                note = configure(sat)
                t0 = time.time(); run_mcs(drv); wall = time.time() - t0
                t, a = classical_sma(sat, 2.0)
                period = 2 * math.pi * math.sqrt((RE + 800.0) ** 3 * 1e9 / 3.986004418e14)
                tt, am = orbit_average(t, a, period)
                props = av_series(sat, "Spacecraft Properties", ["SRPArea", "RadPressureArea", "RadPressureCoefficient", "Cr"], 2.0)
                row = dict(label=label, note=note, da2d_mean_km=float(am[-1] - am[0]), effective_props=props, wall_s=wall)
                log(f"[B] {label:48s} da(2d)={row['da2d_mean_km']:+.4f} km  props={props}  {note}")
                res["B_srp"].append(row)
            except Exception as e:
                log(f"[B] {label}: FAILED {type(e).__name__}: {str(e)[:200]}")
                res["B_srp"].append(dict(label=label, error=str(e)[:300]))

        srp_trial("baseline: eProfileFixedInAxes (ICRF) + body plate", lambda sat: "as submitted")
        # J2-only reference for the SRP response
        try:
            sat0, drv0 = build_satellite(root, c, sat_name="J2only", use_drag=False, use_srp=False)
            run_mcs(drv0); t, a = classical_sma(sat0, 2.0)
            period = 2 * math.pi * math.sqrt((RE + 800.0) ** 3 * 1e9 / 3.986004418e14); tt, am = orbit_average(t, a, period)
            res["B_j2only_da2d_km"] = float(am[-1] - am[0]); log(f"[B] J2-only reference da(2d)={res['B_j2only_da2d_km']:+.4f} km")
        except Exception as e:
            log(f"[B] J2-only reference failed: {e}")
        # open-source SRP-only 2-day response for comparison
        try:
            r = propagate(SailCase(altitude_km=800.0, inc_deg=98.31, raan_deg=RAAN, pitch_deg=PITCH, use_drag=False, dt=10.0), 2.0)
            res["B_opensource_srp_only_da2d_km"] = r["da_final"]; log(f"[B] open-source J2+SRP (no drag) da(2d)={r['da_final']:+.4f} km")
        except Exception as e:
            log(f"[B] open-source reference failed: {e}")

        # alternative inertial profiles
        for pname in profiles:
            if pname in ("eProfileFixedInAxes",) or "Inertial" not in pname and "Fixed" not in pname:
                continue
            def cfg(sat, pname=pname):
                basic = sat.Attitude.Basic
                basic.SetProfileType(getattr(o.AgEVeProfile, pname))
                prof = basic.Profile
                done = []
                for ax in ("CentralBody/Earth ICRF", "CentralBody/Earth Inertial", "CentralBody/Earth J2000"):
                    try: prof.ReferenceAxes = ax; done.append(f"axes={ax}"); break
                    except Exception: pass
                try: prof.Orientation.AssignQuaternion(*q); done.append("quaternion assigned")
                except Exception as e: done.append(f"no quaternion ({str(e)[:60]})")
                return "; ".join(done)
            srp_trial(f"profile {pname}", cfg)

        # plate-file grammar: Sun-tracking plate type (diagnostic only)
        for code in ("S", "Sun", "I"):
            def cfg_plate(sat, code=code):
                from pathlib import Path
                p = Path(NPLATE_DIR) / f"srp800_type{code}.nplate"
                p.write_text("\n".join(["Version 1.0", "Formulation SRP", "Begin Plates",
                                        f"  Sail  Sail  {code}  100.000000  0.000000 0.000000 1.000000  0.700000  0.000000",
                                        "End Plates", ""]), encoding="utf-8")
                cd = root.CurrentScenario.ComponentDirectory
                prop = cd.GetComponents(2).GetFolder("Propagators").Item("SailProp_Srp")
                pf = prop.PropagatorFunctions
                for i in range(pf.Count):
                    it = pf.Item(i)
                    if getattr(it, "Name", "") == "NPlate SRP":
                        it.NPlateDefinitionFile = str(p); return f"plate type code '{code}' accepted"
                return "NPlate SRP function not found"
            srp_trial(f"plate type code '{code}' (grammar probe)", cfg_plate)
    finally:
        app.ShutDown()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    log("wrote", OUT)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
