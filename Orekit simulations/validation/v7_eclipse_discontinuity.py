"""
V7 -- step-size convergence of an eclipse-gated force.

A binary umbra makes the SRP acceleration *discontinuous* in time: it switches
between its full value and zero at every shadow entry and exit, roughly thirty
times a day in this orbit. A fixed-step Runge-Kutta scheme cannot see that
switch; it evaluates its stages on both sides of the jump and smears the
transition across one step, incurring an O(dt) error at every crossing. The
errors do not cancel, because the crossings are phase-locked to the orbit.

Both the paper's open-source propagator and the STK Astrogator runs used fixed
steps. Orekit lets us test whether that matters, because
`CylindricallyShadowedLightFluxModel` publishes eclipse event detectors: with an
adaptive integrator, Orekit stops exactly at the shadow boundary, restarts, and
integrates each continuous arc cleanly.

Three configurations are swept over step size:

  full model         J2 + drag + eclipse-gated SRP   (discontinuous)
  SRP, no eclipse    J2 + drag + SRP, umbra disabled (continuous)
  drag only          J2 + drag, no SRP               (continuous)

If the diagnosis is right, only the first shows a step-size dependence, and it
converges towards the event-detected adaptive answer as dt shrinks.

Writes results/v7_eclipse_discontinuity.json and
reproduced_figures/orekit_step_convergence.png.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orekit_core.orekit_setup import boot, ROOT  # noqa: E402

boot()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from orekit_core.constants import REPRO_LTDN_H, REPRO_PITCH_DEG  # noqa: E402
from orekit_core.propagation import OrekitCase, propagate  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "reproduced_figures")

ALT = 800.0
DAYS = 14.0
STEPS = [120.0, 60.0, 30.0, 15.0, 7.5, 5.0, 2.5]
#: Adaptive-integrator target position error per step, in metres (Orekit's
#: `tolerances(dP, ...)` convention). 1 m down to 0.1 mm brackets the regime.
POS_TOLS = [1.0, 1e-2, 1e-3, 1e-4]

#: The comparison metric is the 14-day endpoint, not the maximum excursion:
#: for the two continuous-forcing configurations the mean semi-major axis decays
#: monotonically, so `da_max` is identically zero and carries no information.
METRIC = "da_final_km"

CONFIGS = [
    ("full model (eclipse-gated SRP)", dict(use_srp=True, use_drag=True,
                                            disable_eclipse=False)),
    ("SRP with umbra disabled", dict(use_srp=True, use_drag=True,
                                     disable_eclipse=True)),
    ("drag only, no SRP", dict(use_srp=False, use_drag=True)),
]


def run(dt=None, pos_tol=None, **kw):
    kwargs = dict(dt=30.0, **kw)
    if pos_tol is None:
        kwargs.update(integrator="rk4", dt=dt)
    else:
        kwargs.update(integrator="dp853", pos_tol_m=pos_tol, dt=30.0)
    case = OrekitCase.from_ltdn(ALT, REPRO_LTDN_H, REPRO_PITCH_DEG, **kwargs)
    t0 = time.time()
    r = propagate(case, DAYS)
    return dict(da_max_km=r["da_max"], da_final_km=r["da_final"],
                t_at_max_d=r["t_at_max_d"], seconds=time.time() - t0)


#: Coarse steps are excluded from the order fit. For a discontinuous force the
#: error at a coarse step depends on *where in the shadow crossing* the step
#: happens to land, so it is erratic rather than asymptotic: a 120 s step can
#: land closer to the truth than a 60 s one purely by cancellation. The fitted
#: order is therefore meaningful only in the asymptotic range.
ORDER_FIT_MAX_DT = 30.0


def observed_order(dts, errs, max_dt=ORDER_FIT_MAX_DT):
    """Least-squares slope of log|error| against log(dt), over dt <= max_dt.

    A fixed-step RK4 scheme should show slope 4 on smooth forcing. A slope near
    1 is the signature of a discontinuity being stepped over.
    """
    dts = np.asarray(dts, dtype=float)
    errs = np.abs(np.asarray(errs, dtype=float))
    keep = (errs > 1e-6) & (dts <= max_dt)   # drop the reference's own noise floor
    if keep.sum() < 2:
        return float("nan")
    return float(np.polyfit(np.log(dts[keep]), np.log(errs[keep]), 1)[0])


def monotonic_in_dt(dts, errs):
    """True if |error| decreases monotonically as the step is reduced."""
    order = np.argsort(-np.asarray(dts, dtype=float))   # coarse -> fine
    e = np.abs(np.asarray(errs, dtype=float))[order]
    return bool(np.all(np.diff(e) <= 1e-12))


def main():
    out = {"altitude_km": ALT, "days": DAYS, "ltdn_h": REPRO_LTDN_H,
           "pitch_deg": REPRO_PITCH_DEG, "metric": METRIC,
           "fixed_step": {}, "adaptive": {}, "reference": {}, "order": {}}

    print(f"14-day run at {ALT:.0f} km, LTDN {REPRO_LTDN_H} h, pitch {REPRO_PITCH_DEG} deg")
    print(f"metric: {METRIC} (the 14-day endpoint; da_max is identically zero for the "
          "monotonically decaying configurations)\n")
    for label, cfg in CONFIGS:
        print(f"[fixed-step RK4]  {label}")
        rows = []
        for dt in STEPS:
            r = run(dt=dt, **cfg)
            rows.append(dict(dt_s=dt, **r))
            print(f"   dt = {dt:6.1f} s   Delta a(14 d) = {r['da_final_km']:+9.4f} km   "
                  f"(Delta a_max {r['da_max_km']:+7.4f} km, {r['seconds']:.1f} s)")
        out["fixed_step"][label] = rows

    # ---- converged reference for every configuration -------------------------
    print("\n[adaptive DP853 with eclipse event detection]")
    for label, cfg in CONFIGS:
        rows = []
        for tol in POS_TOLS:
            r = run(pos_tol=tol, **cfg)
            rows.append(dict(pos_tol_m=tol, **r))
            print(f"   {label:32s} dP = {tol:7.0e} m   "
                  f"Delta a(14 d) = {r['da_final_km']:+9.4f} km   ({r['seconds']:.1f} s)")
        out["adaptive"][label] = rows
        out["reference"][label] = float(rows[-1][METRIC])

    ref_full = out["reference"][CONFIGS[0][0]]
    out["reference_da_final_km"] = ref_full
    out["reference_da_max_km"] = float(out["adaptive"][CONFIGS[0][0]][-1]["da_max_km"])

    # ---- observed convergence order ------------------------------------------
    print("\nobserved convergence order (slope of log|error| vs log dt):")
    for label, _ in CONFIGS:
        rows_ = out["fixed_step"][label]
        ref = out["reference"][label]
        dts = [r["dt_s"] for r in rows_]
        errs = [r[METRIC] - ref for r in rows_]
        p = observed_order(dts, errs)
        mono = monotonic_in_dt(dts, errs)
        out["order"][label] = p
        out.setdefault("monotonic", {})[label] = mono
        print(f"   {label:34s} p = {p:5.2f}   "
              f"error monotonic in dt: {'yes' if mono else 'NO'}")
    print(f"   (fitted over dt <= {ORDER_FIT_MAX_DT:.0f} s. Classical RK4 is nominally")
    print("    p = 4; a discontinuity crossed by a fixed step degrades this towards")
    print("    p = 1 and makes the coarse-step error erratic rather than asymptotic.)")

    print("\nerror against the converged reference:")
    for label, _ in CONFIGS:
        ref = out["reference"][label]
        print(f"  {label}  (reference {ref:+.4f} km)")
        for row in out["fixed_step"][label]:
            err = row[METRIC] - ref
            rel = abs(err) / max(abs(ref), 1e-12) * 100.0
            print(f"     dt = {row['dt_s']:6.1f} s   error = {err:+8.4f} km ({rel:6.2f} %)")

    # ---- figure -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    styles = {"full model (eclipse-gated SRP)": "tab:purple",
              "SRP with umbra disabled": "tab:orange",
              "drag only, no SRP": "tab:gray"}
    for label, _ in CONFIGS:
        rows_ = out["fixed_step"][label]
        c = styles.get(label, "k")
        axes[0].plot([r["dt_s"] for r in rows_], [r[METRIC] for r in rows_],
                     "o-", lw=1.5, ms=4, color=c, label=label)
        axes[0].axhline(out["reference"][label], color=c, ls="--", lw=0.9)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("fixed integration step [s]")
    axes[0].set_ylabel(r"14-day $\Delta a$ (mean) [km]")
    axes[0].set_title("Step-size dependence at 800 km "
                      "(dashed: event-detected reference)", fontsize=8.5)
    axes[0].legend(fontsize=7.5)
    axes[0].grid(alpha=0.3, which="both")

    for label, _ in CONFIGS:
        rows_ = out["fixed_step"][label]
        ref = out["reference"][label]
        dts = np.array([r["dt_s"] for r in rows_])
        errs = np.abs(np.array([r[METRIC] for r in rows_]) - ref)
        axes[1].loglog(dts, np.maximum(errs, 1e-6), "o-", lw=1.5, ms=4,
                       color=styles.get(label, "k"),
                       label=f"{label}  ($p$ = {out['order'][label]:.1f})")
    d0 = np.array(STEPS, dtype=float)
    axes[1].loglog(d0, 1.3 * (d0 / 60.0), "k:", lw=1.0, label=r"$\mathcal{O}(\Delta t)$")
    axes[1].loglog(d0, 1.3 * (d0 / 60.0) ** 4, "k-.", lw=1.0,
                   label=r"$\mathcal{O}(\Delta t^{4})$")
    axes[1].set_xlabel("fixed integration step [s]")
    axes[1].set_ylabel(r"$|\Delta a - \Delta a_{\rm reference}|$ [km]")
    axes[1].set_title("Convergence order", fontsize=9)
    axes[1].legend(fontsize=7)
    axes[1].grid(alpha=0.3, which="both")
    axes[1].set_ylim(1e-4, 1e2)
    fig.suptitle("A binary umbra makes the SRP force discontinuous: fixed steps pay for it",
                 fontsize=10)
    fig.tight_layout()
    os.makedirs(FIGS, exist_ok=True)
    p = os.path.join(FIGS, "orekit_step_convergence.png")
    fig.savefig(p, dpi=140)
    plt.close(fig)
    print(f"\nwrote {p}")

    os.makedirs(RESULTS, exist_ok=True)
    q = os.path.join(RESULTS, "v7_eclipse_discontinuity.json")
    with open(q, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
