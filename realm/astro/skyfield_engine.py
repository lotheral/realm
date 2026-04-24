"""Skyfield-based astrological engine.

Phase 1 ephemeris backend. Computes the 10 classical planets from JPL DE421
and derives North Node / South Node from mean lunar node formula. Chiron is
returned as a neutral placeholder (Phase 1 limitation — switch to the Kerykeion
backend for Chiron ephemeris support).

Houses: Equal House system (Ascendant = cusp 1, +30° per house).

Skyfield coverage (DE421): 1899-07-29 through 2053-10-09. For earlier/later
dates, load a wider ephemeris file (e.g. de440s.bsp).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from realm.core.exceptions import AstroCalculationError
from realm.core.logging import get_logger
from realm.core.types import (
    PLANETS_ALL_PHASE1,
    SIGN_ELEMENT,
    SIGN_MODALITY,
    NatalChart,
    PlanetPosition,
    TransitSnapshot,
)

from .aspect_calculator import find_all_aspects, find_transit_aspects
from .house_system import equal_house_cusps, house_for_longitude, sign_from_longitude
from .interfaces import IAstroEngine

logger = get_logger(__name__)

# Mapping from REALM canonical names to Skyfield / DE421 keys.
_SKYFIELD_PLANETS: dict[str, str] = {
    "Sun": "sun",
    "Moon": "moon",
    "Mercury": "mercury",
    "Venus": "venus",
    "Mars": "mars barycenter",
    "Jupiter": "jupiter barycenter",
    "Saturn": "saturn barycenter",
    "Uranus": "uranus barycenter",
    "Neptune": "neptune barycenter",
    "Pluto": "pluto barycenter",
}

_OBLIQUITY_J2000: float = 23.4392911  # degrees


@lru_cache(maxsize=1)
def _load_skyfield():
    """Lazy-load Skyfield timescale and ephemeris (cached)."""
    try:
        from skyfield.api import load
    except ImportError as e:
        raise AstroCalculationError(
            "skyfield is not installed. Run: pip install skyfield"
        ) from e
    ts = load.timescale()
    eph = load("de421.bsp")
    return ts, eph


def _mean_node_longitude(dt_utc: datetime) -> float:
    """Mean lunar ascending node longitude in degrees (geocentric, ecliptic of date).

    Formula: Omega = 125.04452° - 1934.136261°/century · T
    where T is centuries since J2000.0 TT (approximated with UTC).
    """
    jd = _julian_day_utc(dt_utc)
    t_centuries = (jd - 2451545.0) / 36525.0
    omega = 125.04452 - 1934.136261 * t_centuries
    return omega % 360.0


def _julian_day_utc(dt: datetime) -> float:
    """Julian Day Number for a UTC datetime."""
    if dt.tzinfo is None:
        raise AstroCalculationError("datetime must be timezone-aware")
    dt_utc = dt.astimezone(UTC)
    y, m, d = dt_utc.year, dt_utc.month, dt_utc.day
    frac = (dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    return jd + frac


def _greenwich_sidereal_time_degrees(dt_utc: datetime) -> float:
    """Greenwich Apparent Sidereal Time at `dt_utc`, in degrees (0–360)."""
    jd = _julian_day_utc(dt_utc)
    t = (jd - 2451545.0) / 36525.0
    # Mean sidereal time at Greenwich (IAU 1982 formula, simplified)
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t
        + 0.093104 * t * t
        - 6.2e-6 * t * t * t
    )
    gmst_deg = (gmst_sec / 3600.0) * 15.0
    return gmst_deg % 360.0


def _ascendant(dt_utc: datetime, latitude_deg: float, longitude_deg: float) -> float:
    """Ecliptic longitude of the rising point (Ascendant), in degrees.

    Formula (Meeus, Astronomical Algorithms, eq. 13.2):
        ASC = atan2( cos(LST),  -(sin(LST)·cos(ε) + tan(φ)·sin(ε)) )

    The sign convention places the result in the ecliptic half that is actually
    rising; a naive tan-only formula gives the descendant half the time.
    """
    gst = _greenwich_sidereal_time_degrees(dt_utc)
    lst_deg = (gst + longitude_deg) % 360.0
    lst = math.radians(lst_deg)
    phi = math.radians(latitude_deg)
    eps = math.radians(_OBLIQUITY_J2000)
    asc_rad = math.atan2(
        math.cos(lst),
        -(math.sin(lst) * math.cos(eps) + math.tan(phi) * math.sin(eps)),
    )
    return math.degrees(asc_rad) % 360.0


def _midheaven(dt_utc: datetime, longitude_deg: float) -> float:
    """Midheaven (MC) — ecliptic longitude of upper meridian, in degrees."""
    gst = _greenwich_sidereal_time_degrees(dt_utc)
    lst_deg = (gst + longitude_deg) % 360.0
    lst = math.radians(lst_deg)
    eps = math.radians(_OBLIQUITY_J2000)
    mc_rad = math.atan2(math.sin(lst), math.cos(lst) * math.cos(eps))
    return math.degrees(mc_rad) % 360.0


def _compute_planet_longitude(ts, eph, body_key: str, dt_utc: datetime) -> float:
    t = ts.utc(
        dt_utc.year, dt_utc.month, dt_utc.day,
        dt_utc.hour, dt_utc.minute, dt_utc.second + dt_utc.microsecond * 1e-6,
    )
    astrometric = eph["earth"].at(t).observe(eph[body_key]).apparent()
    _, lon, _ = astrometric.ecliptic_latlon()
    return float(lon.degrees) % 360.0


def _compute_planet_position(
    ts, eph, canonical_name: str, body_key: str,
    dt_utc: datetime, cusps: tuple[float, ...],
) -> PlanetPosition:
    t = ts.utc(
        dt_utc.year, dt_utc.month, dt_utc.day,
        dt_utc.hour, dt_utc.minute, dt_utc.second + dt_utc.microsecond * 1e-6,
    )
    astrometric = eph["earth"].at(t).observe(eph[body_key]).apparent()
    eclon_lat, eclon_lon, _ = astrometric.ecliptic_latlon()
    lon_deg = float(eclon_lon.degrees) % 360.0
    lat_deg = float(eclon_lat.degrees)

    # Speed: sample 1 hour later; convert to deg/day.
    dt_later = dt_utc + timedelta(hours=1)
    lon_later = _compute_planet_longitude(ts, eph, body_key, dt_later)
    raw_delta = (lon_later - lon_deg + 540.0) % 360.0 - 180.0  # signed, [-180,180)
    speed_per_day = raw_delta * 24.0

    sign, sign_deg = sign_from_longitude(lon_deg)
    return PlanetPosition(
        name=canonical_name,
        longitude=lon_deg,
        latitude=lat_deg,
        sign=sign,
        sign_degree=sign_deg,
        house=house_for_longitude(lon_deg, cusps),
        is_retrograde=speed_per_day < 0,
        speed=speed_per_day,
    )


def _compute_node_positions(
    dt_utc: datetime, cusps: tuple[float, ...],
) -> tuple[PlanetPosition, PlanetPosition]:
    """North and South nodes (Mean). Nodes retrograde slowly (~-0.053°/day)."""
    lon_north = _mean_node_longitude(dt_utc)
    lon_south = (lon_north + 180.0) % 360.0
    speed = -0.0529539  # deg/day, mean regression rate
    sign_n, deg_n = sign_from_longitude(lon_north)
    sign_s, deg_s = sign_from_longitude(lon_south)
    north = PlanetPosition(
        name="North_Node", longitude=lon_north, latitude=0.0,
        sign=sign_n, sign_degree=deg_n,
        house=house_for_longitude(lon_north, cusps),
        is_retrograde=True, speed=speed,
    )
    south = PlanetPosition(
        name="South_Node", longitude=lon_south, latitude=0.0,
        sign=sign_s, sign_degree=deg_s,
        house=house_for_longitude(lon_south, cusps),
        is_retrograde=True, speed=speed,
    )
    return north, south


def _placeholder_chiron(cusps: tuple[float, ...]) -> PlanetPosition:
    """Phase 1 placeholder. Returns Chiron at Virgo 0° with neutral dignity.

    Replace with Kerykeion backend or a proper Chiron ephemeris for accurate
    values. Current implementation preserves downstream pipeline but contributes
    only neutral modifiers to the trait vector.
    """
    lon = 150.0  # Virgo 0°
    sign, deg = sign_from_longitude(lon)
    return PlanetPosition(
        name="Chiron", longitude=lon, latitude=0.0,
        sign=sign, sign_degree=deg,
        house=house_for_longitude(lon, cusps),
        is_retrograde=False, speed=0.05,
    )


def _element_balance(planets: tuple[PlanetPosition, ...]) -> dict[str, float]:
    """Relative share of luminaries + personal planets in each element.

    Sun/Moon get weight 2; Mercury/Venus/Mars weight 1.5; social planets (Jupiter,
    Saturn) weight 1.0; outer planets (Uranus, Neptune, Pluto) weight 0.5; nodes
    and Chiron weight 0.3.
    """
    weights = {
        "Sun": 2.0, "Moon": 2.0,
        "Mercury": 1.5, "Venus": 1.5, "Mars": 1.5,
        "Jupiter": 1.0, "Saturn": 1.0,
        "Uranus": 0.5, "Neptune": 0.5, "Pluto": 0.5,
        "North_Node": 0.3, "South_Node": 0.3, "Chiron": 0.3,
    }
    totals = dict.fromkeys(("fire", "earth", "air", "water"), 0.0)
    for p in planets:
        w = weights.get(p.name, 0.5)
        totals[SIGN_ELEMENT[p.sign]] += w
    total = sum(totals.values()) or 1.0
    return {k: v / total for k, v in totals.items()}


def _modality_balance(planets: tuple[PlanetPosition, ...]) -> dict[str, float]:
    weights = {
        "Sun": 2.0, "Moon": 2.0,
        "Mercury": 1.5, "Venus": 1.5, "Mars": 1.5,
        "Jupiter": 1.0, "Saturn": 1.0,
        "Uranus": 0.5, "Neptune": 0.5, "Pluto": 0.5,
        "North_Node": 0.3, "South_Node": 0.3, "Chiron": 0.3,
    }
    totals = dict.fromkeys(("cardinal", "fixed", "mutable"), 0.0)
    for p in planets:
        w = weights.get(p.name, 0.5)
        totals[SIGN_MODALITY[p.sign]] += w
    total = sum(totals.values()) or 1.0
    return {k: v / total for k, v in totals.items()}


class SkyfieldEngine(IAstroEngine):
    """Skyfield/JPL-DE421 backed natal and transit engine."""

    backend = "skyfield"

    def __init__(self, orbs: dict[str, float] | None = None) -> None:
        self._orbs = orbs or {
            "conjunction": 8.0, "opposition": 8.0, "trine": 7.0,
            "square": 7.0, "sextile": 5.0, "quincunx": 3.0,
        }
        self._transit_orbs = {
            "conjunction": 3.0, "opposition": 3.0, "trine": 2.5,
            "square": 2.5, "sextile": 2.0, "quincunx": 1.5,
        }

    @property
    def backend_name(self) -> str:
        return self.backend

    def calculate_natal_chart(
        self,
        birth_dt: datetime,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> NatalChart:
        if birth_dt.tzinfo is None:
            raise AstroCalculationError("birth_dt must be timezone-aware")
        if not -90.0 <= latitude <= 90.0:
            raise AstroCalculationError(f"latitude out of range: {latitude}")
        if not -180.0 <= longitude <= 180.0:
            raise AstroCalculationError(f"longitude out of range: {longitude}")

        dt_utc = birth_dt.astimezone(UTC)

        ts, eph = _load_skyfield()

        try:
            asc = _ascendant(dt_utc, latitude, longitude)
            mc = _midheaven(dt_utc, longitude)
            cusps = equal_house_cusps(asc)

            planets: list[PlanetPosition] = []
            for canonical, body_key in _SKYFIELD_PLANETS.items():
                planets.append(
                    _compute_planet_position(ts, eph, canonical, body_key, dt_utc, cusps)
                )
            north, south = _compute_node_positions(dt_utc, cusps)
            planets.append(north)
            planets.append(south)
            planets.append(_placeholder_chiron(cusps))

            # Sanity check
            assert len(planets) == len(PLANETS_ALL_PHASE1), (
                f"expected {len(PLANETS_ALL_PHASE1)} bodies, got {len(planets)}"
            )

            planets_tuple = tuple(planets)
            aspects = find_all_aspects(planets_tuple, self._orbs)

            return NatalChart(
                birth_datetime=birth_dt,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                planets=planets_tuple,
                houses=cusps,
                aspects=aspects,
                ascendant=asc,
                midheaven=mc,
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
        if target_dt.tzinfo is None:
            raise AstroCalculationError("target_dt must be timezone-aware")
        dt_utc = target_dt.astimezone(UTC)
        ts, eph = _load_skyfield()

        # Transit planets computed geocentrically (house=1 placeholder, we
        # don't need natal-relative houses for transits in Phase 1).
        dummy_cusps = tuple(i * 30.0 for i in range(12))
        transiting: list[PlanetPosition] = []
        for canonical, body_key in _SKYFIELD_PLANETS.items():
            transiting.append(
                _compute_planet_position(ts, eph, canonical, body_key, dt_utc, dummy_cusps)
            )
        north, south = _compute_node_positions(dt_utc, dummy_cusps)
        transiting.extend([north, south, _placeholder_chiron(dummy_cusps)])

        transits_tuple = tuple(transiting)
        active = find_transit_aspects(transits_tuple, natal.planets, self._transit_orbs)
        retrograde = tuple(p.name for p in transits_tuple if p.is_retrograde)

        moon = next((p for p in transits_tuple if p.name == "Moon"), None)
        sun = next((p for p in transits_tuple if p.name == "Sun"), None)
        phase = _moon_phase(sun.longitude if sun else 0.0, moon.longitude if moon else 0.0)

        return TransitSnapshot(
            timestamp=target_dt,
            transiting_planets=transits_tuple,
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
        snapshots: list[TransitSnapshot] = []
        cursor = start_dt
        while cursor <= end_dt:
            snapshots.append(self.calculate_transits(natal, cursor))
            cursor += timedelta(hours=interval_hours)
        return snapshots


def _moon_phase(sun_lon: float, moon_lon: float) -> str:
    diff = (moon_lon - sun_lon) % 360.0
    if diff < 45 or diff >= 315:
        return "new"
    if diff < 135:
        return "waxing"
    if diff < 225:
        return "full"
    return "waning"
