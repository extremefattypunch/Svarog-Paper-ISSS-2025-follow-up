"""
Shared configuration for the revision (R1) production runs.

Everything the manuscript quotes is written to results/revision/*.json by the
rev_*.py runners, and every figure is written straight into the paper's
Figures/ directory under an `r_` prefix so the .tex can include it directly.
"""
from __future__ import annotations
import json, os, sys, math
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PAPER_ROOT = os.path.dirname(ROOT)
RESULTS = os.path.join(ROOT, "results", "revision")
FIGURES = os.path.join(PAPER_ROOT, "Figures")
os.makedirs(RESULTS, exist_ok=True)
os.makedirs(FIGURES, exist_ok=True)

# Sun-synchronous inclinations (paper Table 1 / Table 2 conventions).
INC = {700.0: 98.17, 800.0: 98.31}

# Production integrator step [s]. Chosen from rev_convergence.py; the eclipse-
# gated force is discontinuous, so RK4 degrades to ~1st order and the step must
# be small (see Orekit v7). 10 s keeps the 14-day endpoint within ~0.5% of the
# DP853 reference at the 800 km anchor.
DT_PROD = 10.0

# Initial representative geometry (refined from the map by rev_cases.py).
def _gain_anchor():
    """Gain anchor = peak cell of the 800 km map (results/revision/cases.json)
    once rev_cases.py has run; the preliminary geometry before that."""
    p = os.path.join(RESULTS, "cases.json")
    try:
        with open(p) as f:
            g = json.load(f)["cases"]["gain"]
        return float(g["ltan_h"]), float(g["pitch_deg"])
    except Exception:
        return 14.0, 34.0


_LT, _PT = _gain_anchor()
GAIN800 = dict(altitude_km=800.0, inc_deg=INC[800.0], ltan_h=_LT, pitch_deg=_PT)
ANCHOR700_OLD = dict(altitude_km=700.0, inc_deg=INC[700.0], ltan_h=12.266, pitch_deg=24.8)

N_WORKERS = max(1, (os.cpu_count() or 8) - 2)


def save_json(name, obj):
    p = os.path.join(RESULTS, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=_np_default)
    print("wrote", p)
    return p


def load_json(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


def _np_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not serialisable: {type(o)}")


def fig_path(name):
    return os.path.join(FIGURES, name)


def mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9,
        "legend.fontsize": 8, "figure.dpi": 150, "savefig.dpi": 300,
        "axes.grid": False, "font.family": "DejaVu Sans",
    })
    return plt


def orbit_period_s(altitude_km):
    a = (6378.1363 + altitude_km) * 1e3
    return 2 * math.pi * math.sqrt(a**3 / 3.986004418e14)
