"""
Pull Classical-Element time series out of a propagated STK satellite.

The DataProvider patterns here are the same as in
C:\\Users\\Ian Poon\\Documents\\STK_ODTK 13\\LEOsolarsailSIMS\\export_stk_reports.py
adapted to this project's layout and column conventions.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Tuple


CLASSICAL_COLS = (
    "Time", "Semi-major Axis", "Eccentricity", "Inclination",
    "RAAN", "Arg of Perigee", "True Anomaly",
)


def extract_classical_elements(sat, start_iso: str, stop_iso: str,
                               step_sec: float = 60.0) -> List[Tuple]:
    """
    Returns list of rows (t_iso, sma_km, ecc, inc_deg, raan_deg, aop_deg, ta_deg).
    Uses the ICRF group of the Classical Elements DataProvider.
    """
    grp = sat.DataProviders.Item("Classical Elements").Group.Item("ICRF")
    ds = grp.ExecElements(start_iso, stop_iso, step_sec, list(CLASSICAL_COLS))
    cols = [list(ds.DataSets.Item(i).GetValues()) for i in range(ds.DataSets.Count)]
    n = len(cols[0]) if cols else 0
    return [tuple(c[i] for c in cols) for i in range(n)]


def write_classical_csv(rows: Iterable[Tuple], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_iso", "sma_km", "ecc", "inc_deg", "raan_deg", "aop_deg", "ta_deg"])
        for r in rows:
            w.writerow(r)
    return out_path


def extract_eclipse_intervals(sat, start_iso: str, stop_iso: str):
    """Returns list of (start_iso, stop_iso) pairs for umbra intervals."""
    try:
        grp = sat.DataProviders.Item("Eclipse Times")
        ds = grp.Exec(start_iso, stop_iso)
        out = []
        for i in range(ds.DataSets.Count):
            d = ds.DataSets.Item(i)
            vals = list(d.GetValues())
            out.append(vals)
        return out
    except Exception:
        return []
