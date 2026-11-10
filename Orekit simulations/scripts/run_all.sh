#!/usr/bin/env bash
# Reproduce every result in this study, in dependency order.
# Roughly an hour on 16 cores; the two gain-lobe sweeps dominate.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

run() { echo; echo "==================== $* ===================="; ./run.sh "$@"; }

# Validation battery
run validation/v1_component_gates.py
run validation/v2_crossvalidation.py
run validation/v3_instantaneous_drag.py
run validation/v4_srp_attitude_coupling.py
run validation/v5_calibration_gate.py
run validation/v6_drag_decomposition.py
run validation/v7_eclipse_discontinuity.py

# Gain-regime reproduction
run runners/run_srp_power.py
run runners/run_eclipse_causality.py 30
run runners/run_long_horizon.py 75
run runners/run_gain_lobe.py 800 25 25 14
run runners/run_gain_lobe.py 700 25 25 14

echo
echo "All done. Figures in reproduced_figures/, numbers in results/."
