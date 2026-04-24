"""IInputAdapter — type-agnostic abstraction above IPersonalityEmbedder."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from realm.personality.trait_vector import TraitVector


class IInputAdapter(ABC):
    """Transform domain-specific input data into a 24-trait TraitVector.

    Input type is adapter-dependent (NatalChart, Mapping of Big Five scores,
    DemographicProfile, etc.). The adapter is responsible for validating
    its input; callers must route the right input type to the right adapter.
    """

    @abstractmethod
    def build(self, input_data: Any) -> TraitVector:
        """Transform input_data into a TraitVector.

        Raises:
            PersonalityEmbeddingError: input is the wrong type or malformed.
        """

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """'astrological' | 'big_five' | 'demographic'."""

    @property
    def applies_cultural_modifier(self) -> bool:
        """Whether AgentFactory should apply CulturalModifier after this adapter.

        Default True. DemographicAdapter overrides to False because Hofstede
        is already its primary input — applying CulturalModifier on top would
        double-count the same cultural signal.
        """
        return True
