"""Collective astrological climate layer (Phase 5).

Builds on TransitModulator. Where TransitModulator computes PER-AGENT aspect
effects (natal chart vs transits), ClimateEngine computes GLOBAL effects that
apply to every agent uniformly:

    - Outer-planet sign eras (Pluto, Neptune, Uranus, …)
      e.g. "Pluto in Capricorn" dominates 2008–2024 (institutional / debt era)
    - Moon phase (new / waxing / full / waning)
    - Eclipse detection (solar / lunar) — Sun-Moon near the lunar nodes
    - Retrograde global effects (Mercury R, Venus R, …)

Final trait composition per tick (in SimulationEngine):

    effective_traits = agent.traits                 # natal + culture (static)
                          .apply_modifier(climate)  # global, per-tick
                          .apply_modifier(individual_transits)  # per-agent, per-tick
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from realm.core.logging import get_logger
from realm.core.types import PlanetPosition
from realm.simulation.transit_modulator import TransitModulator

logger = get_logger(__name__)


# ---- Outer-planet sign era mappings --------------------------------------
# Value ranges: per-sign delta in [-0.08, +0.08]. ClimateEngine further scales
# these by (planet_weight × global dampening) so the final per-tick shift stays
# under ~0.10 per trait.

_PLUTO_SIGN: dict[str, dict[str, float]] = {
    "Aries":       {"risk_appetite": 0.06, "impulsivity": 0.05, "contrarian_tendency": 0.04},
    "Taurus":      {"loss_aversion": 0.06, "patience": 0.04, "financial_optimism": -0.03},
    "Gemini":      {"information_sharing": 0.05, "communication_assertiveness": 0.04},
    "Cancer":      {"empathy": 0.05, "herd_susceptibility": 0.04, "individualism": -0.03},
    "Leo":         {"social_dominance": 0.06, "extraversion": 0.04, "individualism": 0.04},
    "Virgo":       {"analytical_depth": 0.05, "conscientiousness": 0.04},
    "Libra":       {"agreeableness": 0.05, "authority_compliance": 0.03},
    "Scorpio":     {"social_dominance": 0.05, "risk_appetite": 0.04, "neuroticism": 0.03},
    "Sagittarius": {"openness": 0.05, "financial_optimism": 0.04, "spirituality": 0.03},
    "Capricorn":   {"authority_compliance": 0.06, "loss_aversion": 0.05,
                    "contrarian_tendency": -0.04, "conscientiousness": 0.03},
    "Aquarius":    {"contrarian_tendency": 0.06, "openness": 0.05,
                    "authority_compliance": -0.05, "tradition_vs_progress": 0.04},
    "Pisces":      {"spirituality": 0.05, "herd_susceptibility": 0.04,
                    "analytical_depth": -0.03, "empathy": 0.03},
}

_NEPTUNE_SIGN: dict[str, dict[str, float]] = {
    "Aries":       {"risk_appetite": 0.03, "analytical_depth": -0.02},
    "Taurus":      {"financial_optimism": 0.02, "patience": 0.02},
    "Gemini":      {"information_sharing": 0.03, "herd_susceptibility": 0.02},
    "Cancer":      {"empathy": 0.04, "herd_susceptibility": 0.03},
    "Leo":         {"spirituality": 0.03, "extraversion": 0.02},
    "Virgo":       {"spirituality": -0.02, "analytical_depth": 0.02},
    "Libra":       {"agreeableness": 0.03, "spirituality": 0.02},
    "Scorpio":     {"spirituality": 0.03, "neuroticism": 0.03},
    "Sagittarius": {"openness": 0.04, "spirituality": 0.04},
    "Capricorn":   {"spirituality": -0.03, "conscientiousness": 0.02},
    "Aquarius":    {"spirituality": 0.03, "openness": 0.03, "contrarian_tendency": 0.02},
    "Pisces":      {"spirituality": 0.05, "empathy": 0.04, "analytical_depth": -0.04,
                    "herd_susceptibility": 0.03},
}

_URANUS_SIGN: dict[str, dict[str, float]] = {
    "Aries":       {"contrarian_tendency": 0.04, "risk_appetite": 0.03, "impulsivity": 0.03},
    "Taurus":      {"contrarian_tendency": 0.03, "financial_optimism": -0.02,
                    "tradition_vs_progress": 0.03},
    "Gemini":      {"openness": 0.04, "information_sharing": 0.03},
    "Cancer":      {"empathy": 0.02, "contrarian_tendency": 0.02},
    "Leo":         {"social_dominance": 0.03, "individualism": 0.03},
    "Virgo":       {"analytical_depth": 0.03, "contrarian_tendency": 0.02},
    "Libra":       {"agreeableness": 0.02, "contrarian_tendency": 0.02},
    "Scorpio":     {"contrarian_tendency": 0.04, "risk_appetite": 0.02},
    "Sagittarius": {"openness": 0.04, "tradition_vs_progress": 0.03},
    "Capricorn":   {"contrarian_tendency": 0.03, "authority_compliance": -0.02,
                    "tradition_vs_progress": 0.02},
    "Aquarius":    {"contrarian_tendency": 0.05, "openness": 0.04,
                    "tradition_vs_progress": 0.04, "authority_compliance": -0.03},
    "Pisces":      {"spirituality": 0.03, "herd_susceptibility": 0.02},
}

_SATURN_SIGN: dict[str, dict[str, float]] = {
    "Aries":       {"conscientiousness": 0.02, "risk_appetite": -0.02},
    "Taurus":      {"loss_aversion": 0.03, "patience": 0.03},
    "Gemini":      {"analytical_depth": 0.02, "communication_assertiveness": -0.02},
    "Cancer":      {"loss_aversion": 0.03, "herd_susceptibility": 0.02},
    "Leo":         {"authority_compliance": 0.02, "social_dominance": 0.02},
    "Virgo":       {"conscientiousness": 0.03, "analytical_depth": 0.02},
    "Libra":       {"agreeableness": 0.03, "authority_compliance": 0.02},
    "Scorpio":     {"neuroticism": 0.02, "loss_aversion": 0.02},
    "Sagittarius": {"tradition_vs_progress": -0.02, "conscientiousness": 0.02},
    "Capricorn":   {"conscientiousness": 0.04, "authority_compliance": 0.03,
                    "loss_aversion": 0.03},
    "Aquarius":    {"authority_compliance": 0.02, "contrarian_tendency": 0.02},
    "Pisces":      {"spirituality": 0.02, "herd_susceptibility": 0.02},
}

_JUPITER_SIGN: dict[str, dict[str, float]] = {
    "Aries":       {"risk_appetite": 0.03, "extraversion": 0.02},
    "Taurus":      {"financial_optimism": 0.03, "patience": 0.02},
    "Gemini":      {"information_sharing": 0.03, "openness": 0.02},
    "Cancer":      {"empathy": 0.03, "financial_optimism": 0.03},
    "Leo":         {"extraversion": 0.03, "social_dominance": 0.03},
    "Virgo":       {"conscientiousness": 0.02, "analytical_depth": 0.02},
    "Libra":       {"agreeableness": 0.03, "persuasion_skill": 0.02},
    "Scorpio":     {"risk_appetite": 0.02, "persuasion_skill": 0.02},
    "Sagittarius": {"openness": 0.04, "financial_optimism": 0.03, "spirituality": 0.03},
    "Capricorn":   {"conscientiousness": 0.02, "financial_optimism": -0.02},
    "Aquarius":    {"openness": 0.03, "contrarian_tendency": 0.02},
    "Pisces":      {"spirituality": 0.03, "empathy": 0.03},
}

_OUTER_PLANET_MAPS: dict[str, dict[str, dict[str, float]]] = {
    "Pluto":   _PLUTO_SIGN,
    "Neptune": _NEPTUNE_SIGN,
    "Uranus":  _URANUS_SIGN,
    "Saturn":  _SATURN_SIGN,
    "Jupiter": _JUPITER_SIGN,
}

# Per-planet weight: slower movers stamp the era more strongly.
_OUTER_PLANET_WEIGHT: Mapping[str, float] = {
    "Pluto":   1.00,
    "Neptune": 0.80,
    "Uranus":  0.70,
    "Saturn":  0.45,
    "Jupiter": 0.25,
}


# ---- Moon phase effects ---------------------------------------------------

_MOON_PHASE_MOD: Mapping[str, dict[str, float]] = {
    "new":    {"extraversion": -0.02, "analytical_depth": 0.02, "introspection_proxy": 0.0},
    "waxing": {"extraversion": 0.02, "risk_appetite": 0.015, "financial_optimism": 0.01},
    "full":   {"impulsivity": 0.03, "communication_assertiveness": 0.02,
               "neuroticism": 0.02, "fomo_susceptibility": 0.02},
    "waning": {"patience": 0.02, "loss_aversion": 0.015, "analytical_depth": 0.01},
}


def compute_moon_phase(sun_lon: float, moon_lon: float) -> str:
    diff = (moon_lon - sun_lon) % 360.0
    if diff < 45 or diff >= 315:
        return "new"
    if diff < 135:
        return "waxing"
    if diff < 225:
        return "full"
    return "waning"


# ---- Eclipse detection ----------------------------------------------------

_SOLAR_ECLIPSE_ORB: float = 18.0   # Sun–Moon conjunction within this of a node
_LUNAR_ECLIPSE_ORB: float = 12.0   # Sun–Moon opposition within this of a node

_ECLIPSE_MOD: Mapping[str, dict[str, float]] = {
    "solar": {"neuroticism": 0.04, "herd_susceptibility": 0.03, "fomo_susceptibility": 0.02},
    "lunar": {"neuroticism": 0.03, "fomo_susceptibility": 0.02, "impulsivity": 0.02},
}


def _angle_diff(a: float, b: float) -> float:
    """Smallest unsigned angular distance on a circle."""
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def detect_eclipse(positions: tuple[PlanetPosition, ...]) -> str | None:
    """Return 'solar' or 'lunar' if an eclipse is active, else None.

    Uses simplified orb thresholds. A rigorous ephemeris test would check the
    Sun-Moon-Earth geometry — for Phase 5 we approximate via angular distance
    to the lunar nodes.
    """
    by_name = {p.name: p for p in positions}
    sun = by_name.get("Sun")
    moon = by_name.get("Moon")
    north = by_name.get("North_Node")
    if not (sun and moon and north):
        return None

    sun_moon = _angle_diff(sun.longitude, moon.longitude)
    # Conjunction (near 0°)
    if sun_moon <= _SOLAR_ECLIPSE_ORB:
        mid_lon = (sun.longitude + moon.longitude) / 2
        if _angle_diff(mid_lon, north.longitude) <= _SOLAR_ECLIPSE_ORB:
            return "solar"
    # Opposition (near 180°)
    if abs(sun_moon - 180.0) <= _LUNAR_ECLIPSE_ORB:
        # Moon near node (lunar eclipse requires Moon-node alignment)
        if _angle_diff(moon.longitude, north.longitude) <= _LUNAR_ECLIPSE_ORB:
            return "lunar"
        south_lon = (north.longitude + 180.0) % 360.0
        if _angle_diff(moon.longitude, south_lon) <= _LUNAR_ECLIPSE_ORB:
            return "lunar"
    return None


# ---- Retrograde effects ---------------------------------------------------

_RETROGRADE_MOD: Mapping[str, dict[str, float]] = {
    "Mercury": {"communication_assertiveness": -0.04, "information_sharing": -0.03,
                "analytical_depth": -0.01},
    "Venus":   {"agreeableness": -0.03, "financial_optimism": -0.02},
    "Mars":    {"risk_appetite": -0.03, "impulsivity": -0.02},
    "Jupiter": {"financial_optimism": -0.02, "openness": -0.01},
    "Saturn":  {"loss_aversion": 0.03, "risk_appetite": -0.02},
    "Uranus":  {"contrarian_tendency": -0.01},
    "Neptune": {"spirituality": -0.01},
    "Pluto":   {"social_dominance": -0.01},
}


# ---- ClimateEngine orchestrator -------------------------------------------

@dataclass
class ClimateEngine:
    """Computes the global collective modifier for a single moment."""

    modulator: TransitModulator
    dampening: float = 0.7           # global scale on all climate contributions
    include_outer_planets: bool = True
    include_moon_phase: bool = True
    include_eclipses: bool = True
    include_retrogrades: bool = True

    def compute(self, sim_time: datetime) -> dict[str, float]:
        """Return the additive trait modifier dict for `sim_time`."""
        positions = self.modulator.transit_positions(sim_time)
        modifiers: dict[str, float] = {}

        if self.include_outer_planets:
            self._add_outer_planet_era(modifiers, positions)
        if self.include_retrogrades:
            self._add_retrograde(modifiers, positions)
        if self.include_moon_phase:
            self._add_moon_phase(modifiers, positions)
        if self.include_eclipses:
            self._add_eclipse(modifiers, positions)

        # Apply global dampening (and drop unknown trait names)
        from realm.personality.trait_vector import TraitVector
        valid = set(TraitVector.trait_names())
        return {k: v * self.dampening for k, v in modifiers.items() if k in valid}

    # ---- helpers ----

    def _add_outer_planet_era(
        self, modifiers: dict[str, float], positions: tuple[PlanetPosition, ...],
    ) -> None:
        for p in positions:
            sign_map = _OUTER_PLANET_MAPS.get(p.name)
            if not sign_map:
                continue
            weight = _OUTER_PLANET_WEIGHT.get(p.name, 0.0)
            sign_effects = sign_map.get(p.sign, {})
            for trait, delta in sign_effects.items():
                modifiers[trait] = modifiers.get(trait, 0.0) + delta * weight

    def _add_retrograde(
        self, modifiers: dict[str, float], positions: tuple[PlanetPosition, ...],
    ) -> None:
        for p in positions:
            if not p.is_retrograde:
                continue
            eff = _RETROGRADE_MOD.get(p.name, {})
            for trait, delta in eff.items():
                modifiers[trait] = modifiers.get(trait, 0.0) + delta

    def _add_moon_phase(
        self, modifiers: dict[str, float], positions: tuple[PlanetPosition, ...],
    ) -> None:
        sun = next((p for p in positions if p.name == "Sun"), None)
        moon = next((p for p in positions if p.name == "Moon"), None)
        if not (sun and moon):
            return
        phase = compute_moon_phase(sun.longitude, moon.longitude)
        for trait, delta in _MOON_PHASE_MOD.get(phase, {}).items():
            modifiers[trait] = modifiers.get(trait, 0.0) + delta

    def _add_eclipse(
        self, modifiers: dict[str, float], positions: tuple[PlanetPosition, ...],
    ) -> None:
        kind = detect_eclipse(positions)
        if kind is None:
            return
        for trait, delta in _ECLIPSE_MOD[kind].items():
            modifiers[trait] = modifiers.get(trait, 0.0) + delta

    # ---- introspection -----------------------------------------------

    def describe(self, sim_time: datetime) -> dict[str, object]:
        """Return a human-readable snapshot of the current climate drivers."""
        positions = self.modulator.transit_positions(sim_time)
        by_name = {p.name: p for p in positions}
        outer = {
            name: (by_name[name].sign, "R" if by_name[name].is_retrograde else "D")
            for name in _OUTER_PLANET_MAPS if name in by_name
        }
        sun = by_name.get("Sun")
        moon = by_name.get("Moon")
        phase = compute_moon_phase(sun.longitude, moon.longitude) if sun and moon else "?"
        retro = [p.name for p in positions if p.is_retrograde]
        eclipse = detect_eclipse(positions)
        return {
            "outer_planets": outer,
            "moon_phase": phase,
            "retrograde": retro,
            "eclipse": eclipse,
        }
