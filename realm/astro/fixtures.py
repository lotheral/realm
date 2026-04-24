"""Deterministic natal chart fixtures for tests and offline demos.

These fixtures cover famous figures with documented birth data. The synthetic
chart is built by running SkyfieldEngine at module-level-lazy-evaluation — so
tests that just want "a valid chart" don't need to know any astronomy.

For regression stability, we also expose hand-crafted static charts that don't
depend on ephemeris — useful for testing downstream code (aspect-based trait
shifts, etc.) in isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

from realm.core.types import NatalChart, PlanetPosition

from .aspect_calculator import find_all_aspects
from .house_system import equal_house_cusps, house_for_longitude, sign_from_longitude


class BirthData(NamedTuple):
    """Verified historical birth record."""

    name: str
    birth_dt: datetime       # timezone-aware
    latitude: float
    longitude: float
    timezone: str


# All dates are tz-aware local times converted appropriately.
STEVE_JOBS = BirthData(
    name="Steve Jobs",
    birth_dt=datetime(1955, 2, 24, 19, 15, tzinfo=UTC).astimezone(
        UTC
    ).replace(tzinfo=UTC),
    # Using UTC offsets. Local: 1955-02-24 19:15 PST (UTC-8). UTC = 1955-02-25 03:15.
    latitude=37.7749,
    longitude=-122.4194,
    timezone="America/Los_Angeles",
)
STEVE_JOBS = STEVE_JOBS._replace(
    birth_dt=datetime(1955, 2, 25, 3, 15, tzinfo=UTC),
)

CARL_SAGAN = BirthData(
    name="Carl Sagan",
    # Born 1934-11-09 05:05 EST (UTC-5) in Brooklyn, NY
    birth_dt=datetime(1934, 11, 9, 10, 5, tzinfo=UTC),
    latitude=40.6782,
    longitude=-73.9442,
    timezone="America/New_York",
)

MARIE_CURIE = BirthData(
    name="Marie Curie",
    # Born 1867-11-07 in Warsaw. Outside DE421 range (pre-1899) — kept for
    # reference; use fixtures.static_chart_marie_curie() for tests.
    birth_dt=datetime(1867, 11, 7, 11, 0, tzinfo=UTC),
    latitude=52.2297,
    longitude=21.0122,
    timezone="Europe/Warsaw",
)

ALAN_TURING = BirthData(
    name="Alan Turing",
    # Born 1912-06-23 02:15 GMT (UTC+0) in Maida Vale, London
    birth_dt=datetime(1912, 6, 23, 2, 15, tzinfo=UTC),
    latitude=51.5237,
    longitude=-0.1850,
    timezone="Europe/London",
)

KNOWN_SUBJECTS: tuple[BirthData, ...] = (STEVE_JOBS, CARL_SAGAN, ALAN_TURING)


# ---- Hand-crafted static chart ------------------------------------------
# For tests that need a fully determined chart WITHOUT running an ephemeris.

def _planet(name: str, lon: float, speed: float = 1.0,
            retrograde: bool = False, cusps: tuple[float, ...] | None = None) -> PlanetPosition:
    sign, deg = sign_from_longitude(lon)
    cusps_used = cusps or tuple(i * 30.0 for i in range(12))
    return PlanetPosition(
        name=name, longitude=lon % 360.0, latitude=0.0,
        sign=sign, sign_degree=deg,
        house=house_for_longitude(lon, cusps_used),
        is_retrograde=retrograde, speed=-abs(speed) if retrograde else abs(speed),
    )


def synthetic_chart() -> NatalChart:
    """A fully determined 13-body chart for deterministic downstream tests.

    - Sun at Aries 15°, Moon at Cancer 10° (trine)
    - Mars at Aries 20° (conjunct Sun)
    - All other bodies placed at spaced longitudes so aspect patterns are predictable.
    """
    asc = 0.0
    cusps = equal_house_cusps(asc)

    planets = (
        _planet("Sun", 15.0, 1.0, cusps=cusps),              # Aries 15°
        _planet("Moon", 100.0, 13.0, cusps=cusps),           # Cancer 10°
        _planet("Mercury", 25.0, 1.5, cusps=cusps),          # Aries 25°
        _planet("Venus", 45.0, 1.2, cusps=cusps),            # Taurus 15°
        _planet("Mars", 20.0, 0.7, cusps=cusps),             # Aries 20° (conjunct Sun)
        _planet("Jupiter", 255.0, 0.1, cusps=cusps),         # Sagittarius 15°
        _planet("Saturn", 285.0, 0.05, cusps=cusps),         # Capricorn 15°
        _planet("Uranus", 315.0, 0.03, retrograde=True, cusps=cusps),  # Aquarius 15°
        _planet("Neptune", 345.0, 0.02, cusps=cusps),        # Pisces 15°
        _planet("Pluto", 225.0, 0.01, cusps=cusps),          # Scorpio 15°
        _planet("North_Node", 75.0, -0.053, retrograde=True, cusps=cusps),  # Gemini 15°
        _planet("South_Node", 255.0, -0.053, retrograde=True, cusps=cusps), # Sag 15° (conj Jupiter)
        _planet("Chiron", 150.0, 0.05, cusps=cusps),         # Virgo 0°
    )

    orbs = {
        "conjunction": 8.0, "opposition": 8.0, "trine": 7.0,
        "square": 7.0, "sextile": 5.0, "quincunx": 3.0,
    }
    aspects = find_all_aspects(planets, orbs)

    # Element balance: more fire/water than air/earth in this synthetic chart.
    element_balance = {"fire": 0.40, "water": 0.30, "earth": 0.15, "air": 0.15}
    modality_balance = {"cardinal": 0.40, "fixed": 0.30, "mutable": 0.30}

    return NatalChart(
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=UTC),
        latitude=0.0, longitude=0.0, timezone="UTC",
        planets=planets,
        houses=cusps,
        aspects=aspects,
        ascendant=asc,
        midheaven=270.0,
        element_balance=element_balance,
        modality_balance=modality_balance,
    )
