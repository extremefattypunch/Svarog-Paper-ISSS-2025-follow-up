"""
Parallel parameter sweeps.

Each worker process runs its own JVM, so the pool must be created with the
"spawn" start method: forking a process that already holds a live JVM gives a
child with a half-initialised runtime and deadlocks on the first Java call. With
"spawn" the child imports this module fresh, `boot()` runs again, and the worker
gets a clean JVM of its own. Booting costs roughly a second, which is amortised
over the many cases each worker handles.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from dataclasses import asdict

from .propagation import OrekitCase, propagate


def _cell(payload):
    """Run one sweep cell. Must be importable at module level for spawn."""
    index, kwargs, days = payload
    case = OrekitCase(**kwargs)
    try:
        r = propagate(case, days)
    except Exception as exc:                    # reentry or integrator failure
        return index, dict(da_max=float("nan"), da_final=float("nan"),
                           t_at_max_d=float("nan"), error=str(exc)[:200])
    return index, dict(da_max=r.get("da_max", float("nan")),
                       da_final=r.get("da_final", float("nan")),
                       t_at_max_d=r.get("t_at_max_d", float("nan")),
                       n_orbits=int(len(r["node_a"])))


def run_sweep(cases, days, workers=None, chunksize=1, progress_every=25):
    """Run `cases` (list of (index, OrekitCase-kwargs)) in parallel.

    Returns {index: result-dict}. Results come back in completion order; the
    index is carried through so the caller can place them on its own grid.
    """
    if workers is None:
        workers = max(1, (os.cpu_count() or 4) - 2)
    payloads = [(idx, kwargs, days) for idx, kwargs in cases]
    out = {}
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (index, res) in enumerate(
                pool.imap_unordered(_cell, payloads, chunksize=chunksize), start=1):
            out[index] = res
            if progress_every and k % progress_every == 0:
                print(f"    {k}/{len(payloads)} cells", flush=True)
    return out
