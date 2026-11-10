#!/usr/bin/env bash
# Fetch the Orekit data archive (leap seconds, Earth orientation parameters,
# DE-440 planetary ephemerides, CSSI space weather).
#
# Orekit refuses to initialise its time scales without this, and the
# NRLMSISE-00 comparison in validation/v6_drag_decomposition.py needs the
# space-weather file it contains.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="https://gitlab.orekit.org/orekit/orekit-data/-/archive/main/orekit-data-main.zip"
DEST="$HERE/data/orekit-data.zip"

mkdir -p "$HERE/data"
echo "fetching $URL"
curl -sSL -o "$DEST" "$URL"
ls -lh "$DEST"
