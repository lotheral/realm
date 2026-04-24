"""Shared astrological data types.

These are immutable value objects used across AstroCore, PersonalityEngine,
and SimulationEngine. Types stay in core/ because multiple modules depend on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ---- Canonical vocabulary -------------------------------------------------

SIGNS: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

PLANETS_CLASSIC: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
)
# REALM canonical names for extended bodies.
PLANETS_NODES: tuple[str, ...] = ("North_Node", "South_Node")
PLANETS_EXTRA: tuple[str, ...] = ("Chiron",)
PLANETS_ALL_PHASE1: tuple[str, ...] = PLANETS_CLASSIC + PLANETS_NODES + PLANETS_EXTRA

ASPECT_TYPES: tuple[str, ...] = (
    "conjunction", "opposition", "trine", "square", "sextile", "quincunx",
)

ELEMENTS: tuple[str, ...] = ("fire", "earth", "air", "water")
MODALITIES: tuple[str, ...] = ("cardinal", "fixed", "mutable")

SIGN_ELEMENT: dict[str, str] = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

SIGN_MODALITY: dict[str, str] = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}

# Dignity: planet ↔ sign relationships.
#   "rulership"  — planet rules this sign (max strength)
#   "exaltation" — planet is exalted (strong)
#   "detriment"  — opposite of rulership (weak)
#   "fall"       — opposite of exaltation (weakest)
PLANET_DIGNITY: dict[str, dict[str, str]] = {
    "Sun":     {"rulership": "Leo",        "exaltation": "Aries",    "detriment": "Aquarius",  "fall": "Libra"},
    "Moon":    {"rulership": "Cancer",     "exaltation": "Taurus",   "detriment": "Capricorn", "fall": "Scorpio"},
    "Mercury": {"rulership": "Gemini",     "exaltation": "Virgo",    "detriment": "Sagittarius", "fall": "Pisces"},
    "Venus":   {"rulership": "Taurus",     "exaltation": "Pisces",   "detriment": "Scorpio",   "fall": "Virgo"},
    "Mars":    {"rulership": "Aries",      "exaltation": "Capricorn","detriment": "Libra",     "fall": "Cancer"},
    "Jupiter": {"rulership": "Sagittarius","exaltation": "Cancer",   "detriment": "Gemini",    "fall": "Capricorn"},
    "Saturn":  {"rulership": "Capricorn",  "exaltation": "Libra",    "detriment": "Cancer",    "fall": "Aries"},
    "Uranus":  {"rulership": "Aquarius",   "exaltation": "Scorpio",  "detriment": "Leo",       "fall": "Taurus"},
    "Neptune": {"rulership": "Pisces",     "exaltation": "Leo",      "detriment": "Virgo",     "fall": "Aquarius"},
    "Pluto":   {"rulership": "Scorpio",    "exaltation": "Aries",    "detriment": "Taurus",    "fall": "Libra"},
}

# Dignity score multiplier applied to a planet's effective strength.
DIGNITY_SCORE: dict[str, float] = {
    "rulership": 1.5,
    "exaltation": 1.3,
    "neutral": 1.0,
    "detriment": 0.7,
    "fall": 0.5,
}


# ---- Dataclasses ----------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PlanetPosition:
    """A single celestial body's position on the ecliptic."""

    name: str               # Canonical name from PLANETS_ALL_PHASE1
    longitude: float        # 0–360 absolute ecliptic longitude
    latitude: float         # Ecliptic latitude (often ~0 for inner planets)
    sign: str               # One of SIGNS
    sign_degree: float      # 0–30 within the sign
    house: int              # 1–12 (Placidus by default)
    is_retrograde: bool
    speed: float            # Deg/day; negative = retrograde motion


@dataclass(frozen=True, slots=True)
class Aspect:
    """An angular relationship between two bodies."""

    planet1: str
    planet2: str
    aspect_type: str        # One of ASPECT_TYPES
    angle: float            # Actual separation, 0–180
    orb: float              # Deviation from exact aspect (absolute value)
    is_applying: bool       # True = tightening, False = separating


@dataclass(frozen=True, slots=True)
class NatalChart:
    """Full natal chart data returned by IAstroEngine.calculate_natal_chart()."""

    birth_datetime: datetime
    latitude: float
    longitude: float
    timezone: str
    planets: tuple[PlanetPosition, ...]
    houses: tuple[float, ...]           # 12 cusp longitudes
    aspects: tuple[Aspect, ...]
    ascendant: float
    midheaven: float
    element_balance: dict[str, float]   # Shares sum to 1.0
    modality_balance: dict[str, float]  # Shares sum to 1.0

    def planet(self, name: str) -> PlanetPosition | None:
        """Find a planet by canonical name, or return None."""
        for p in self.planets:
            if p.name == name:
                return p
        return None

    def aspects_for(self, planet_name: str) -> tuple[Aspect, ...]:
        """All aspects touching the given planet."""
        return tuple(a for a in self.aspects if planet_name in (a.planet1, a.planet2))


@dataclass(frozen=True, slots=True)
class TransitSnapshot:
    """State of transiting bodies against a natal chart at a specific instant."""

    timestamp: datetime
    transiting_planets: tuple[PlanetPosition, ...]
    active_transits: tuple[Aspect, ...]   # transit body → natal body
    moon_phase: str                       # "new" | "waxing" | "full" | "waning"
    retrograde_planets: tuple[str, ...]
