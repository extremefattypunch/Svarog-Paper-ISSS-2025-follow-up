"""
Spacecraft models handed to Orekit's force models.

The paper's sail is one flat plate, but it is *one-sided for SRP* (a sail facing
away from the Sun produces no thrust) and *two-sided for drag* (the projected
area follows A|cos theta| whichever way the flow arrives). A single Orekit
`Panel` carries a single `doubleSided` flag and is shared by
`BoxAndSolarArraySpacecraft`'s drag and radiation paths, so one panel cannot be
both. We therefore build two `BoxAndSolarArraySpacecraft` instances from two
`FixedPanel`s and hand one to `DragForce` and the other to
`RadiationPressureModel`.

That is exactly the STK Astrogator arrangement described in the manuscript --
"a single body-fixed +Z plate for SRP and two opposed +/-Z plates for drag" --
expressed in Orekit's vocabulary.

Panel optics: Orekit's `Panel` takes (absorption, reflection) where `reflection`
is the *specular* coefficient and the diffuse fraction is the remainder. The
paper's calibration (alpha=0.3, rho_s=0.7, rho_d=0) therefore maps directly onto
(absorption=0.3, reflection=0.7), giving C_r,eff = 1 + rho_s = 1.7.
"""

from __future__ import annotations

from .orekit_setup import boot

boot()

from org.hipparchus.geometry.euclidean.threed import Vector3D  # noqa: E402
from org.orekit.forces import FixedPanel, BoxAndSolarArraySpacecraft  # noqa: E402
from org.orekit.forces.drag import IsotropicDrag  # noqa: E402
from java.util import ArrayList  # noqa: E402

from .constants import (  # noqa: E402
    SAIL_AREA, CD, ABSORPTION, SPECULAR,
)

# Body-frame normal of the sail. The attitude provider freezes this axis along
# the inertial sail normal, so the plate normal in inertial space is the paper's
# n_hat by construction.
BODY_NORMAL = Vector3D.PLUS_K


def _plate(area, double_sided, cd, absorption, reflection):
    panels = ArrayList()
    #                  normal,      area, doubleSided, drag, liftRatio, absorption, reflection
    panels.add(FixedPanel(BODY_NORMAL, float(area), bool(double_sided),
                          float(cd), 0.0, float(absorption), float(reflection)))
    return BoxAndSolarArraySpacecraft(panels)


def drag_plate(area: float = SAIL_AREA, cd: float = CD,
               absorption: float = ABSORPTION, reflection: float = SPECULAR):
    """Two-sided flat plate: drag area follows A|cos theta| (paper convention)."""
    return _plate(area, True, cd, absorption, reflection)


def srp_plate(area: float = SAIL_AREA, cd: float = CD,
              absorption: float = ABSORPTION, reflection: float = SPECULAR):
    """One-sided flat plate: no SRP when the sail faces away from the Sun."""
    return _plate(area, False, cd, absorption, reflection)


def spherical_drag(area: float = SAIL_AREA, cd: float = CD):
    """Attitude-independent cannonball drag, for the apples-to-apples validation
    configuration where the result cannot depend on the sail orientation."""
    return IsotropicDrag(float(area), float(cd))
