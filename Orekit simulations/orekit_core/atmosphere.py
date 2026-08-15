"""
US Standard Atmosphere 1976 as an Orekit `Atmosphere`.

Orekit ships DTM2000, NRLMSISE-00, JB2008, Harris-Priester and a single-scale-
height exponential model, but not the piecewise-exponential US-1976 profile the
paper uses. Rather than substitute a different atmosphere (which would confound
the comparison), we implement Orekit's `Atmosphere` *interface* in Python with
JPype and delegate the density lookup to the paper's own table, imported
verbatim from the sibling STK study. Orekit then owns the integration, the
frames and the drag force assembly; only rho(h) is ours.

Two implementation notes that matter:

1. JPype proxies do not inherit Java `default` interface methods, so
   `getVelocity` must be implemented explicitly even though `Atmosphere`
   provides a default. That turns out to be an advantage: it makes the
   atmosphere co-rotation assumption an explicit, switchable modelling choice
   (`corotating=`), which is exactly the ambiguity the manuscript flags as a
   candidate explanation for the STK-vs-open-source drag divergence.

2. Every method must accept both the double and the CalculusFieldElement
   (`Field*`) call signatures, because Orekit dispatches to the field variants
   when computing partial derivatives. We branch on the argument type.
"""

from __future__ import annotations

from .orekit_setup import boot

boot()

from jpype import JImplements, JOverride  # noqa: E402
from org.hipparchus.geometry.euclidean.threed import Vector3D, FieldVector3D  # noqa: E402
from org.orekit.utils import PVCoordinates, FieldPVCoordinates  # noqa: E402

# The paper's own density table, imported (not copied) from "STK simulations".
from plugins.flatplate_drag_hpop import density_us1976_kg_m3  # noqa: E402

from .constants import R_EARTH  # noqa: E402


def _is_field(x) -> bool:
    return hasattr(x, "getReal")


@JImplements("org.orekit.models.earth.atmosphere.Atmosphere")
class US1976Atmosphere:
    """Piecewise-exponential US-1976 density, spherical geocentric altitude.

    Parameters
    ----------
    frame
        The frame the atmosphere is attached to. Pass an inertial frame (EME2000)
        together with ``corotating=False`` for the paper's convention; pass ITRF
        with ``corotating=True`` for the standard flight-dynamics convention.
    scaling
        Constant multiplier on rho (the manuscript's Fig.-7 density sweep).
    corotating
        If False the atmosphere is at rest in the inertial frame, so the
        atmosphere-relative velocity equals the inertial velocity -- the paper's
        stated assumption. If True the atmosphere rigidly rotates with ``frame``.
    """

    def __init__(self, frame, scaling: float = 1.0, corotating: bool = False,
                 altitude_mode: str = "geocentric", ellipsoid=None):
        self._frame = frame
        self._scaling = float(scaling)
        self._corotating = bool(corotating)
        if altitude_mode not in ("geocentric", "geodetic"):
            raise ValueError("altitude_mode must be 'geocentric' or 'geodetic'")
        self._altitude_mode = altitude_mode
        if altitude_mode == "geodetic":
            if ellipsoid is None:
                raise ValueError("geodetic altitude requires an ellipsoid")
            self._ellipsoid = ellipsoid
        else:
            self._ellipsoid = None

    # -- Atmosphere interface -------------------------------------------------
    @JOverride
    def getFrame(self):
        return self._frame

    @JOverride
    def getDensity(self, date, position, frame):
        if self._altitude_mode == "geodetic":
            # Height above the WGS-84 ellipsoid rather than above a sphere of
            # radius R_EARTH. For a near-polar orbit the two differ by up to the
            # ~21 km equatorial bulge, which at a 124 km scale height is a
            # substantial density change -- one of the candidate explanations
            # the manuscript raises for the STK drag discrepancy.
            if _is_field(position.getX()):
                p = Vector3D(float(position.getX().getReal()),
                             float(position.getY().getReal()),
                             float(position.getZ().getReal()))
                alt = self._ellipsoid.transform(p, frame, date).getAltitude()
                rho = density_us1976_kg_m3(float(alt), scaling=self._scaling)
                return position.getX().getField().getZero().add(rho)
            alt = self._ellipsoid.transform(position, frame, date).getAltitude()
            return density_us1976_kg_m3(float(alt), scaling=self._scaling)

        alt = position.getNorm() - R_EARTH
        if _is_field(alt):
            rho = density_us1976_kg_m3(float(alt.getReal()), scaling=self._scaling)
            return alt.getField().getZero().add(rho)
        return density_us1976_kg_m3(float(alt), scaling=self._scaling)

    @JOverride
    def getVelocity(self, date, position, frame):
        field = _is_field(position.getX())
        if not self._corotating:
            # At rest in the inertial frame: no atmosphere co-rotation.
            if field:
                return FieldVector3D(position.getX().getField(), Vector3D.ZERO)
            return Vector3D.ZERO
        # Rigid rotation with self._frame -- replicates Orekit's default method.
        transform = self._frame.getTransformTo(frame, date)
        pos_body = transform.getStaticInverse().transformPosition(position)
        if field:
            zero = FieldVector3D(position.getX().getField(), Vector3D.ZERO)
            return transform.transformPVCoordinates(
                FieldPVCoordinates(pos_body, zero)).getVelocity()
        return transform.transformPVCoordinates(
            PVCoordinates(pos_body, Vector3D.ZERO)).getVelocity()

    # -- Convenience ----------------------------------------------------------
    def density_at_altitude(self, altitude_m: float) -> float:
        return density_us1976_kg_m3(float(altitude_m), scaling=self._scaling)
