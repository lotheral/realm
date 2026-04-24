"""Default CulturalModifier implementation.

Combines Hofstede, religion, and regional modifier layers; blends the result
with the natal TraitVector using `blend_ratio` from astrology.yaml.
"""

from __future__ import annotations

from realm.core.config import load_astrology_config
from realm.demographics.country_data import get_hofstede
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector

from .hofstede import hofstede_to_modifiers
from .interfaces import ICulturalModifier
from .regional_values import region_to_modifiers
from .religion_worldview import religion_to_modifiers


def compose_modifiers(profile: DemographicProfile) -> dict[str, float]:
    """Sum all cultural modifier contributions for a profile."""
    hof_scores = get_hofstede(profile.country)
    m = hofstede_to_modifiers(hof_scores)
    for trait, delta in religion_to_modifiers(profile.primary_religion).items():
        m[trait] = m.get(trait, 0.0) + delta
    for trait, delta in region_to_modifiers(profile.region).items():
        m[trait] = m.get(trait, 0.0) + delta
    return m


class CulturalModifier(ICulturalModifier):
    def __init__(self, blend_ratio: float | None = None) -> None:
        if blend_ratio is None:
            cfg = load_astrology_config()
            blend_ratio = float(
                cfg.get("astrology", {})
                   .get("cultural_modifier", {})
                   .get("blend_ratio", 0.3)
            )
        self._blend = max(0.0, min(1.0, blend_ratio))

    def apply(self, traits: TraitVector, profile: DemographicProfile) -> TraitVector:
        modifiers = compose_modifiers(profile)
        if self._blend <= 0.0 or not modifiers:
            return traits
        scaled = {k: v * self._blend for k, v in modifiers.items()}
        return traits.apply_modifier(scaled)
