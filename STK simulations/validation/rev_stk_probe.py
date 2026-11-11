"""
Quick diagnostic probes (3-day runs) to attribute the two STK discrepancies.
results/revision/stk_probe.json is the diagnostic snapshot taken BEFORE the fixes
in core/astrogator_mcs.py; the script re-creates the submitted build explicitly
(zero_fuel=False, scalar-first quaternion) so that re-running it reproduces it.

1. Drag ballistic coefficient: vary DryMass, DragArea, Cd and the fuel tank one
   at a time and measure the 3-day mean-SMA decay.  If the decay scales with
   DragArea and Cd but not 1/DryMass, the mass STK propagates is not DryMass.
2. SRP attitude coupling: read back the attitude profile's reference axes and
   compare the effective SRP area STK reports (Astrogator Values / Spacecraft
   Properties / SRPArea) with A cos(alpha) = 82.9 m^2 for (i) the quaternion
   order used in the submission (qs, qx, qy, qz) and (ii) the Object-Model
   order (qx, qy, qz, qs).
"""
from __future__ import annotations
import os, sys, math, json, time, traceback
_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
os.environ.setdefault("ANSYSLMD_LICENSE_FILE", "1055@localhost")
import numpy as np
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.attitude import inertial_sail_normal, normal_to_quaternion_eci
from core.orbit_init import sun_direction_eci, raan_from_ltan
from core.offline_propagator import SailCase, propagate, JD_EPOCH

EPOCH = "1 Jan 2026 12:00:00.000"; RE = 6378.1363; MU = 3.986004418e14
LTAN, PITCH = 14.0, 34.0; RAAN = raan_from_ltan(LTAN, JD_EPOCH); ALT = 800.0; INC = 98.31
DAYS = 3.0
OUT = os.path.join(_ROOT, "results", "revision", "stk_probe.json")
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)


def period_of(alt): return 2 * math.pi * math.sqrt((RE + alt) ** 3 * 1e9 / MU)


def orbit_average(t, a, period):
    dt = t[1] - t[0]; w = max(1, int(round(period / dt)))
    am = np.convolve(a, np.ones(w) / w, mode="valid")
    return t[(w - 1) // 2:(w - 1) // 2 + len(am)], am


def mean_da(sat, days, step=60.0):
    stop = _add_seconds_to_iso(EPOCH, days * 86400.0)
    grp = sat.DataProviders.Item("Classical Elements").Group.Item("ICRF")
    ds = grp.ExecElements(EPOCH, stop, step, ["Time", "Semi-major Axis"])
    for i in range(ds.DataSets.Count):
        if ds.DataSets.Item(i).ElementName == "Semi-major Axis":
            a = np.array(ds.DataSets.Item(i).GetValues(), dtype=float)
    t = np.arange(len(a)) * step; tt, am = orbit_average(t, a, period_of(ALT))
    return float(am[-1] - am[0])


def av(sat, group, el, days, step=60.0):
    stop = _add_seconds_to_iso(EPOCH, days * 86400.0)
    try:
        g = sat.DataProviders.Item("Astrogator Values").Group.Item(group)
        ds = g.ExecElements(EPOCH, stop, step, ["Time", el])
        for i in range(ds.DataSets.Count):
            d = ds.DataSets.Item(i)
            if d.ElementName == el:
                v = np.array(d.GetValues(), dtype=float)
                return dict(first=float(v[0]), min=float(v.min()), max=float(v.max()), mean=float(v.mean()))
    except Exception as e:
        return f"<{str(e)[:80]}>"


def case(name, disable_eclipse=False):
    n = inertial_sail_normal(sun_direction_eci(JD_EPOCH), RAAN, INC, PITCH, 0.0)
    return RunCase(name=name, altitude_km=ALT, inc_deg=INC, raan_deg=RAAN, sma_km=RE + ALT, ecc=1e-4,
                   sail_normal_eci=n, epoch_iso=EPOCH, duration_sec=DAYS * 86400.0, step_sec=60.0,
                   sail=SailParams(), disable_eclipse=disable_eclipse), n


def main():
    from agi.stk13.stkengine import STKEngine
    res = dict(log=LOG, drag=[], srp=[])
    app = STKEngine.StartApplication(noGraphics=True); root = app.NewObjectRoot()
    try:
        root.NewScenario("RevProbe")
        off = propagate(SailCase(altitude_km=ALT, inc_deg=INC, raan_deg=RAAN, pitch_deg=PITCH, use_srp=False,
                                 drag_mode="spherical", dt=10.0), DAYS)["da_final"]
        log(f"open-source spherical drag, {DAYS:.0f} d: {off:+.4f} km")

        # ---------- 1. ballistic-coefficient probes -------------------------
        def drag_trial(label, mutate):
            c, _ = case("prb")
            # zero_fuel=False reproduces the SUBMITTED build (default 50 kg fuel load); the
            # "fuel tank zeroed" trial empties the tank through its own mutate()
            sat, drv = build_satellite(root, c, sat_name="Prb", use_drag=True, use_srp=False, drag_model="spherical",
                                       zero_fuel=False)
            init = sat.Propagator.MainSequence.Item("Initial State")
            note = mutate(init)
            run_mcs(drv)
            da = mean_da(sat, DAYS)
            row = dict(label=label, note=note, da_km=da, ratio_to_opensource=da / off)
            log(f"[drag] {label:34s} da({DAYS:.0f}d)={da:+.4f} km  ratio {da/off:.3f}  {note}")
            res["drag"].append(row)
            return da

        def tank_info(init):
            try:
                tk = init.FuelTank
                return {n: getattr(tk, n) for n in dir(tk) if not n.startswith("_") and isinstance(getattr(tk, n, None), (int, float))}
            except Exception as e:
                return f"<no FuelTank: {str(e)[:60]}>"

        base = drag_trial("baseline (as built)", lambda init: f"tank={tank_info(init)}")
        drag_trial("DryMass 10 -> 1 kg", lambda init: (setattr(init.SpacecraftParameters, "DryMass", 1.0), f"DryMass={init.SpacecraftParameters.DryMass}")[1])
        drag_trial("DragArea 100 -> 1000 m^2", lambda init: (setattr(init.SpacecraftParameters, "DragArea", 1000.0), f"DragArea={init.SpacecraftParameters.DragArea}")[1])
        drag_trial("Cd 2.2 -> 22", lambda init: (setattr(init.SpacecraftParameters, "Cd", 22.0), f"Cd={init.SpacecraftParameters.Cd}")[1])

        def zero_fuel(init):
            out = {}
            try:
                tk = init.FuelTank
                for n in ("FuelMass", "MaximumFuelMass"):
                    try: setattr(tk, n, 0.0); out[n] = getattr(tk, n)
                    except Exception as e: out[n] = f"<{str(e)[:50]}>"
            except Exception as e:
                out["FuelTank"] = f"<{str(e)[:50]}>"
            return f"fuel->{out}"
        drag_trial("fuel tank zeroed", zero_fuel)
        drag_trial("K1 -> 10", lambda init: (setattr(init.SpacecraftParameters, "K1", 10.0), f"K1={init.SpacecraftParameters.K1}")[1])

        # ---------- 2. SRP attitude coupling ---------------------------------
        off_srp = propagate(SailCase(altitude_km=ALT, inc_deg=INC, raan_deg=RAAN, pitch_deg=PITCH, use_drag=False, dt=10.0), DAYS)["da_final"]
        log(f"open-source J2+SRP (no drag), {DAYS:.0f} d: {off_srp:+.4f} km")
        c, n = case("srp"); q = normal_to_quaternion_eci(n)
        sun0 = sun_direction_eci(JD_EPOCH); cosA = float(np.dot(n, sun0))
        log(f"intended normal {np.round(n,4).tolist()}  cos(alpha)={cosA:.4f}  expected SRPArea={100*cosA:.2f} m^2  quaternion (qs,qx,qy,qz)={np.round(q,5).tolist()}")

        def srp_trial(label, assign):
            sat, drv = build_satellite(root, c, sat_name="Srp", use_drag=False, use_srp=True)
            init = sat.Propagator.MainSequence.Item("Initial State")
            zero_fuel(init)
            prof = sat.Attitude.Basic.Profile
            note = assign(prof)
            try: axes = prof.ReferenceAxes
            except Exception as e: axes = f"<{str(e)[:50]}>"
            run_mcs(drv)
            da = mean_da(sat, DAYS)
            area = av(sat, "Spacecraft Properties", "SRPArea", DAYS)
            row = dict(label=label, note=note, reference_axes=str(axes), da_km=da, srp_area=area)
            log(f"[srp] {label:40s} axes={axes}  da({DAYS:.0f}d)={da:+.4f} km (open-source {off_srp:+.4f})  SRPArea={area}  {note}")
            res["srp"].append(row)

        def as_submitted(prof):
            qs, qx, qy, qz = q
            prof.Orientation.AssignQuaternion(qs, qx, qy, qz); return "AssignQuaternion(qs,qx,qy,qz) (submitted order)"
        srp_trial("as built: AssignQuaternion(qs,qx,qy,qz)", as_submitted)
        def swapped(prof):
            qs, qx, qy, qz = q
            prof.Orientation.AssignQuaternion(qx, qy, qz, qs); return "AssignQuaternion(qx,qy,qz,qs)"
        srp_trial("Object-Model order (qx,qy,qz,qs)", swapped)
        def swapped_icrf(prof):
            qs, qx, qy, qz = q
            for ax in ("CentralBody/Earth ICRF", "CentralBody/Earth J2000", "CentralBody/Earth Inertial"):
                try: prof.ReferenceAxes = ax; break
                except Exception: continue
            prof.Orientation.AssignQuaternion(qx, qy, qz, qs); return f"axes set + (qx,qy,qz,qs)"
        srp_trial("(qx,qy,qz,qs) + explicit ICRF axes", swapped_icrf)
        def conj(prof):
            qs, qx, qy, qz = q
            for ax in ("CentralBody/Earth ICRF", "CentralBody/Earth J2000", "CentralBody/Earth Inertial"):
                try: prof.ReferenceAxes = ax; break
                except Exception: continue
            prof.Orientation.AssignQuaternion(-qx, -qy, -qz, qs); return "axes set + conjugate (-qx,-qy,-qz,qs)"
        srp_trial("conjugate (-qx,-qy,-qz,qs) + ICRF axes", conj)
        # read back body axes via quaternion data provider, if available
        try:
            sat = root.CurrentScenario.Children.Item("Srp")
            dp = sat.DataProviders.Item("Attitude Quaternions")
            ds = dp.Exec(EPOCH, _add_seconds_to_iso(EPOCH, 600.0), 300.0)
            names = [ds.DataSets.Item(i).ElementName for i in range(ds.DataSets.Count)]
            vals = {ds.DataSets.Item(i).ElementName: list(ds.DataSets.Item(i).GetValues())[:1] for i in range(ds.DataSets.Count)}
            log(f"Attitude Quaternions provider: {vals}")
            res["attitude_quaternions"] = {k: [float(x) for x in v] for k, v in vals.items() if k != "Time"}
        except Exception as e:
            log(f"Attitude Quaternions provider unavailable: {str(e)[:100]}")
    finally:
        app.ShutDown()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    log("wrote", OUT)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
