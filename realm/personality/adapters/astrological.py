"""AstrologicalAdapter — wraps an IPersonalityEmbedder for NatalChart input."""

from __future__ import annotations

from typing import Any

from realm.core.exceptions import PersonalityEmbeddingError
from realm.core.types import NatalChart
from realm.personality.embedder import get_personality_embedder
from realm.personality.interfaces import IPersonalityEmbedder
from realm.personality.trait_vector import TraitVector

from .interfaces import IInputAdapter


class AstrologicalAdapter(IInputAdapter):
    """Pass-through adapter that delegates to an IPersonalityEmbedder.

    The wrapped embedder can be rule-based, LLM, or hybrid — decided by the
    realm.personality.mode config key via get_personality_embedder().
    """

    def __init__(self, embedder: IPersonalityEmbedder | None = None) -> None:
        self._embedder = embedder or get_personality_embedder()

    def build(self, input_data: Any) -> TraitVector:
        if not isinstance(input_data, NatalChart):
            raise PersonalityEmbeddingError(
                f"AstrologicalAdapter expects NatalChart, got {type(input_data).__name__}",
            )
        return self._embedder.embed(input_data)

    @property
    def adapter_type(self) -> str:
        return "astrological"

    @property
    def embedder_mode(self) -> str:
        """Expose the wrapped embedder's mode for diagnostics."""
        return self._embedder.mode
