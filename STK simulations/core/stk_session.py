"""
STK 13 session lifecycle. Wraps `agi.stk13` import + Engine/Desktop attach
patterns so runners don't repeat boilerplate.

Usage:
    from core.stk_session import stk_session

    with stk_session(prefer="engine") as (app, root):
        # build scenario, propagate, extract data
        ...

`prefer="engine"` is the default for sweep runners (headless, no GUI overhead).
`prefer="desktop"` attaches to a running STK Desktop instance for interactive
debugging.
"""

from __future__ import annotations

import contextlib
from typing import Tuple


def _import_stk():
    """Import `agi.stk13` lazily so this module imports without STK installed."""
    from agi.stk13 import stkobjects as o          # noqa: F401
    from agi.stk13.stkdesktop import STKDesktop    # noqa: F401
    try:
        from agi.stk13.stkengine import STKEngine  # may not exist on all licences
    except Exception:
        STKEngine = None
    return o, STKDesktop, STKEngine


@contextlib.contextmanager
def stk_session(prefer: str = "engine", new_scenario: bool = True) -> Tuple:
    """
    Context manager. Yields (app, root). Closes on exit.

    prefer:       "engine" → start STKEngine (headless); "desktop" → attach to
                  STKDesktop, starting one if necessary.
    new_scenario: if True, create a fresh empty scenario "Sim".
                  If False, the runner is expected to attach to an existing one.
    """
    o, STKDesktop, STKEngine = _import_stk()
    app = None
    started_here = False
    try:
        if prefer == "engine" and STKEngine is not None:
            app = STKEngine.StartApplication(noGraphics=True)
            root = app.NewObjectRoot()
            started_here = True
        else:
            try:
                app = STKDesktop.AttachToApplication()
            except Exception:
                app = STKDesktop.StartApplication(visible=True, userControl=True)
                started_here = True
            root = app.Root

        if new_scenario:
            try:
                root.CloseScenario()
            except Exception:
                pass
            root.NewScenario("Sim")

        yield app, root
    finally:
        if started_here and app is not None:
            try:
                app.ShutDown()
            except Exception:
                pass
