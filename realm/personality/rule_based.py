"""Rule-based PersonalityEmbedder (Mode A).

Uses deterministic lookup tables:
    planet_trait_map   — each planet's base influence per trait
    sign_modifiers     — sign-specific trait shifts
    aspect_weights     — aspect amplification + planet relative weights
    dignity_analyzer   — dignity-based strength per planet

Algorithm per trait T:

    score(T) = 0.5 + Σ_planet  scale · [base(P,T) + sign_shift(P.sign,T)]
                             · strength(P)
                             · planet_weight(P)
                             · aspect_multiplier(P, chart.aspects)

    final(T) = clamp(score(T), 0, 1)

`scale` (DAMPENING) keeps the dynamic range reasonable so that no single planet
can push a trait from 0.5 to the extreme; luminary contributions typically land
in the ±0.15 range.
"""

from __future__ import annotations

from collections.abc import Mapping

from realm.astro.dignity_analyzer import planet_strength
from realm.core.config import load_astrology_config
from realm.core.logging import get_logger
from realm.core.types import NatalChart

from .aspect_modifiers import planet_aspect_multiplier
from .interfaces import IPersonalityEmbedder
from .planet_traits import load_aspect_weights, load_planet_trait_map, load_sign_modifiers
from .trait_vector import TraitVector

logger = get_logger(__name__)

DAMPENING_FALLBACK: float = 0.40
MAX_ORB_FOR_TIGHTNESS: float = 8.0


def _load_dampening_default() -> float:
    """Read dampening from astrology.yaml, fall back to the module default."""
    try:
        cfg = load_astrology_config()
        return float(
            cfg.get("astrology", {})
               .get("rule_based_embedder", {})
               .get("dampening", DAMPENING_FALLBACK),
        )
    except Exception:
        return DAMPENING_FALLBACK


class RuleBasedEmbedder(IPersonalityEmbedder):
    """Deterministic, table-driven natal→TraitVector mapping."""

    def __init__(
        self,
        planet_trait_map: Mapping[str, Mapping[str, float]] | None = None,
        sign_modifiers: Mapping[str, Mapping[str, float]] | None = None,
        aspect_weights: Mapping[str, float] | None = None,
        planet_weights: Mapping[str, float] | None = None,
        dampening: float | None = None,
    ) -> None:
        if dampening is None:
            dampening = _load_dampening_default()
        if aspect_weights is None or planet_weights is None:
            aw, pw = load_aspect_weights()
            aspect_weights = aspect_weights if aspect_weights is not None else aw
            planet_weights = planet_weights if planet_weights is not None else pw
        self._planet_trait_map = (
            load_planet_trait_map() if planet_trait_map is None else planet_trait_map
        )
        self._sign_modifiers = (
            load_sign_modifiers() if sign_modifiers is None else sign_modifiers
        )
        self._aspect_weights = aspect_weights
        self._planet_weights = planet_weights
        self._dampening = dampening

    @property
    def mode(self) -> str:
        return "rule_based"

    def embed(self, chart: NatalChart) -> TraitVector:
        scores: dict[str, float] = dict.fromkeys(TraitVector.trait_names(), 0.5)

        for p in chart.planets:
            trait_deltas = self._planet_trait_map.get(p.name)
            if not trait_deltas:
                continue

            strength = planet_strength(p)
            weight = self._planet_weights.get(p.name, 0.3)
            sign_shifts = self._sign_modifiers.get(p.sign, {})
            aspect_mult = planet_aspect_multiplier(
                p.name, chart.aspects, self._aspect_weights, MAX_ORB_FOR_TIGHTNESS,
            )

            for trait, base_delta in trait_deltas.items():
                if trait not in scores:
                    logger.debug("Unknown trait %r in planet_trait_map; skipping", trait)
                    continue
                sign_shift = sign_shifts.get(trait, 0.0)
                contribution = (
                    (base_delta + sign_shift)
                    * strength
                    * weight
                    * aspect_mult
                    * self._dampening
                )
                scores[trait] += contribution

        # Clamp via TraitVector.from_dict
        return TraitVector.from_dict(scores)
