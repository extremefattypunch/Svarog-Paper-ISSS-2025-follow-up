"""
JVM bootstrap and Orekit data loading.

`orekit_jpype` talks to the stock Orekit Java jars through JPype/JNI, so the JVM
must be started exactly once per process and the Orekit data archive (leap
seconds, EOP, DE-440 planetary ephemerides) registered before any Orekit call.
Both are idempotent here so that every script can simply call `boot()` at import
time regardless of who else already did.

The data archive is `data/orekit-data.zip`, fetched by `scripts/fetch_data.sh`
from https://gitlab.orekit.org/orekit/orekit-data (branch `main`).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DATA_ZIP = os.path.join(ROOT, "data", "orekit-data.zip")

# The paper's reference implementation lives in the sibling STK study; we import
# it verbatim rather than re-deriving it, so the cross-validation compares the
# two tools and not two transcriptions of the same equations.
#
# That study exposes packages named `core` and `plugins`. Ours is deliberately
# called `orekit_core` rather than `core` so both trees can sit on sys.path at
# once without shadowing each other -- `core.*` always means the paper's
# reference propagator, `orekit_core.*` always means this Orekit port.
PAPER_REF_DIR = os.path.join(os.path.dirname(ROOT), "STK simulations")

_BOOTED = False


def boot(verbose: bool = False) -> None:
    """Start the JVM and load the Orekit data archive (idempotent)."""
    global _BOOTED
    if _BOOTED:
        return

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    if PAPER_REF_DIR not in sys.path:
        sys.path.append(PAPER_REF_DIR)

    import orekit_jpype

    orekit_jpype.initVM()

    from orekit_jpype.pyhelpers import setup_orekit_data

    if not os.path.exists(DATA_ZIP):
        raise FileNotFoundError(
            f"Orekit data archive not found at {DATA_ZIP}. "
            "Run scripts/fetch_data.sh first."
        )
    setup_orekit_data(filenames=DATA_ZIP, from_pip_library=False)
    _BOOTED = True

    if verbose:
        from org.orekit.time import TimeScalesFactory  # noqa: E402

        print(f"[orekit] JVM up, data loaded from {DATA_ZIP}; UTC = {TimeScalesFactory.getUTC()}")


def orekit_version() -> str:
    boot()
    import glob

    jars = glob.glob(
        os.path.join(ROOT, ".venv", "lib", "python*", "site-packages",
                     "orekit_jpype", "jars", "orekit-*.jar")
    )
    if jars:
        return os.path.basename(jars[0])
    return "orekit (version unknown)"
