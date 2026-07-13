"""
Post-processing diagnostics computed from extracted CSVs.

- delta_a_max(T): paper's primary metric for Fig. 2 sweep
- per-orbit SRP / drag work integrals (from plugin sidecar logs)
- apogee/perigee altitude time series

All functions take CSV paths or numpy-style arrays. No STK dependency.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import List, Tuple

R_EARTH_KM = 6378.1363


def _parse_iso_seconds(t_iso: str, t0_iso: str) -> float:
    """Compute seconds between t_iso and t0_iso. Both must be ISO-like."""
    # STK ISO usually like "1 Jan 2026 12:00:00.000". We avoid pulling in
    # a heavy dependency by handling the common formats here.
    from datetime import datetime
    fmts = ("%d %b %Y %H:%M:%S.%f", "%d %b %Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S")
    def _p(s):
        for fmt in fmts:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unrecognised time format: {s!r}")
    return (_p(t_iso) - _p(t0_iso)).total_seconds()


def read_classical_csv(path: Path) -> List[dict]:
    rows = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({
                "t_iso": row["t_iso"],
                "sma_km": float(row["sma_km"]),
                "ecc": float(row["ecc"]),
                "inc_deg": float(row["inc_deg"]),
                "raan_deg": float(row["raan_deg"]),
                "aop_deg": float(row["aop_deg"]),
                "ta_deg": float(row["ta_deg"]),
            })
    return rows


def with_apogee_perigee_time(rows: List[dict], t0_iso: str) -> List[dict]:
    out = []
    for r in rows:
        sma = r["sma_km"]; e = r["ecc"]
        out.append({
            **r,
            "t_sec": _parse_iso_seconds(r["t_iso"], t0_iso),
            "ha_km": sma * (1 + e) - R_EARTH_KM,
            "hp_km": sma * (1 - e) - R_EARTH_KM,
        })
    return out


def delta_a_max(rows: List[dict], a0_km: float, t_max_sec: float = None) -> Tuple[float, float]:
    """
    Returns (delta_a_max_km, t_at_max_sec). t_max_sec optionally bounds the
    search window (e.g. 14 days for paramspace sweep).
    """
    best = -float("inf")
    t_best = 0.0
    for r in rows:
        if t_max_sec is not None and r.get("t_sec", float("inf")) > t_max_sec:
            break
        d = r["sma_km"] - a0_km
        if d > best:
            best = d
            t_best = r.get("t_sec", 0.0)
    return best, t_best


def cumulative_work_from_sidecar(sidecar_path: Path,
                                 force_prefix: str = "a_srp") -> List[Tuple[float, float]]:
    """
    Reads a plugin sidecar log and returns cumulative specific work [J/kg]
    sampled at each plugin call. force_prefix is the column-name prefix:
    "a_srp" for the SRP sidecar, "a_drag" for the drag sidecar.
    """
    out = []
    cum = 0.0
    last_t = None
    with open(sidecar_path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            t = float(row["t_sec"])
            ax = float(row[f"{force_prefix}_x"])
            ay = float(row[f"{force_prefix}_y"])
            az = float(row[f"{force_prefix}_z"])
            vx = float(row.get("v_x", 0.0))
            vy = float(row.get("v_y", 0.0))
            vz = float(row.get("v_z", 0.0))
            P = ax * vx + ay * vy + az * vz
            if last_t is not None:
                cum += P * (t - last_t)
            out.append((t, cum))
            last_t = t
    return out
