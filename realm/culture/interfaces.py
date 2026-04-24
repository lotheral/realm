"""CulturalModifier interface.

Takes a TraitVector (natal-derived) and a DemographicProfile, returns a new
TraitVector with cultural modifiers applied. The shift is blended with
`blend_ratio` from config (default 0.3) so natal signal remains dominant but
culture nudges realistic directions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector


class ICulturalModifier(ABC):
    @abstractmethod
    def apply(self, traits: TraitVector, profile: DemographicProfile) -> TraitVector:
        """Return a new TraitVector with cultural modifiers blended in."""
