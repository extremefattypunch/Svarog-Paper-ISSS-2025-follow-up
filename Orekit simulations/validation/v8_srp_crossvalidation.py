"""
V8 -- propagated cross-validation with SRP enabled.

V2 deliberately compares the two propagators in an SRP-free configuration,
because they use different Sun ephemerides: Orekit reads DE-440, the reduced
model uses an analytic series at a fixed one astronomical unit. Any SRP-bearing
comparison would otherwise mix an ephemeris difference into a propagator
comparison.

`orekit_core.sun.AnalyticSun` removes that obstacle by exposing the paper's own
Sun routine through Orekit's provider interface. Three runs of the full model
(J2 + N-plate drag + eclipse-gated N-plate SRP) then separate the two effects:

  A  open-source propagator                       (paper's Sun, paper's code)
  B  Orekit with the paper's analytic Sun         (isolates the propagators)
  C  Orekit with DE-440                           (B - C isolates the ephemeris)

A vs B is the propagated SRP cross-validation proper. B vs C is the price of the
reduced model's fixed 1 AU Sun distance, which matters here because the epoch
falls within days of perihelion.

Both runs use fixed-step RK4 at 30 s, matching the open-source propagator
exactly; the point is to compare tools, not integrators.

Writes results/v8_srp_crossvalidation.json.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orekit_core.orekit_setup import boot, ROOT  # noqa: E402

boot()

from orekit_core.attitude import raan_for_ltdn  # noqa: E402
from orekit_core.constants import (  # noqa: E402
    ANCHOR_RAAN_DEG, ANCHOR_PITCH_DEG, REPRO_LTDN_H, REPRO_PITCH_DEG,
    INC_700, INC_800,
)
from orekit_core.propagation import OrekitCase, propagate  # noqa: E402

from core.offline_propagator import SailCase, propagate as propagate_paper  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
DAYS = 14.0
DT = 30.0

CASES = [
    dict(name="reproduced gain case, 800 km",
         altitude_km=800.0, inc_deg=INC_800,
         raan_deg=raan_for_ltdn(REPRO_LTDN_H), pitch_deg=REPRO_PITCH_DEG),
    dict(name="reduced-model anchor, 700 km",
         altitude_km=700.0, inc_deg=INC_700,
         raan_deg=ANCHOR_RAAN_DEG, pitch_deg=ANCHOR_PITCH_DEG),
]


def run_paper(cfg):
    c = SailCase(altitude_km=cfg["altitude_km"], inc_deg=cfg["inc_deg"],
                 raan_deg=cfg["raan_deg"], pitch_deg=cfg["pitch_deg"],
                 ecc=1e-4, use_srp=True, drag_mode="nplate", dt=DT)
    return propagate_paper(c, DAYS)


def run_orekit(cfg, sun_model):
    case = OrekitCase(altitude_km=cfg["altitude_km"], inc_deg=cfg["inc_deg"],
                      raan_deg=cfg["raan_deg"], pitch_deg=cfg["pitch_deg"],
                      use_srp=True, use_drag=True, drag_mode="nplate",
                      integrator="rk4", dt=DT, sun_model=sun_model)
    return propagate(case, DAYS)


def series_diff(ref, other):
    """max |difference| of Delta a, interpolating `other` onto `ref` node times."""
    da_ref = ref["node_a"] - ref["node_a"][0]
    da_oth = other["node_a"] - other["node_a"][0]
    d = np.interp(ref["node_t"], other["node_t"], da_oth)
    return float(np.max(np.abs(da_ref - d)))


def main():
    rows = []
    for cfg in CASES:
        a = run_paper(cfg)
        b = run_orekit(cfg, "paper")
        c = run_orekit(cfg, "de440")

        row = dict(
            case=cfg["name"], altitude_km=cfg["altitude_km"],
            pitch_deg=cfg["pitch_deg"], days=DAYS, dt_s=DT,
            paper_da_final_km=float(a["da_final"]),
            paper_da_max_km=float(a["da_max"]),
            orekit_paper_sun_da_final_km=float(b["da_final"]),
            orekit_paper_sun_da_max_km=float(b["da_max"]),
            orekit_de440_da_final_km=float(c["da_final"]),
            orekit_de440_da_max_km=float(c["da_max"]),
            max_abs_diff_propagators_km=series_diff(a, b),
            max_abs_diff_ephemeris_km=series_diff(b, c),
        )
        rows.append(row)

        print(f"\n[{cfg['name']}]  full model, SRP on, {DAYS:.0f} days, dt = {DT:.0f} s")
        print(f"  A  open-source propagator            "
              f"Delta a_max = {a['da_max']:+8.4f} km   "
              f"Delta a(14 d) = {a['da_final']:+8.4f} km")
        print(f"  B  Orekit, paper's analytic Sun      "
              f"Delta a_max = {b['da_max']:+8.4f} km   "
              f"Delta a(14 d) = {b['da_final']:+8.4f} km")
        print(f"  C  Orekit, DE-440                    "
              f"Delta a_max = {c['da_max']:+8.4f} km   "
              f"Delta a(14 d) = {c['da_final']:+8.4f} km")
        print(f"  propagator difference (A vs B), max |Delta a| : "
              f"{row['max_abs_diff_propagators_km']:.3e} km")
        print(f"  ephemeris difference  (B vs C), max |Delta a| : "
              f"{row['max_abs_diff_ephemeris_km']:.4f} km"
              f"   ({row['max_abs_diff_ephemeris_km']/max(abs(b['da_max']),1e-9)*100:.1f} %"
              " of the gain)")

    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, "v8_srp_crossvalidation.json")
    with open(p, "w") as f:
        json.dump(dict(days=DAYS, dt_s=DT, rows=rows), f, indent=2)
    print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
