"""Kerykeion-backed astrological engine.

Preferred production backend. Uses Swiss Ephemeris via pyswisseph for full
precision, Placidus houses (by default), and real Chiron ephemeris.

Requires kerykeion installed (`pip install .[kerykeion]`). Compilation of
pyswisseph on Windows/Python 3.12 needs MSVC Build Tools.

Coverage: Swiss Ephemeris covers ~13000 BCE to ~17000 CE — effectively unlimited
for historical natal data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from realm.core.exceptions import AstroCalculationError
from realm.core.logging import get_logger
from realm.core.types import (
    PLANETS_ALL_PHASE1,
    SIGN_ELEMENT,
    SIGN_MODALITY,
    Aspect,
    NatalChart,
    PlanetPosition,
    TransitSnapshot,
)

from .interfaces import IAstroEngine

logger = get_logger(__name__)


# Kerykeion sign abbreviation → REALM canonical name.
_SIGN_MAP: dict[str, str] = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}

_HOUSE_NAME_TO_INT: dict[str, int] = {
    "First_House": 1, "Second_House": 2, "Third_House": 3, "Fourth_House": 4,
    "Fifth_House": 5, "Sixth_House": 6, "Seventh_House": 7, "Eighth_House": 8,
    "Ninth_House": 9, "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
}

# Kerykeion attribute name → REALM canonical planet name.
_BODY_ATTRS: tuple[tuple[str, str], ...] = (
    ("sun", "Sun"),
    ("moon", "Moon"),
    ("mercury", "Mercury"),
    ("venus", "Venus"),
    ("mars", "Mars"),
    ("jupiter", "Jupiter"),
    ("saturn", "Saturn"),
    ("uranus", "Uranus"),
    ("neptune", "Neptune"),
    ("pluto", "Pluto"),
    ("true_north_lunar_node", "North_Node"),
    ("true_south_lunar_node", "South_Node"),
    ("chiron", "Chiron"),
)

# Kerykeion point name (`p1_name`/`p2_name` on aspects) → canonical.
_KK_POINT_TO_CANONICAL: dict[str, str] = {
    "Sun": "Sun", "Moon": "Moon", "Mercury": "Mercury", "Venus": "Venus",
    "Mars": "Mars", "Jupiter": "Jupiter", "Saturn": "Saturn", "Uranus": "Uranus",
    "Neptune": "Neptune", "Pluto": "Pluto", "Chiron": "Chiron",
    "True_North_Lunar_Node": "North_Node",
    "True_South_Lunar_Node": "South_Node",
    "Mean_North_Lunar_Node": "North_Node",
    "Mean_South_Lunar_Node": "South_Node",
    "True_Node": "North_Node",    # v5 alias
    "Mean_Node": "North_Node",    # v5 alias
}


def _require_kerykeion():
    try:
        import kerykeion  # noqa: F401
    except ImportError as e:
        raise AstroCalculationError(
            "kerykeion is not installed. `pip install .[kerykeion]` "
            "(needs MSVC Build Tools on Windows/Python 3.12)."
        ) from e


def _kerykeion_point_to_position(point, canonical_name: str) -> PlanetPosition:
    """Convert a Kerykeion point model to our PlanetPosition."""
    sign_full = _SIGN_MAP.get(point.sign)
    if sign_full is None:
        raise AstroCalculationError(f"unknown Kerykeion sign code: {point.sign!r}")
    house = _HOUSE_NAME_TO_INT.get(point.house, 1)
    # Kerykeion provides speed as deg/day when available; some points (nodes,
    # Chiron) may not populate it. Default to 0 for those; retrograde flag still
    # drives dignity adjustments downstream.
    speed = float(getattr(point, "speed", 0.0) or 0.0)
    retrograde = bool(getattr(point, "retrograde", False))
    return PlanetPosition(
        name=canonical_name,
        longitude=float(point.abs_pos),
        latitude=float(getattr(point, "declination", 0.0) or 0.0),
        sign=sign_full,
        sign_degree=float(point.position),
        house=house,
        is_retrograde=retrograde,
        speed=speed,
    )


def _build_aspect_list(kk_aspects, natal_point_names: set[str]) -> tuple[Aspect, ...]:
    """Translate Kerykeion aspects, dropping any involving bodies we don't track
    and filtering to the canonical ASPECT_TYPES set (quintile, biquintile, and
    other minor aspects Kerykeion reports are discarded — Phase 1 rule-based
    embedder only uses the six major aspects)."""
    from realm.core.types import ASPECT_TYPES
    canonical = set(ASPECT_TYPES)
    out: list[Aspect] = []
    for a in kk_aspects:
        aspect_type = str(a.aspect).lower()
        if aspect_type not in canonical:
            continue
        p1 = _KK_POINT_TO_CANONICAL.get(a.p1_name, a.p1_name)
        p2 = _KK_POINT_TO_CANONICAL.get(a.p2_name, a.p2_name)
        if p1 not in natal_point_names or p2 not in natal_point_names:
            continue
        out.append(Aspect(
            planet1=p1,
            planet2=p2,
            aspect_type=aspect_type,
            angle=float(getattr(a, "diff", 0.0)),
            orb=abs(float(a.orbit)),
            is_applying=str(getattr(a, "aspect_movement", "")).lower() == "applying",
        ))
    return tuple(out)


def _build_houses(subject) -> tuple[float, ...]:
    cusps: list[float] = []
    for attr in (
        "first_house", "second_house", "third_house", "fourth_house",
        "fifth_house", "sixth_house", "seventh_house", "eighth_house",
        "ninth_house", "tenth_house", "eleventh_house", "twelfth_house",
    ):
        h = getattr(subject, attr)
        cusps.append(float(h.abs_pos))
    return tuple(cusps)


def _balance_weights(name: str) -> float:
    return {
        "Sun": 2.0, "Moon": 2.0,
        "Mercury": 1.5, "Venus": 1.5, "Mars": 1.5,
        "Jupiter": 1.0, "Saturn": 1.0,
        "Uranus": 0.5, "Neptune": 0.5, "Pluto": 0.5,
        "North_Node": 0.3, "South_Node": 0.3, "Chiron": 0.3,
    }.get(name, 0.5)


def _element_balance(planets: tuple[PlanetPosition, ...]) -> dict[str, float]:
    totals = dict.fromkeys(("fire", "earth", "air", "water"), 0.0)
    for p in planets:
        totals[SIGN_ELEMENT[p.sign]] += _balance_weights(p.name)
    s = sum(totals.values()) or 1.0
    return {k: v / s for k, v in totals.items()}


def _modality_balance(planets: tuple[PlanetPosition, ...]) -> dict[str, float]:
    totals = dict.fromkeys(("cardinal", "fixed", "mutable"), 0.0)
    for p in planets:
        totals[SIGN_MODALITY[p.sign]] += _balance_weights(p.name)
    s = sum(totals.values()) or 1.0
    return {k: v / s for k, v in totals.items()}


class KerykeionEngine(IAstroEngine):
    """Swiss-Ephemeris backed engine."""

    backend = "kerykeion"

    def __init__(self, house_system: str = "P") -> None:
        """house_system: Kerykeion single-letter code. 'P' = Placidus (default).
        Other options: 'K' = Koch, 'E' = Equal, 'W' = Whole Sign, etc."""
        _require_kerykeion()
        self._house_system = house_system

    @property
    def backend_name(self) -> str:
        return self.backend

    def calculate_natal_chart(
        self, birth_dt: datetime, latitude: float, longitude: float, timezone: str,
    ) -> NatalChart:
        if birth_dt.tzinfo is None:
            raise AstroCalculationError("birth_dt must be timezone-aware")
        if not -90.0 <= latitude <= 90.0:
            raise AstroCalculationError(f"latitude out of range: {latitude}")
        if not -180.0 <= longitude <= 180.0:
            raise AstroCalculationError(f"longitude out of range: {longitude}")

        try:
            from kerykeion import AstrologicalSubject, NatalAspects
        except ImportError as e:
            raise AstroCalculationError("kerykeion import failed") from e

        try:
            from zoneinfo import ZoneInfo
            local_dt = birth_dt.astimezone(ZoneInfo(timezone))
        except Exception as e:
            logger.warning("Timezone conversion failed (%s); using UTC clock values", e)
            local_dt = birth_dt.astimezone(UTC)

        try:
            subject = AstrologicalSubject(
                name="realm_agent",
                year=local_dt.year, month=local_dt.month, day=local_dt.day,
                hour=local_dt.hour, minute=local_dt.minute,
                lat=latitude, lng=longitude, tz_str=timezone,
                houses_system_identifier=self._house_system,
                # online=False suppresses Kerykeion's GeoNames API lookup —
                # we already have lat/lng/tz_str from our own dataset, so no
                # network call is needed. Eliminates the "NO GEONAMES USERNAME"
                # warning, removes a shared-rate-limit dependency, and keeps
                # the hot path deterministic / offline.
                online=False,
            )
        except Exception as e:
            raise AstroCalculationError(f"Kerykeion subject creation failed: {e}") from e

        try:
            planets: list[PlanetPosition] = []
            for attr, canonical in _BODY_ATTRS:
                point = getattr(subject, attr, None)
                if point is None:
                    logger.debug("Kerykeion subject missing %s; skipping", attr)
                    continue
                planets.append(_kerykeion_point_to_position(point, canonical))

            assert len(planets) == len(PLANETS_ALL_PHASE1), (
                f"expected {len(PLANETS_ALL_PHASE1)} bodies, got {len(planets)}"
            )
            planets_tuple = tuple(planets)
            point_name_set = {p.name for p in planets_tuple}

            houses = _build_houses(subject)
            asc = houses[0]
            mc = houses[9]

            kk_aspects = NatalAspects(subject).all_aspects
            aspects_tuple = _build_aspect_list(kk_aspects, point_name_set)

            return NatalChart(
                birth_datetime=birth_dt,
                latitude=latitude, longitude=longitude, timezone=timezone,
                planets=planets_tuple,
                houses=houses,
                aspects=aspects_tuple,
                ascendant=asc, midheaven=mc,
                element_balance=_element_balance(planets_tuple),
                modality_balance=_modality_balance(planets_tuple),
            )
        except AstroCalculationError:
            raise
        except Exception as e:
            raise AstroCalculationError(f"Natal calculation failed: {e}") from e

    def calculate_transits(
        self, natal: NatalChart, target_dt: datetime,
    ) -> TransitSnapshot:
        """Phase 1 transits — compute a fresh natal-like chart at target time and
        derive transit→natal aspects via our pure-Python aspect calculator."""
        if target_dt.tzinfo is None:
            raise AstroCalculationError("target_dt must be timezone-aware")
        from .aspect_calculator import find_transit_aspects

        # Use the same location/tz as the natal chart for the "transit chart".
        transit_chart = self.calculate_natal_chart(
            target_dt, natal.latitude, natal.longitude, natal.timezone,
        )
        transit_orbs = {
            "conjunction": 3.0, "opposition": 3.0, "trine": 2.5,
            "square": 2.5, "sextile": 2.0, "quincunx": 1.5,
        }
        active = find_transit_aspects(transit_chart.planets, natal.planets, transit_orbs)
        retrograde = tuple(p.name for p in transit_chart.planets if p.is_retrograde)

        sun = transit_chart.planet("Sun")
        moon = transit_chart.planet("Moon")
        phase = _moon_phase(sun.longitude if sun else 0.0, moon.longitude if moon else 0.0)
        return TransitSnapshot(
            timestamp=target_dt,
            transiting_planets=transit_chart.planets,
            active_transits=active,
            moon_phase=phase,
            retrograde_planets=retrograde,
        )

    def calculate_transit_range(
        self, natal: NatalChart, start_dt: datetime, end_dt: datetime,
        interval_hours: int = 24,
    ) -> list[TransitSnapshot]:
        if end_dt <= start_dt:
            raise AstroCalculationError("end_dt must be after start_dt")
        snaps: list[TransitSnapshot] = []
        cursor = start_dt
        while cursor <= end_dt:
            snaps.append(self.calculate_transits(natal, cursor))
            cursor += timedelta(hours=interval_hours)
        return snaps


def _moon_phase(sun_lon: float, moon_lon: float) -> str:
    diff = (moon_lon - sun_lon) % 360.0
    if diff < 45 or diff >= 315:
        return "new"
    if diff < 135:
        return "waxing"
    if diff < 225:
        return "full"
    return "waning"
