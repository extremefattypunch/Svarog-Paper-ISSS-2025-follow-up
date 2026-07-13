"""
Probe #5: how to add/remove force functions on a numerical propagator, the
available force-function templates (find the 1976-Standard atmosphere + SRP
N-Plate), and the atmosphere co-rotation toggle.

Writes docs/astrogator_addfuncs.md.  Run from the "STK simulations" dir.
"""
from __future__ import annotations
import os, sys, traceback

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
OUT_MD = os.path.join(_ROOT, "docs", "astrogator_addfuncs.md")
_lines = []
def emit(s=""):
    print(s); _lines.append(s)
def mem(o):
    try: return [m for m in dir(o) if not m.startswith("_")]
    except Exception as e: return [f"<{e}>"]
def dump(label, o):
    emit(f"\n### {label}\n- type: `{type(o).__name__}`\n- members: " + ", ".join(f"`{m}`" for m in mem(o)))
def tc(label, fn, quiet=False):
    try:
        v = fn(); emit(f"- {label}: OK -> `{type(v).__name__}`"); return v
    except Exception as e:
        if not quiet: emit(f"- {label}: FAIL ({type(e).__name__}: {str(e)[:150]})")
        return None

def main():
    from agi.stk13 import stkobjects as o
    from agi.stk13.stkengine import STKEngine
    emit("# STK Astrogator: add/remove force functions + atmosphere templates — probe #5")
    app = STKEngine.StartApplication(noGraphics=True); root = app.NewObjectRoot()
    try:
        root.NewScenario("Probe5"); scen = root.CurrentScenario
        scen.SetTimePeriod("1 Jan 2026 12:00:00.000", "2 Jan 2026 12:00:00.000")
        sat = scen.Children.New(o.AgESTKObjectType.eSatellite, "Probe5")
        sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorAstrogator)
        cd = root.CurrentScenario.ComponentDirectory
        astro_cat = cd.GetComponents(2)

        # available force-function templates
        pff = tc("astro_cat.GetFolder('Propagator Functions')",
                 lambda: astro_cat.GetFolder("Propagator Functions"))
        if pff is not None:
            dump("Propagator Functions folder", pff)
            # folders under it?
            try:
                emit(f"- FolderCount={pff.FolderCount}; folders={list(pff.AvailableFolders)}")
            except Exception as e:
                emit(f"- folder introspection: {e}")
            # names at top level
            try:
                emit(f"- Count={pff.Count}; names=" + ", ".join(pff.Item(i).Name for i in range(pff.Count)))
            except Exception as e:
                emit(f"- top-level names failed: {e}")
            # drill any subfolders (atmosphere models likely under a subfolder)
            try:
                for fn in list(pff.AvailableFolders):
                    sub = pff.GetFolder(fn)
                    try:
                        nms = [sub.Item(i).Name for i in range(sub.Count)]
                    except Exception:
                        nms = ["<none>"]
                    emit(f"  - subfolder `{fn}`: {nms}")
            except Exception as e:
                emit(f"- subfolder drill failed: {e}")

        # duplicate a propagator + inspect the PropagatorFunctions Add API
        props = astro_cat.GetFolder("Propagators")
        props.DuplicateComponent("Earth Default High Fidelity v13", "SailProp")
        prop = props.Item("SailProp")
        pf = prop.PropagatorFunctions
        dump("PropagatorFunctions collection", pf)

        # the drag function present -> look for co-rotation + atmosphere props
        drag = None
        for i in range(pf.Count):
            it = pf.Item(i)
            if hasattr(it, "DragModelType"):
                drag = it; break
        if drag is not None:
            dump("drag function (default)", drag)
            for a in ("DragModelType", "UseApproximateAltitude", "DragCorrectionType"):
                tc(f"drag.{a}", lambda x=a: getattr(drag, x), quiet=True)
            # search for a rotating-atmosphere / co-rotation toggle anywhere plausible
            emit("- co-rotation candidates on drag: "
                 + ", ".join(m for m in mem(drag) if "otat" in m.lower() or "wind" in m.lower()
                             or "corot" in m.lower()))

        # Try Add() signatures for a 1976 atmosphere drag + SRP N-Plate
        emit("\n## Add() attempts")
        for args in (("AtmosphericDensity",), ("Drag",), ("1976 Standard",),
                     ("Atmospheric Density",)):
            tc(f"pf.Add{args}", lambda a=args: pf.Add(*a), quiet=False)
        # Inspect Add signature via help text
        try:
            emit("- pf.Add doc: " + str(getattr(pf.Add, "__doc__", ""))[:300])
        except Exception:
            pass

        # central-body / scenario level rotating atmosphere?
        emit("\n## Rotating-atmosphere search (central body / scenario)")
        for path, getter in (("scen", lambda: scen),):
            obj = getter()
            emit(f"- {path} rotat/wind members: "
                 + ", ".join(m for m in mem(obj) if "otat" in m.lower() or "wind" in m.lower()))
    finally:
        os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
        with open(OUT_MD, "w", encoding="utf-8") as f: f.write("\n".join(_lines)+"\n")
        emit(f"\n(wrote {OUT_MD})")
        try: app.ShutDown()
        except Exception: pass

if __name__ == "__main__":
    try: main()
    except Exception:
        traceback.print_exc()
        try:
            with open(OUT_MD,"w",encoding="utf-8") as f: f.write("\n".join(_lines)+"\n")
        except Exception: pass
        sys.exit(1)
