"""Tests for AstrologicalAdapter — pass-through wrapper around IPersonalityEmbedder."""

from __future__ import annotations

import pytest

from realm.astro.fixtures import synthetic_chart
from realm.core.exceptions import PersonalityEmbeddingError
from realm.personality.adapters import AstrologicalAdapter
from realm.personality.rule_based import RuleBasedEmbedder
from realm.personality.trait_vector import TraitVector


class TestAstrologicalAdapter:
    def test_build_returns_trait_vector(self):
        adapter = AstrologicalAdapter(RuleBasedEmbedder())
        tv = adapter.build(synthetic_chart())
        assert isinstance(tv, TraitVector)

    def test_matches_direct_embedder_output(self):
        """Adapter is a pure pass-through; output must equal direct embed()."""
        embedder = RuleBasedEmbedder()
        adapter = AstrologicalAdapter(embedder)
        chart = synthetic_chart()
        direct = embedder.embed(chart)
        wrapped = adapter.build(chart)
        assert direct == wrapped

    def test_adapter_type(self):
        adapter = AstrologicalAdapter(RuleBasedEmbedder())
        assert adapter.adapter_type == "astrological"

    def test_applies_cultural_modifier_true(self):
        adapter = AstrologicalAdapter(RuleBasedEmbedder())
        assert adapter.applies_cultural_modifier is True

    def test_rejects_non_natal_chart_input(self):
        adapter = AstrologicalAdapter(RuleBasedEmbedder())
        with pytest.raises(PersonalityEmbeddingError, match="NatalChart"):
            adapter.build({"openness": 0.7})

    def test_default_embedder_from_config(self):
        """Calling AstrologicalAdapter() with no args resolves via factory."""
        adapter = AstrologicalAdapter()
        tv = adapter.build(synthetic_chart())
        assert isinstance(tv, TraitVector)
        # embedder_mode exposes the wrapped embedder's mode for diagnostics
        assert adapter.embedder_mode in ("rule_based", "llm", "hybrid")
