"""
Inertially-fixed sail attitude for Orekit.

The paper's sail is passively spin-stabilised: its normal is constructed once at
epoch from (LTDN, inclination, pitch, roll) and then frozen in inertial space.
In STK this was imposed with `eProfileFixedInAxes` plus a quaternion mapping
body +Z onto the sail normal -- and STK's N-plate SRP model then failed to
consume it. The Orekit analogue is `FrameAlignedProvider`, a constant rotation
between the inertial frame and the spacecraft frame.

Convention check (verified numerically in validation/v1_component_gates.py):
`Rotation(n_eci, Vector3D.PLUS_K)` is the rotation taking n_eci to +Z, i.e. the
inertial -> body rotation, which is exactly what Orekit's `Attitude` stores. So
`state.getAttitude().getRotation().applyInverseTo(PLUS_K)` returns n_eci, and a
`FixedPanel` whose body normal is +Z has its normal along n_eci in inertial
space -- the behaviour the whole passive-sail model depends on.

The geometric construction of the normal itself is imported verbatim from the
paper's implementation so the two tools start from an identical vector.
"""

from __future__ import annotations

from .orekit_setup import boot

boot()

from org.hipparchus.geometry.euclidean.threed import Vector3D, Rotation  # noqa: E402
from org.orekit.attitudes import FrameAlignedProvider  # noqa: E402

# Paper's own geometry, imported from "STK simulations" (`core` == paper tree).
from core.attitude import inertial_sail_normal  # noqa: E402
from core.orbit_init import (  # noqa: E402
    raan_from_ltdn,
    sun_direction_eci,
    julian_date_from_ymdhms,
)

from .constants import EPOCH  # noqa: E402

JD_EPOCH = julian_date_from_ymdhms(*EPOCH)


def sun_unit_at_epoch():
    """Paper's low-precision analytic Sun direction at the scenario epoch."""
    return sun_direction_eci(JD_EPOCH)


def raan_for_ltdn(ltdn_hours: float) -> float:
    return raan_from_ltdn(ltdn_hours, JD_EPOCH)


def sail_normal_eci(raan_deg: float, inc_deg: float, pitch_deg: float,
                    roll_deg: float = 0.0, sun_unit=None):
    """Inertially-frozen sail normal as a tuple, using the paper's construction."""
    if sun_unit is None:
        sun_unit = sun_unit_at_epoch()
    return inertial_sail_normal(sun_unit, raan_deg, inc_deg, pitch_deg, roll_deg)


def fixed_inertial_attitude(normal_eci, frame):
    """`AttitudeProvider` freezing body +Z along `normal_eci` in `frame`."""
    n = Vector3D(float(normal_eci[0]), float(normal_eci[1]), float(normal_eci[2])).normalize()
    return FrameAlignedProvider(Rotation(n, Vector3D.PLUS_K), frame)
