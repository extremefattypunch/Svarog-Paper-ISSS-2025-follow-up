"""
Probe #3: reach the Astrogator numerical propagator, enumerate its force models,
and dump the N-Plate SRP + drag + gravity + atmosphere APIs.

Writes docs/astrogator_propfuncs.md.  Run from the "STK simulations" dir.
"""
from __future__ import annotations
import os, sys, traceback

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
OUT_MD = os.path.join(_ROOT, "docs", "astrogator_propfuncs.md")
_lines = []
def emit(s=""):
    print(s); _lines.append(s)
def members(o):
    try: return [m for m in dir(o) if not m.startswith("_")]
    except Exception as e: return [f"<{e}>"]
def dump(label, o):
    emit(f"\n### {label}")
    emit(f"- type: `{type(o).__name__}`")
    emit(f"- members: " + ", ".join(f"`{m}`" for m in members(o)))
def tc(label, fn, quiet=False):
    try:
        v = fn()
        emit(f"- {label}: OK -> `{type(v).__name__}` = `{str(v)[:80]}`"); return v
    except Exception as e:
        if not quiet: emit(f"- {label}: FAIL ({type(e).__name__}: {str(e)[:140]})")
        return None

def main():
    from agi.stk13 import stkobjects as o
    from agi.stk13.stkobjects import astrogator as astro
    from agi.stk13.stkengine import STKEngine
    emit("# STK Astrogator numerical propagator + force models — probe #3")

    # drag-model enum values
    for en in ("AgEVADragModelType", "AgEVADragCorrectionType"):
        cls = getattr(astro, en, None)
        if cls:
            vals = {m:int(getattr(cls,m)) for m in dir(cls) if not m.startswith("_")
                    and isinstance(getattr(cls,m,None),int)}
            emit(f"- enum `{en}`: " + ", ".join(f"{k}={v}" for k,v in sorted(vals.items(), key=lambda x:x[1])))

    app = STKEngine.StartApplication(noGraphics=True)
    root = app.NewObjectRoot()
    try:
        root.NewScenario("Probe3"); scen = root.CurrentScenario
        scen.SetTimePeriod("1 Jan 2026 12:00:00.000", "2 Jan 2026 12:00:00.000")
        sat = scen.Children.New(o.AgESTKObjectType.eSatellite, "Probe3")
        sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorAstrogator)
        driver = sat.Propagator

        # ---- navigate the Astrogator component directory -------------------
        emit("\n## Component directory navigation")
        cd = root.CurrentScenario.ComponentDirectory
        astro_cat = tc("cd.GetComponents(eComponentAstrogator=2)",
                       lambda: cd.GetComponents(2))
        if astro_cat is not None:
            dump("astro component category", astro_cat)
            props = tc("astro_cat.GetComponents('Propagators')",
                       lambda: astro_cat.GetComponents("Propagators"))
            if props is not None:
                dump("Propagators collection", props)
                try:
                    emit(f"- Propagators Count={props.Count}; names="
                         + ", ".join(props.Item(i).Name for i in range(props.Count)))
                except Exception as e:
                    emit(f"- name enum failed: {e}")
                # duplicate the default to an editable owned propagator
                tc("props.DuplicateComponent('Earth Default High Fidelity v13','SailProp')",
                   lambda: props.DuplicateComponent("Earth Default High Fidelity v13", "SailProp"))
                prop = tc("props.Item('SailProp')", lambda: props.Item("SailProp"))
                if prop is None:
                    prop = tc("props.Item(0)", lambda: props.Item(0))
                if prop is not None:
                    dump("numerical propagator (wrapper)", prop)
                    pf = tc("prop.PropagatorFunctions", lambda: prop.PropagatorFunctions)
                    if pf is not None:
                        dump("PropagatorFunctions collection", pf)
                        try:
                            emit(f"- Count={pf.Count}")
                            for i in range(pf.Count):
                                it = pf.Item(i)
                                emit(f"  - [{i}] Name=`{getattr(it,'Name',None)}` "
                                     f"pytype=`{type(it).__name__}`")
                        except Exception as e:
                            emit(f"- enumerate failed: {e}")
                        # dump each known function type by name
                        for nm in ("Gravitational Force", "Earth Gravity", "Drag",
                                   "Atmospheric Density Model", "SRP", "Solar Radiation Pressure",
                                   "Solar Pressure", "Third Body Gravity"):
                            f = tc(f"pf.Item('{nm}')", lambda n=nm: pf.Item(n), quiet=True)
                            if f is not None:
                                dump(f"force function '{nm}'", f)
                        # container add/remove API
                        for m in ("Add","Insert","Remove","Contains","GetItemByName"):
                            emit(f"- PropagatorFunctions has `{m}`: {hasattr(pf,m)}")

                    # integrator
                    integ = tc("prop.NumericalIntegrator", lambda: prop.NumericalIntegrator, quiet=True) \
                            or tc("prop.Integrator", lambda: prop.Integrator, quiet=True)
                    if integ is not None:
                        dump("integrator", integ)

        # ---- Initial State: SpacecraftParameters (area/mass/Cr/Cd) ---------
        emit("\n## Initial State spacecraft parameters")
        mcs = driver.MainSequence
        initseg = mcs.Item("Initial State")
        sp = tc("initseg.SpacecraftParameters", lambda: initseg.SpacecraftParameters)
        if sp is not None:
            dump("SpacecraftParameters", sp)
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
