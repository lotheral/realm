"""PersonalityEngine interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from realm.core.types import NatalChart

from .trait_vector import TraitVector


class IPersonalityEmbedder(ABC):
    """Transforms a natal chart into a 24-dimensional TraitVector."""

    @abstractmethod
    def embed(self, chart: NatalChart) -> TraitVector:
        ...

    @property
    @abstractmethod
    def mode(self) -> str:
        """Embedding mode: 'rule_based' | 'llm' | 'hybrid'."""
