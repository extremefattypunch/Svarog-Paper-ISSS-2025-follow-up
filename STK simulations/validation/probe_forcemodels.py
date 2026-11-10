"""
Probe #2: STK Astrogator numerical-propagator + force-model discovery.

Follows up probe_astrogator.py. Finds:
  - the AgEComponentType-style enum + the ComponentDirectory GetComponents ints
  - the Propagators collection and the default numerical propagator's members
  - how force models (gravity / drag / SRP) attach to a numerical propagator
  - available SRP models (look for N-Plate) and atmosphere models (USStandard 1976)
  - the Initial-State element-type enum + Keplerian element members
  - a smoke RunMCS() with the stock propagator, then extract classical elements

Writes docs/astrogator_forcemodels.md.
Run:  python validation/probe_forcemodels.py   (from the "STK simulations" dir)
"""

from __future__ import annotations

import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

OUT_MD = os.path.join(_ROOT, "docs", "astrogator_forcemodels.md")
_lines = []


def emit(s=""):
    print(s)
    _lines.append(s)


def members(obj):
    try:
        return [m for m in dir(obj) if not m.startswith("_")]
    except Exception as e:
        return [f"<dir failed: {e}>"]


def dump(label, obj):
    emit(f"\n### {label}")
    emit(f"- type: `{type(obj).__name__}`")
    ms = members(obj)
    emit(f"- members ({len(ms)}): " + ", ".join(f"`{m}`" for m in ms))


def enum_values(o, name):
    """Dump an enum class's member names+values if present on stkobjects."""
    cls = getattr(o, name, None)
    if cls is None:
        emit(f"- enum `{name}`: NOT FOUND")
        return None
    vals = {}
    for m in dir(cls):
        if m.startswith("_"):
            continue
        try:
            vals[m] = int(getattr(cls, m))
        except Exception:
            vals[m] = getattr(cls, m)
    emit(f"- enum `{name}` ({len(vals)}): " + ", ".join(f"{k}={v}" for k, v in vals.items()))
    return vals


def try_call(label, fn, quiet=False):
    try:
        v = fn()
        if not quiet:
            emit(f"- {label}: OK -> `{type(v).__name__}`")
        return v
    except Exception as e:
        if not quiet:
            emit(f"- {label}: FAIL ({type(e).__name__}: {str(e)[:120]})")
        return None


def main():
    from agi.stk13 import stkobjects as o
    from agi.stk13.stkengine import STKEngine

    emit("# STK Astrogator numerical propagator + force models — probe #2")

    # ---- enums we will need -----------------------------------------------
    emit("\n## Relevant enums (stkobjects)")
    for en in ("AgEComponentType", "AgEVAElementType", "AgESrpModel", "AgESRPModel",
               "AgEVASRPModel", "AgEVADragModel", "AgEVAAtmosphericModel",
               "AgEVAShadowModel", "AgEVAStoppingCondition"):
        enum_values(o, en)

    app = STKEngine.StartApplication(noGraphics=True)
    root = app.NewObjectRoot()
    try:
        root.NewScenario("Probe2")
        scen = root.CurrentScenario
        scen.SetTimePeriod("1 Jan 2026 12:00:00.000", "2 Jan 2026 12:00:00.000")
        sat = scen.Children.New(o.AgESTKObjectType.eSatellite, "Probe2")
        sat.SetPropagatorType(o.AgEVePropagatorType.ePropagatorAstrogator)
        driver = sat.Propagator

        # ---- component directory: brute-force GetComponents(int) -----------
        emit("\n## ComponentDirectory.GetComponents(int) scan")
        cd = root.CurrentScenario.ComponentDirectory
        prop_coll = None
        for i in range(0, 30):
            coll = try_call(f"GetComponents({i})", lambda i=i: cd.GetComponents(i), quiet=True)
            if coll is None:
                continue
            # Try to enumerate names
            names = []
            try:
                for k in range(coll.Count):
                    names.append(coll.Item(k).Name)
            except Exception:
                # maybe collection items aren't Name-bearing; dump members once
                names = ["<no Name enumeration>"]
            emit(f"- GetComponents({i}) -> `{type(coll).__name__}` Count="
                 f"{getattr(coll,'Count','?')} names={names[:12]}")
            # Heuristic: the propagators collection contains our default prop name
            if any("Fidelity" in str(n) or "Point Mass" in str(n) for n in names):
                prop_coll = coll
                emit(f"  --> looks like the Propagators collection (index {i}).")

        if prop_coll is not None:
            dump("Propagators collection", prop_coll)
            for meth in ("DuplicateComponent", "Item"):
                emit(f"- has `{meth}`: {hasattr(prop_coll, meth)}")
            # Duplicate the default to an owned propagator we can safely edit
            newname = "SailProp"
            try_call("DuplicateComponent('Earth Default High Fidelity v13','SailProp')",
                     lambda: prop_coll.DuplicateComponent("Earth Default High Fidelity v13", newname))
            prop = try_call("prop_coll.Item('SailProp')", lambda: prop_coll.Item(newname))
            if prop is None:
                prop = try_call("prop_coll.Item('Earth Default High Fidelity v13')",
                                lambda: prop_coll.Item("Earth Default High Fidelity v13"))
            if prop is not None:
                dump("numerical propagator", prop)
                # Force-model container: try common accessors
                for acc in ("PropagatorFunctions", "ForceModel", "Force",
                            "NumericalIntegrator", "Integrator", "PropagatorType"):
                    v = try_call(f"prop.{acc}", lambda a=acc: getattr(prop, a))
                    if v is not None and acc in ("PropagatorFunctions", "ForceModel"):
                        dump(f"prop.{acc}", v)
                        # enumerate the force-model collection
                        try:
                            emit(f"  Count={v.Count}")
                            for k in range(v.Count):
                                it = v.Item(k)
                                emit(f"   - [{k}] Name=`{getattr(it,'Name',None)}` "
                                     f"pytype=`{type(it).__name__}` "
                                     f"Type=`{getattr(it,'Type',None)}`")
                                dump(f"forcefunc[{k}] {getattr(it,'Name','?')}", it)
                        except Exception as e:
                            emit(f"  enumerate force funcs failed: {e}")
                        # what force-model types can be added?
                        for addm in ("Add", "Insert"):
                            emit(f"  container has `{addm}`: {hasattr(v, addm)}")

        # ---- Initial State element type -> Keplerian ----------------------
        emit("\n## Initial State: switch to Keplerian")
        mcs = driver.MainSequence
        initseg = mcs.Item("Initial State")
        emit(f"- current ElementType: {try_call('initseg.ElementType', lambda: initseg.ElementType, quiet=True)}")
        # try SetElementType with discovered enum values
        etype = getattr(o, "AgEVAElementType", None)
        if etype is not None:
            kep_val = None
            for cand in ("eVAElementTypeKeplerian", "eVAElementKeplerian", "eKeplerian"):
                if hasattr(etype, cand):
                    kep_val = getattr(etype, cand)
                    emit(f"- using AgEVAElementType.{cand} = {int(kep_val)}")
                    break
            if kep_val is not None:
                try_call("initseg.SetElementType(Keplerian)",
                         lambda: initseg.SetElementType(kep_val))
                dump("initseg.Element (after Keplerian)", initseg.Element)

        # ---- smoke test: set a duration + run stock MCS + extract ----------
        emit("\n## Smoke RunMCS with stock propagator")
        propseg = mcs.Item("Propagate")
        stop = propseg.StoppingConditions.Item("Duration").Properties
        try_call("set Duration.Trip=6000", lambda: setattr(stop, "Trip", 6000.0))
        # set a simple Keplerian state if we managed to switch element type
        try:
            el = initseg.Element
            for attr, val in (("SemiMajorAxis", 7078.137), ("SemimajorAxis", 7078.137),
                              ("Eccentricity", 1e-4), ("Inclination", 98.17),
                              ("RAAN", 285.5), ("ArgOfPeriapsis", 0.0),
                              ("TrueAnomaly", 0.0), ("ArgumentOfPeriapsis", 0.0)):
                if hasattr(el, attr):
                    try:
                        setattr(el, attr, val)
                    except Exception:
                        pass
            emit("- set Keplerian element fields where present.")
        except Exception as e:
            emit(f"- element set failed: {e}")
        ran = try_call("driver.RunMCS()", lambda: driver.RunMCS())
        # try extracting classical elements
        try:
            grp = sat.DataProviders.Item("Classical Elements").Group.Item("ICRF")
            start = sat.Propagator.EphemerisInterval.FindStartTime()
            stop_t = sat.Propagator.EphemerisInterval.FindStopTime()
            ds = grp.ExecElements(start, stop_t, 60.0,
                                  ["Time", "Semi-major Axis", "Eccentricity", "Inclination"])
            n = ds.DataSets.Count
            emit(f"- extract OK: {n} element columns; "
                 f"first SMA sample = "
                 f"{list(ds.DataSets.Item(1).GetValues())[:1] if n>1 else '?'}")
        except Exception as e:
            emit(f"- extract FAIL ({type(e).__name__}: {str(e)[:160]})")
    finally:
        os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(_lines) + "\n")
        emit(f"\n(wrote {OUT_MD})")
        try:
            app.ShutDown()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            with open(OUT_MD, "w", encoding="utf-8") as f:
                f.write("\n".join(_lines) + "\n")
        except Exception:
            pass
        sys.exit(1)
