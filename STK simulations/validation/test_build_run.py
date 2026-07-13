"""
End-to-end pipeline test: build the gain-anchor Astrogator satellite (J2 +
US-1976 N-plate drag + N-plate SRP), run a short MCS, extract SMA.

Usage:  python validation/test_build_run.py [duration_days]   (default 1)
"""
from __future__ import annotations
import math, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from agi.stk13 import stkobjects as o
from agi.stk13.stkengine import STKEngine
from core.scenario_builder import RunCase, SailParams, _add_seconds_to_iso
from core.astrogator_mcs import build_satellite, run_mcs
from core.orbit_init import julian_date_from_ymdhms, sun_direction_eci
from core.attitude import inertial_sail_normal

DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
ALT = float(sys.argv[2]) if len(sys.argv) > 2 else 700.0
PITCH = float(sys.argv[3]) if len(sys.argv) > 3 else 24.8
EPOCH = "1 Jan 2026 12:00:00.000"
RE_KM = 6378.1363


def anchor_case(duration_days):
    jd = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)
    sun_unit = sun_direction_eci(jd)
    inc = 98.31 if ALT >= 750 else 98.17
    raan = 285.5
    n = inertial_sail_normal(sun_unit, raan, inc, PITCH, 0.0)
    return RunCase(
        name="anchor_test", altitude_km=ALT, inc_deg=inc, raan_deg=raan,
        sma_km=RE_KM + ALT, ecc=1e-4, aop_deg=0.0, ta_deg=0.0,
        sail_normal_eci=n, epoch_iso=EPOCH,
        duration_sec=duration_days * 86400.0, step_sec=60.0, sail=SailParams(),
    )


def main():
    case = anchor_case(DAYS)
    print(f"anchor sail_normal_eci = {case.sail_normal_eci}")
    app = STKEngine.StartApplication(noGraphics=True)
    root = app.NewObjectRoot()
    try:
        root.NewScenario("BuildTest")
        sat, driver = build_satellite(root, case, sat_name="Sat")

        # confirm the Keplerian element read back correctly
        init = driver.MainSequence.Item("Initial State")
        el = init.Element
        elmembers = [m for m in dir(el) if not m.startswith("_")]
        print("Keplerian element members:", elmembers)
        for m in elmembers:
            try:
                v = getattr(el, m)
                if isinstance(v, (int, float)):
                    print(f"   {m} = {v}")
            except Exception:
                pass

        print(f"\nRunning MCS for {DAYS} day(s)...")
        run_mcs(driver)
        print("RunMCS OK.")

        stop_iso = _add_seconds_to_iso(EPOCH, case.duration_sec)
        grp = sat.DataProviders.Item("Brouwer-Lyd Mean Long").Group.Item("ICRF")
        cols = ["Time", "Mean Semi-major Axis", "Mean Eccentricity"]
        ds = grp.ExecElements(EPOCH, stop_iso, case.step_sec, cols)
        data = {}
        for i in range(ds.DataSets.Count):
            d = ds.DataSets.Item(i)
            data[d.ElementName] = list(d.GetValues())
        sma = data.get("Mean Semi-major Axis", [])
        ecc = data.get("Mean Eccentricity", [])
        tvals = data.get("Time", [])
        print(f"\nExtracted {len(sma)} MEAN samples.")
        if sma:
            a0 = sma[0]
            damax = max(sma) - a0
            i_max = sma.index(max(sma))
            t_max_day = i_max * case.step_sec / 86400.0
            print(f"  mean a[0]   = {a0:.4f} km")
            print(f"  mean a[-1]  = {sma[-1]:.4f} km   (delta {sma[-1]-a0:+.4f} km)")
            print(f"  mean a_max  = {max(sma):.4f} km   -> da_max = {damax:+.4f} km"
                  f" at t={t_max_day:.2f} d   (paper 14d anchor +14.958 km)")
            print(f"  mean e[0]={ecc[0]:.3e}  e[-1]={ecc[-1]:.3e}")
    finally:
        try: app.ShutDown()
        except Exception: pass


if __name__ == "__main__":
    main()
