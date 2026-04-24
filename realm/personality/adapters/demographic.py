"""DemographicAdapter — Hofstede + religion + region as PRIMARY trait source.

Differs from CulturalModifier (which applies demographic signal as a small
additive overlay at blend_ratio=0.3). This adapter uses the same
compose_modifiers() result but at full magnitude, treating demographic data
as the primary signal rather than a secondary nudge. Consequently, AgentFactory
does NOT apply CulturalModifier after this adapter — doing so would
double-count Hofstede.
"""

from __future__ import annotations

from typing import Any

from realm.core.exceptions import PersonalityEmbeddingError
from realm.culture.modifier import compose_modifiers
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector

from .interfaces import IInputAdapter


class DemographicAdapter(IInputAdapter):
    """Build a TraitVector from a DemographicProfile alone."""

    def build(self, input_data: Any) -> TraitVector:
        if not isinstance(input_data, DemographicProfile):
            raise PersonalityEmbeddingError(
                f"DemographicAdapter expects DemographicProfile, got {type(input_data).__name__}",
            )
        # Start at neutral 0.5 and apply compose_modifiers at FULL weight.
        # TraitVector.from_dict clamps to [0, 1].
        neutral = dict.fromkeys(TraitVector.trait_names(), 0.5)
        deltas = compose_modifiers(input_data)
        for trait, delta in deltas.items():
            if trait in neutral:
                neutral[trait] += float(delta)
        return TraitVector.from_dict(neutral)

    @property
    def adapter_type(self) -> str:
        return "demographic"

    @property
    def applies_cultural_modifier(self) -> bool:
        # Hofstede is the primary signal here; applying CulturalModifier
        # after would re-add the same delta at blend_ratio * 0.3.
        return False
