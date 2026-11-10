"""
Probe #4: navigate to the numerical propagator via GetFolder, enumerate its
force models, and fully dump the N-Plate SRP + N-Plate drag + gravity + atmosphere
configuration APIs (plate collections: area, normal, reflectivity).

Writes docs/astrogator_nplate.md.  Run from the "STK simulations" dir.
"""
from __future__ import annotations
import os, sys, traceback

_HERE = os.path.dirname(os.path.abspath(__file__)); _ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)
OUT_MD = os.path.join(_ROOT, "docs", "astrogator_nplate.md")
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
        v = fn(); emit(f"- {label}: OK -> `{type(v).__name__}`"); return v
    except Exception as e:
        if not quiet: emit(f"- {label}: FAIL ({type(e).__name__}: {str(e)[:150]})")
        return None

def main():
    from agi.stk13 import stkobjects as o
    from agi.stk13.stkobjects import astrogator as astro
    from agi.stk13.stkengine import STKEngine
    emit("# STK Astrogator N-Plate SRP/drag configuration — probe #4")

    # SRP model-type enum (Astrogator)
    for en in ("AgEVASRPModelType", "AgEVASRPModel"):
        cls = getattr(astro, en, None)
        if cls:
            vals = {m:int(getattr(cls,m)) for m in dir(cls) if not m.startswith("_")
                    and isinstance(getattr(cls,m,None),int)}
            emit(f"- enum `{en}`: " + ", ".join(f"{k}={v}" for k,v in sorted(vals.items(), key=lambda x:x[1])))

    app = STKEngine.StartApplication(noGraphics=True)
    root = app.NewObjectRoot()
    try:
        root.NewScenario("Probe4"); scen = root.CurrentScenario
        scen.SetTimePeriod("1 Jan 2026 12:00:00.000", "2 Jan 2026 12:00:00.000")
        sat = scen.Children.New(o.AgESTKObjectType.eSatellite, "Probe4")
        sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorAstrogator)

        cd = root.CurrentScenario.ComponentDirectory
        astro_cat = cd.GetComponents(2)
        emit(f"\n## Folders under Astrogator category")
        try:
            emit(f"- FolderCount={astro_cat.FolderCount}; folders="
                 + ", ".join(astro_cat.FolderName(i) for i in range(astro_cat.FolderCount)))
        except Exception as e:
            emit(f"- folder list failed: {e}; AvailableFolders={tc('AvailableFolders', lambda: astro_cat.AvailableFolders, quiet=True)}")

        props = tc("astro_cat.GetFolder('Propagators')", lambda: astro_cat.GetFolder("Propagators"))
        if props is None:
            emit("!! cannot get Propagators folder; aborting"); return
        dump("Propagators folder", props)
        try:
            emit(f"- names=" + ", ".join(props.Item(i).Name for i in range(props.Count)))
        except Exception as e:
            emit(f"- name enum failed: {e}")

        tc("DuplicateComponent(default,'SailProp')",
           lambda: props.DuplicateComponent("Earth Default High Fidelity v13", "SailProp"))
        prop = tc("props.GetItemByName('SailProp')", lambda: props.GetItemByName("SailProp"),
                  quiet=True) or tc("props.Item('SailProp')", lambda: props.Item("SailProp"))
        if prop is None:
            emit("!! cannot get SailProp; aborting"); return
        dump("numerical propagator SailProp", prop)

        pf = tc("prop.PropagatorFunctions", lambda: prop.PropagatorFunctions)
        if pf is not None:
            emit(f"\n## Force models in default propagator")
            names = []
            try:
                for i in range(pf.Count):
                    it = pf.Item(i); nm = getattr(it, "Name", None)
                    names.append(nm)
                    emit(f"  - [{i}] Name=`{nm}` pytype=`{type(it).__name__}`")
            except Exception as e:
                emit(f"- enumerate failed: {e}")

            # dump each force function fully
            for i in range(pf.Count):
                it = pf.Item(i)
                dump(f"force[{i}] {getattr(it,'Name','?')}", it)
                tn = type(it).__name__
                # SRP function -> set N-plate, dump plate API
                if "Radiation" in tn or "SRP" in tn or "Radiation" in str(getattr(it,"Name","")):
                    for setter in ("SolarRadiationPressureModel", "SRPModel", "Model"):
                        m = tc(f"  srp.{setter}", lambda s=setter, x=it: getattr(x, s), quiet=True)
                        if m is not None: dump(f"  srp.{setter}", m)
                    # try to set N-plate model type
                    for meth, arg in (("SetSRPModelType", 3), ("SetModelType", 3),
                                      ("SetSolarRadiationPressureModel", 3)):
                        tc(f"  srp.{meth}(NPlate=3?)", lambda mm=meth, x=it, a=arg: getattr(x, mm)(a), quiet=True)
                # Drag function -> inspect model type API + N-plate
                if "Drag" in tn or "Drag" in str(getattr(it,"Name","")):
                    for acc in ("DragModel","Model","AtmosphericDensityModel","AtmosphereModel"):
                        m = tc(f"  drag.{acc}", lambda a=acc, x=it: getattr(x, a), quiet=True)
                        if m is not None: dump(f"  drag.{acc}", m)

        # If a live SRP N-plate object type exists, instantiate-inspect via the class
        emit("\n## Class-level member dump: AgVASRPNPlate / AgVANPlateStochasticParam")
        for cn in ("AgVASRPNPlate", "IAgVASRPNPlate", "AgVANPlateStochasticParam"):
            cls = getattr(astro, cn, None)
            if cls is not None:
                emit(f"- `{cn}` members: " + ", ".join(m for m in dir(cls) if not m.startswith("_")))
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
