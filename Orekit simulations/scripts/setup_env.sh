#!/usr/bin/env bash
# Create the study's virtual environment and install Orekit.
#
# Notes for reproducing this on another machine:
#   * The classic `orekit` Python wrapper is built with JCC and published only
#     through conda-forge, pinned to particular CPython ABIs. This study instead
#     uses `orekit_jpype`, which drives the stock Orekit jars through JPype and
#     installs from PyPI on any CPython >= 3.8.
#   * A JRE/JDK must be on PATH. Any Java 17+ runtime works; developed against
#     OpenJDK 21.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

if ! command -v java >/dev/null 2>&1; then
  echo "error: no 'java' on PATH. Install a JDK/JRE (Arch: pacman -S jdk-openjdk)." >&2
  exit 1
fi
echo "java: $(java -version 2>&1 | head -1)"

python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip wheel setuptools
./.venv/bin/python -m pip install -r requirements.txt

./.venv/bin/python - <<'PY'
import jpype, orekit_jpype
print("jpype", jpype.__version__)
print("orekit_jpype", orekit_jpype.__file__)
PY
echo
echo "Done. Next: ./scripts/fetch_data.sh"
