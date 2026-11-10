"""
Write STK Astrogator N-Plate definition files (.nplate) for the flat-plate sail.

Format is the STK plate-definition file documented in
STKData/Flight_Dynamics/{SRP,Drag}_NPlate_Example.nplate (see docs/astrogator_design.md).

Sail model (see plan "SRP modeling reconciliation"):
- SRP  : ONE body-fixed plate, normal = body +Z, specular 0.70 / diffuse 0.0 -> one-sided,
         C_r,eff = 1 + rho_s = 1.7 (the paper's effective C_r).
- Drag : TWO opposed body-fixed plates (+Z, -Z), each area A, drag coeff Cd -> the projected
         area to the flow is A*|cos(theta)| (whichever face leads), matching the paper's
         a_drag ~ A|cos(theta)|.
"""

from __future__ import annotations

from pathlib import Path

# Primary SRP calibration (see plugins/flatplate_srp_hpop.NPLATE_CALIBRATION_PRIMARY).
SRP_SPECULAR = 0.70
SRP_DIFFUSE = 0.0


def write_srp_nplate_file(path, area_m2: float,
                          specular: float = SRP_SPECULAR,
                          diffuse: float = SRP_DIFFUSE,
                          normal=(0.0, 0.0, 1.0)) -> str:
    """One-sided sail SRP plate (body +Z). Returns the absolute path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    nx, ny, nz = normal
    lines = [
        "# Sail SRP N-plate (auto-generated) - one-sided body +Z plate",
        "Version 1.0",
        "Formulation SRP",
        "Begin Plates",
        "# [Name] [Group] [Type] [Area m^2] [Normal X Y Z] [Spec] [Diff]",
        f"  Sail  Sail  B  {area_m2:.6f}  {nx:.6f} {ny:.6f} {nz:.6f}  "
        f"{specular:.6f}  {diffuse:.6f}",
        "End Plates",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_drag_nplate_file(path, area_m2: float, cd: float,
                           cd_scale: float = 1.0) -> str:
    """
    Two opposed body plates (+Z, -Z) so the projected area to the flow is
    A*|cos(theta)| regardless of which face leads. `cd_scale` multiplies Cd for
    the Fig-7 density sweep (drag ~ rho*Cd, so scaling Cd == scaling density).
    Returns the absolute path written.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cd_eff = cd * cd_scale
    lines = [
        "# Sail drag N-plate (auto-generated) - opposed +Z/-Z body plates",
        "Version 1.0",
        "Formulation DragCd",
        "Begin Plates",
        "# [Name] [Group] [Type] [Area m^2] [Normal X Y Z] [Cd]",
        f"  SailPlusZ   Sail  B  {area_m2:.6f}   0.0 0.0  1.0  {cd_eff:.6f}",
        f"  SailMinusZ  Sail  B  {area_m2:.6f}   0.0 0.0 -1.0  {cd_eff:.6f}",
        "End Plates",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


if __name__ == "__main__":
    import tempfile
    d = Path(tempfile.gettempdir())
    print(write_srp_nplate_file(d / "srp_test.nplate", 100.0))
    print((d / "srp_test.nplate").read_text())
    print(write_drag_nplate_file(d / "drag_test.nplate", 100.0, 2.2))
    print((d / "drag_test.nplate").read_text())
