#!/usr/bin/env bash
# Run a script inside this study's virtual environment, from the study root.
#   ./run.sh validation/v1_component_gates.py
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
exec "$HERE/.venv/bin/python" "$@"
