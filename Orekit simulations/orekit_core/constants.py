"""
Physical constants and locked case parameters.

Every value here is the *paper's* value, not Orekit's default. That is
deliberate: the point of the exercise is to compare how two tools *apply* a
force model, so the constants that feed the model must be identical. Where
Orekit would otherwise substitute its own (WGS-84 radius, EIGEN-5C mu), we pass
these explicitly.

Sources: Sections/dynmodel.tex, Sections/breakdown.tex, and
"STK simulations"/README.md ("Sail and orbit parameters (locked)").
"""

from __future__ import annotations

# --- Earth (identical to "STK simulations"/core/dynamics.py) -----------------
MU_EARTH = 3.986004418e14        # m^3 s^-2
R_EARTH = 6_378_136.3            # m  (paper's equatorial radius)
J2 = 1.082_626_173e-3            # unnormalised, positive convention
R_EARTH_KM = R_EARTH / 1000.0

# --- Solar radiation --------------------------------------------------------
P_1AU = 4.5605e-6                # N m^-2 at 1 AU
AU = 1.495978707e11              # m
# Orekit's flux models are parameterised by a reference flux constant kRef such
# that the local pressure is kRef / d^2; for the paper's convention that is
# P_1AU * AU^2.
K_REF = P_1AU * AU * AU

# --- Sail (locked) ----------------------------------------------------------
SAIL_AREA = 100.0                # m^2
SAIL_MASS = 10.0                 # kg
CR = 1.7                         # paper reflectivity coefficient
CD = 2.2                         # drag coefficient
# N-plate optical calibration reproducing C_r,eff = 1 + rho_s = 1.7
ABSORPTION = 0.3
SPECULAR = 0.7
DIFFUSE = 0.0

# --- Orbit (locked) ---------------------------------------------------------
ECC = 1e-4
INC_700 = 98.17                  # deg
INC_800 = 98.31                  # deg
EPOCH = (2026, 1, 1, 12, 0, 0.0)  # 1 Jan 2026 12:00:00 UT

# Gain anchor from the reduced model (paper Fig. 2)
ANCHOR_LTDN_H = 12.266
ANCHOR_PITCH_DEG = 24.8
ANCHOR_RAAN_DEG = 285.5

# Reproduced gain case found by the open-source propagator at 800 km
def _revision_anchor():
    """Gain anchor of the revised manuscript (STK simulations/results/revision/cases.json)
    when available; otherwise the preliminary 800 km gain geometry."""
    import json as _json, os as _os
    p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                      "STK simulations", "results", "revision", "cases.json")
    try:
        g = _json.load(open(p))["cases"]["gain"]
        return float(g["ltan_h"]), float(g["pitch_deg"])
    except Exception:
        return 14.0, 34.0


REPRO_LTDN_H, REPRO_PITCH_DEG = _revision_anchor()   # LTAN of the gain anchor (name kept for compatibility)


def inclination_for(altitude_km: float) -> float:
    """Paper's near-Sun-synchronous inclination for the two study altitudes."""
    return INC_800 if altitude_km >= 750.0 else INC_700
