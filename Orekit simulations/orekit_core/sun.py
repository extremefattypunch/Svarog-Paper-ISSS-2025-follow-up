"""
The paper's analytic Sun, as an Orekit `ExtendedPositionProvider`.

Orekit reads DE-440; the paper's propagator uses a low-precision analytic
(Meeus) series and holds the Earth-Sun distance at exactly one astronomical
unit. Over the study window the directions differ by up to 0.37 degrees and,
more consequentially, the true distance departs from 1 AU by up to 1.67 per
cent -- a 3.4 per cent flux difference, since the epoch falls within days of
perihelion.

That difference is a legitimate modelling difference to report, but it also
blocks a propagated SRP cross-validation: any disagreement between the two
tools with SRP enabled would be a mixture of ephemeris and propagator effects.
Wrapping the paper's own Sun routine in Orekit's provider interface lets the
ephemeris be held fixed, so the two effects can be separated by running Orekit
both ways.

As with `Atmosphere`, JPype proxies do not inherit Java default methods, so
every overload Orekit might call is written out here, and each branches on
whether it was handed field or double arguments.
"""

from __future__ import annotations

from .orekit_setup import boot

boot()

from jpype import JImplements, JOverride  # noqa: E402
from org.hipparchus.geometry.euclidean.threed import Vector3D, FieldVector3D  # noqa: E402
from org.orekit.utils import PVCoordinates, FieldPVCoordinates, TimeStampedPVCoordinates  # noqa: E402

from core.orbit_init import sun_direction_eci  # noqa: E402

from .attitude import JD_EPOCH  # noqa: E402
from .constants import AU  # noqa: E402
from .propagation import EME2000, T0  # noqa: E402


def _paper_sun_vector(seconds_from_epoch: float) -> Vector3D:
    u = sun_direction_eci(JD_EPOCH + seconds_from_epoch / 86400.0)
    return Vector3D(float(u[0]) * AU, float(u[1]) * AU, float(u[2]) * AU)


@JImplements("org.orekit.utils.ExtendedPositionProvider")
class AnalyticSun:
    """Earth-centred Sun position from the paper's Meeus series, fixed at 1 AU.

    Positions are produced in EME2000 and transformed to whatever frame the
    caller asks for, so this behaves like any other Orekit body provider.
    """

    @JOverride
    def getPosition(self, date, frame):
        # Field variant: the date carries CalculusFieldElement components.
        if hasattr(date, "getField"):
            dt = date.durationFrom(T0)
            seconds = float(dt.getReal()) if hasattr(dt, "getReal") else float(dt)
            v = _paper_sun_vector(seconds)
            if frame is not EME2000:
                v = EME2000.getStaticTransformTo(frame, date.toAbsoluteDate()) \
                    .transformPosition(v)
            return FieldVector3D(date.getField(), v)
        seconds = float(date.durationFrom(T0))
        v = _paper_sun_vector(seconds)
        if frame is not EME2000:
            v = EME2000.getStaticTransformTo(frame, date).transformPosition(v)
        return v

    @JOverride
    def getPVCoordinates(self, date, frame):
        """Position with a finite-difference velocity, in case Orekit asks."""
        if hasattr(date, "getField"):
            zero = FieldVector3D(date.getField(), Vector3D.ZERO)
            return FieldPVCoordinates(self.getPosition(date, frame), zero)
        h = 60.0
        p = self.getPosition(date, frame)
        pm = self.getPosition(date.shiftedBy(-h), frame)
        pp = self.getPosition(date.shiftedBy(h), frame)
        v = pp.subtract(pm).scalarMultiply(1.0 / (2.0 * h))
        return TimeStampedPVCoordinates(date, p, v)
