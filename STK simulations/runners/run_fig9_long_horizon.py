"""
Figure 9 — 75-day orbital element evolution for the representative gain case.

This runner is the **Phase 1 smoke test** for the entire pipeline. It exercises
the SRP + drag plugins, the inertial-attitude vector, the LTDN -> RAAN mapping,
the J2 + plugin force model, and the Classical Elements DataProvider extraction.

Acceptance gate (paper, breakdown.tex):
  a_peak  ~ 7098.211 km @ day 26.50  (within +/-1%)
  a_final ~ 7064.717 km @ day 75      (within +/-1%)
  ha_peak ~  864.548 km @ day 39.50  (within +/-2%)
  hp_min  ~  546.370 km @ day 42.17  (within +/-2%)
  e_peak  ~ 2.176e-2     @ day 40.72  (within +/-5%)

If this run reproduces those numbers, the plugins and core utilities are
correct and we can proceed to the rest of the figures. If not, the failure
is in the physics — most likely the SRP cos^2 factor, the eclipse hook,
or the inertial-attitude construction.

Usage:
    python -m runners.run_fig9_long_horizon
    python -m runners.run_fig9_long_horizon --duration-days 14   # quick check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is importable
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.attitude import inertial_sail_normal
from core.data_extract import extract_classical_elements, write_classical_csv
from core.orbit_init import (
    initial_classical_state,
    julian_date_from_ymdhms,
    sun_direction_eci,
)
from core.scenario_builder import RunCase, SailParams, build_satellite, propagate
from core.stk_session import stk_session


# Gain anchor (paper breakdown.tex)
LTDN_HOURS = 12.266
PITCH_DEG = 24.8
ROLL_DEG = 0.0
ALTITUDE_KM = 700.0
EPOCH_ISO = "1 Jan 2026 12:00:00.000"
EPOCH_JD = julian_date_from_ymdhms(2026, 1, 1, 12, 0, 0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration-days", type=float, default=75.0)
    p.add_argument("--step-sec", type=float, default=60.0)
    p.add_argument("--use-desktop", action="store_true",
                   help="Attach to STK Desktop instead of starting Engine")
    p.add_argument("--results-dir", type=Path,
                   default=_PROJECT_ROOT / "results" / "fig9")
    args = p.parse_args()

    results_dir = args.results_dir
    sidecar_dir = results_dir / "sidecar"
    results_dir.mkdir(parents=True, exist_ok=True)
    sidecar_dir.mkdir(parents=True, exist_ok=True)

    # Build initial state and sail-normal vector
    init = initial_classical_state(ALTITUDE_KM, LTDN_HOURS, EPOCH_JD)
    rs = sun_direction_eci(EPOCH_JD)
    n_eci = inertial_sail_normal(rs, init.raan_deg, init.inc_deg,
                                 PITCH_DEG, ROLL_DEG)

    case = RunCase(
        name="fig9_gain_anchor",
        altitude_km=ALTITUDE_KM,
        inc_deg=init.inc_deg,
        raan_deg=init.raan_deg,
        sma_km=init.sma_km,
        ecc=init.ecc,
        aop_deg=init.aop_deg,
        ta_deg=init.ta_deg,
        sail_normal_eci=n_eci,
        epoch_iso=EPOCH_ISO,
        duration_sec=args.duration_days * 86400.0,
        step_sec=args.step_sec,
        sail=SailParams(),
        sidecar_dir=sidecar_dir,
    )

    print(f"[run_fig9] anchor: alt={ALTITUDE_KM} km, LTDN={LTDN_HOURS} h, "
          f"pitch={PITCH_DEG} deg, roll={ROLL_DEG} deg")
    print(f"[run_fig9] computed RAAN={init.raan_deg:.3f}, i={init.inc_deg:.3f}")
    print(f"[run_fig9] sail_normal_eci = ({n_eci[0]:+.6f}, {n_eci[1]:+.6f}, {n_eci[2]:+.6f})")
    print(f"[run_fig9] duration={args.duration_days} d, step={args.step_sec} s")

    prefer = "desktop" if args.use_desktop else "engine"
    with stk_session(prefer=prefer) as (app, root):
        sat = build_satellite(root, case, sat_name="Fig9Anchor")
        print("[run_fig9] satellite built; propagating...")
        propagate(sat)

        from core.scenario_builder import _add_seconds_to_iso
        stop_iso = _add_seconds_to_iso(EPOCH_ISO, case.duration_sec)
        rows = extract_classical_elements(sat, EPOCH_ISO, stop_iso, args.step_sec)
        out_csv = write_classical_csv(rows, results_dir / "elements_75d.csv")
        print(f"[run_fig9] wrote {out_csv} ({len(rows)} rows)")

        # Quick acceptance-gate check inline
        try:
            sma = [float(r[1]) for r in rows]
            a0 = sma[0]
            a_max = max(sma)
            a_final = sma[-1]
            print(f"[run_fig9] a0={a0:.3f} km  a_max={a_max:.3f} km  a_final={a_final:.3f} km")
            print(f"[run_fig9] PAPER reference: a0=7078.137  a_max=7098.211  a_final=7064.717")
        except Exception as exc:
            print(f"[run_fig9] gate-check parse error: {exc}")


if __name__ == "__main__":
    main()
