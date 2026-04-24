"""Transit-driven trait shifts.

Decoupled design (decision #5):
  - Once per tick: compute transit-planet geocentric positions (one ephemeris call).
  - Per agent:    pure-Python aspect check transit_positions vs agent.natal_chart.planets.
                  Apply temporary trait modifiers from active transits.

Result: O(tick) expensive ephemeris calls, O(tick × agents) cheap aspect checks,
instead of O(tick × agents) expensive calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from realm.astro.aspect_calculator import find_transit_aspects
from realm.astro.interfaces import IAstroEngine
from realm.core.config import load_astrology_config
from realm.core.logging import get_logger
from realm.core.types import NatalChart, PlanetPosition
from realm.personality.planet_traits import load_aspect_weights, load_planet_trait_map
from realm.personality.trait_vector import TraitVector

logger = get_logger(__name__)


# How a transit aspect direction modulates the natal planet's trait influence.
# Harmonious aspects reinforce the natal expression; challenging aspects invert
# partially (creating tension that expresses as opposite-leaning behaviour).
_TRANSIT_DIRECTION: Mapping[str, float] = {
    "conjunction": 1.0,
    "trine": 1.0,
    "sextile": 0.7,
    "square": -0.5,
    "opposition": -0.4,
    "quincunx": 0.2,
}

# Transit-weighted per planet (astrology.yaml default). Slower planets hit harder
# because they hold an aspect longer — their influence accumulates in the agent's
# lived time.
_DEFAULT_TRANSIT_WEIGHTS: Mapping[str, float] = {
    "sun": 0.50, "moon": 0.30, "mercury": 0.40, "venus": 0.45, "mars": 0.60,
    "jupiter": 0.75, "saturn": 0.85, "uranus": 0.90, "neptune": 0.95, "pluto": 1.00,
}

_DEFAULT_TRANSIT_ORBS: Mapping[str, float] = {
    "conjunction": 3.0, "opposition": 3.0, "trine": 2.5,
    "square": 2.5, "sextile": 2.0, "quincunx": 1.5,
}

# Global dampening so transit shifts stay subtle vs. baseline traits.
DAMPENING: float = 0.06


@dataclass
class TransitModulator:
    """Per-tick transit cache + per-agent modifier computation."""

    astro_engine: IAstroEngine
    transit_weights: Mapping[str, float]
    transit_orbs: Mapping[str, float]
    _cache_time: datetime | None = None
    _cached_positions: tuple[PlanetPosition, ...] | None = None

    @classmethod
    def from_config(cls, astro_engine: IAstroEngine) -> TransitModulator:
        cfg = load_astrology_config().get("astrology", {})
        weights = {
            k.lower(): float(v)
            for k, v in cfg.get("transit_weights", _DEFAULT_TRANSIT_WEIGHTS).items()
        }
        orbs = {
            k: float(v) for k, v in cfg.get("transit_orbs", _DEFAULT_TRANSIT_ORBS).items()
        }
        return cls(
            astro_engine=astro_engine,
            transit_weights=weights,
            transit_orbs=orbs,
        )

    def transit_positions(self, sim_time: datetime) -> tuple[PlanetPosition, ...]:
        """Cached per-tick transit ephemeris. Geocentric — location-independent."""
        if self._cache_time == sim_time and self._cached_positions is not None:
            return self._cached_positions

        # Build a minimal chart at (0,0, UTC) just for planet longitudes.
        chart = self.astro_engine.calculate_natal_chart(
            birth_dt=sim_time,
            latitude=0.0,
            longitude=0.0,
            timezone="UTC",
        )
        self._cache_time = sim_time
        self._cached_positions = chart.planets
        return chart.planets

    def compute_modifiers(
        self, natal: NatalChart, sim_time: datetime,
    ) -> dict[str, float]:
        """Additive trait modifiers from active transits on this natal chart.

        Values stay small (typically ±0.05 per trait) — they're momentary
        behaviour nudges, not permanent changes.
        """
        transits = self.transit_positions(sim_time)
        active = find_transit_aspects(transits, natal.planets, self.transit_orbs)
        if not active:
            return {}

        planet_trait_map = load_planet_trait_map()
        aspect_weights, _planet_weights = load_aspect_weights()

        modifiers: dict[str, float] = {}
        for a in active:
            direction = _TRANSIT_DIRECTION.get(a.aspect_type, 0.3)
            transit_weight = self.transit_weights.get(a.planet1.lower(), 0.3)
            aspect_weight = float(aspect_weights.get(a.aspect_type, 0.0))
            max_orb = float(self.transit_orbs.get(a.aspect_type, 3.0))
            orb_tightness = max(0.0, 1.0 - a.orb / max_orb)

            natal_mapping = planet_trait_map.get(a.planet2, {})
            scale = direction * transit_weight * aspect_weight * orb_tightness * DAMPENING
            for trait, base_delta in natal_mapping.items():
                modifiers[trait] = modifiers.get(trait, 0.0) + base_delta * scale

        return modifiers

    def apply_to(self, natal_traits: TraitVector, natal: NatalChart,
                 sim_time: datetime) -> TraitVector:
        """Return a new TraitVector with transit modifiers applied."""
        return natal_traits.apply_modifier(self.compute_modifiers(natal, sim_time))

    def reset_cache(self) -> None:
        """Call this if the underlying astro engine or config changes."""
        self._cache_time = None
        self._cached_positions = None


def utcnow() -> datetime:
    """Helper: tz-aware current UTC datetime."""
    return datetime.now(UTC)
