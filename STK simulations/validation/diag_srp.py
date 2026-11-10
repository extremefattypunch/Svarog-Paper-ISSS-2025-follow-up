"""
Diagnose whether the N-plate SRP force is actually being applied.

Builds the anchor case, prints the SRP + drag force-function state, verifies the
.nplate files exist, then runs 2-day propagations in four configurations
(J2-only, SRP-only, drag-only, full) and reports the SMA behaviour of each.
"""
from __future__ import annotations
import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from agi.stk13 import stkobjects as o
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal

EPOCH = "1 Jan 2026 12:00:00.000"
DAYS = 2.0


def anchor_case(use_drag, use_srp, name):
    jd = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)
    n = inertial_sail_normal(sun_direction_eci(jd), 285.5, 98.17, 24.8, 0.0)
    return RunCase(name=name, altitude_km=700.0, inc_deg=98.17, raan_deg=285.5,
                   sma_km=7078.137, ecc=1e-4, sail_normal_eci=n, epoch_iso=EPOCH,
                   duration_sec=DAYS * 86400.0, step_sec=60.0, sail=SailParams())


def sma_series(sat, dur, provider="Classical Elements", elem="Semi-major Axis"):
    stop_iso = _add_seconds_to_iso(EPOCH, dur)
    grp = sat.DataProviders.Item(provider).Group.Item("ICRF")
    ds = grp.ExecElements(EPOCH, stop_iso, 60.0, ["Time", elem])
    for i in range(ds.DataSets.Count):
        d = ds.DataSets.Item(i)
        if d.ElementName == elem:
            return list(d.GetValues())
    return []


def run_config(root, use_drag, use_srp, label, inspect=False):
    case = anchor_case(use_drag, use_srp, label.replace(" ", "_"))
    sat, driver = build_satellite(root, case, sat_name="Sat",
                                  use_drag=use_drag, use_srp=use_srp)
    if inspect:
        from agi.stk13.stkobjects import astrogator as astro
        props = root.CurrentScenario.ComponentDirectory.GetComponents(2).GetFolder("Propagators")
        pf = props.Item("SailProp_Sat").PropagatorFunctions
        print("  propagator functions:", [pf.Item(i).Name for i in range(pf.Count)])
        for i in range(pf.Count):
            it = pf.Item(i); nm = it.Name
            if "SRP" in nm or "Radiation" in type(it).__name__:
                for a in ("NPlateDefinitionFile", "MeanFlux", "ShadowModel", "SolarForceMethod"):
                    try: print(f"    SRP.{a} = {getattr(it, a)!r}")
                    except Exception as e: print(f"    SRP.{a}: {e}")
                f = getattr(it, "NPlateDefinitionFile", "")
                print(f"    SRP file exists: {os.path.exists(str(f))}")
            if "Atmos" in nm or "Standard" in nm or hasattr(it, "DragModelType"):
                for a in ("DragModelType", "NPlateDefinitionFile"):
                    try: print(f"    DRAG.{a} = {getattr(it, a)!r}")
                    except Exception as e: print(f"    DRAG.{a}: {e}")
                f = getattr(it, "NPlateDefinitionFile", "")
                print(f"    DRAG file exists: {os.path.exists(str(f))}")
    run_mcs(driver)
    osc = sma_series(sat, case.duration_sec, "Classical Elements", "Semi-major Axis")
    mean = sma_series(sat, case.duration_sec, "Brouwer-Lyd Mean Long", "Mean Semi-major Axis")
    if mean:
        a0 = mean[0]
        print(f"[{label:10s}] MEAN a0={a0:.3f} a_end={mean[-1]:.3f} "
              f"da_end={mean[-1]-a0:+.4f} da_max={max(x-a0 for x in mean):+.4f} "
              f"da_min={min(x-a0 for x in mean):+.4f} amp={max(mean)-min(mean):.4f} km")
    if osc:
        print(f"             OSC  a0={osc[0]:.3f} amp={max(osc)-min(osc):.3f} km (J2 short-period)")
    return mean


def main():
    app = STKEngine.StartApplication(noGraphics=True)
    root = app.NewObjectRoot()
    try:
        root.NewScenario("DiagSRP")
        print(f"--- {DAYS}-day diagnostics (SMA behaviour by force config) ---")
        run_config(root, False, False, "J2-only")
        run_config(root, False, True, "SRP-only", inspect=True)
        run_config(root, True, False, "drag-only")
        run_config(root, True, True, "full")
    finally:
        try: app.ShutDown()
        except Exception: pass


if __name__ == "__main__":
    main()
