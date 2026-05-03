"""Tests for prediction-category routing (Sprint 11)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from realm.llm.interfaces import ILLMBackend, LLMResponse
from realm.output.category_router import (
    CategoryRouter,
    _validate_categories,
    default_router,
    load_categories,
)

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "prediction_categories.json"


class TestSchemaValidation:
    def test_loads_default_config_cleanly(self):
        cats = load_categories()
        assert len(cats) == 9
        assert cats[-1]["id"] == "balanced"

    def test_rejects_unknown_trait_name(self):
        bad = {
            "categories": [
                {
                    "id": "x",
                    "label": "x",
                    "trait_weights": {
                        "primary": ["nonexistent_trait"],
                        "secondary": [],
                        "suppressed": [],
                    },
                    "keywords": ["x"],
                    "default_horizon_ticks": 10,
                    "subcategories": [],
                },
                {
                    "id": "balanced",
                    "label": "balanced",
                    "trait_weights": {"primary": [], "secondary": [], "suppressed": []},
                    "keywords": [],
                    "default_horizon_ticks": 10,
                    "subcategories": [],
                },
            ]
        }
        with pytest.raises(ValueError, match="unknown trait"):
            _validate_categories(bad)

    def test_requires_primary_trait_for_non_balanced(self):
        bad = {
            "categories": [
                {
                    "id": "x",
                    "label": "x",
                    "trait_weights": {"primary": [], "secondary": ["openness"], "suppressed": []},
                    "keywords": ["x"],
                    "default_horizon_ticks": 10,
                    "subcategories": [],
                },
                {
                    "id": "balanced",
                    "label": "balanced",
                    "trait_weights": {"primary": [], "secondary": [], "suppressed": []},
                    "keywords": [],
                    "default_horizon_ticks": 10,
                    "subcategories": [],
                },
            ]
        }
        with pytest.raises(ValueError, match="at least one primary"):
            _validate_categories(bad)

    def test_requires_balanced_to_be_last(self):
        bad = {
            "categories": [
                {
                    "id": "balanced",
                    "label": "balanced",
                    "trait_weights": {"primary": [], "secondary": [], "suppressed": []},
                    "keywords": [],
                    "default_horizon_ticks": 10,
                    "subcategories": [],
                },
                {
                    "id": "politics",
                    "label": "p",
                    "trait_weights": {"primary": ["openness"], "secondary": [], "suppressed": []},
                    "keywords": ["election"],
                    "default_horizon_ticks": 30,
                    "subcategories": [],
                },
            ]
        }
        with pytest.raises(ValueError, match="last category"):
            _validate_categories(bad)


class TestKeywordRouting:
    def setup_method(self):
        self.router = default_router()

    def test_politics_question(self):
        m = self.router.route("Will Trump be re-elected in 2028?")
        assert m.category_id == "politics"
        assert "elected" in m.matched_keywords
        assert m.fallback is False
        assert "political_spectrum" in m.primary_traits

    def test_economics_question(self):
        m = self.router.route("Will the Fed cut interest rates in June?")
        assert m.category_id == "economics"

    def test_crypto_question(self):
        m = self.router.route("Will BTC hit 200K this year?")
        assert m.category_id == "crypto"

    def test_sports_question(self):
        m = self.router.route("Will the Lakers win the finals this season?")
        assert m.category_id == "sports"

    def test_markets_question(self):
        m = self.router.route("Will gold break 3000 dollars?")
        assert m.category_id == "markets"

    def test_culture_question(self):
        m = self.router.route("Will Oscars give best picture to Oppenheimer?")
        assert m.category_id == "culture"

    def test_science_question(self):
        m = self.router.route("Will SpaceX land on Mars in 2030?")
        assert m.category_id == "science"

    def test_geopolitics_question(self):
        m = self.router.route("Will Russia and Ukraine reach a ceasefire by 2027?")
        assert m.category_id == "geopolitics"

    def test_no_match_falls_back_to_balanced(self):
        m = self.router.route("What is the meaning of life?")
        assert m.category_id == "balanced"
        assert m.fallback is True
        assert m.primary_traits == ()

    def test_empty_question_falls_back(self):
        m = self.router.route("   ")
        assert m.category_id == "balanced"
        assert m.fallback is True

    def test_subcategory_detection_when_keyword_matches(self):
        m = self.router.route("Will SpaceX land on Mars in space in 2030?")
        assert m.category_id == "science"
        assert m.subcategory == "space"

    def test_case_insensitive_match(self):
        m = self.router.route("WILL NATO ADD SWEDEN IN 2027?")
        assert m.category_id == "geopolitics"

    def test_word_boundary_avoids_false_positive(self):
        # 'un' is a geopolitics keyword (united nations); must NOT match inside
        # 'country' / 'fund' / etc. because of word boundaries.
        m = self.router.route("Will the country grow in fund size?")
        assert m.category_id != "geopolitics" or "un" not in m.matched_keywords

    def test_plural_form_matches(self):
        # 'oscar' should match 'oscars' via the trailing-s heuristic.
        m = self.router.route("Will the Oscars award an indie film in 2027?")
        assert m.category_id == "culture"


class _ScriptedBackend(ILLMBackend):
    """Hermetic stub backend that returns a pre-set JSON dict."""

    def __init__(self, response: Mapping[str, Any]):
        self._response = response
        self.calls = 0

    @property
    def backend_name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return "scripted-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls += 1
        return LLMResponse(
            content=json.dumps(self._response),
            model=self.model,
            cached=False,
        )


class TestLLMFirst:
    """Sprint 17: LLM is now the PRIMARY router (when wired). Keyword
    matching is the fallback when LLM is unavailable / errors / returns
    low confidence / returns an unknown category id."""

    def test_llm_used_when_backend_provided_even_with_strong_keyword_match(self):
        """Sprint 17 inversion: previously this test asserted LLM was NOT
        called because the keyword match for 'Lakers championship' was
        strong. Under LLM-first, the LLM is consulted first regardless
        of keyword strength — its answer is the routing decision."""
        backend = _ScriptedBackend({"category": "politics", "confidence": 0.9})
        router = CategoryRouter(llm_backend=backend)
        m = router.route("Will the Lakers win the championship final this season?")
        assert backend.calls == 1
        assert m.llm_used is True
        assert m.category_id == "politics"  # LLM's choice wins

    def test_ambiguous_no_match_uses_llm_when_provided(self):
        backend = _ScriptedBackend({"category": "politics", "confidence": 0.8})
        router = CategoryRouter(llm_backend=backend)
        m = router.route("zztop nothing matches this")
        assert m.llm_used is True
        assert m.category_id == "politics"
        assert backend.calls == 1

    def test_falls_back_to_keyword_when_llm_returns_unknown_id(self):
        """LLM returns a category id that doesn't exist in config →
        keyword fallback kicks in. For a question with no keyword hits
        either, the keyword path itself returns the balanced fallback."""
        backend = _ScriptedBackend({"category": "garbage_id", "confidence": 0.9})
        router = CategoryRouter(llm_backend=backend)
        m = router.route("zztop nothing matches this")
        assert m.fallback is True
        assert m.category_id == "balanced"
        assert backend.calls == 1  # LLM was called, keyword fallback then ran

    def test_low_llm_confidence_falls_back_to_keyword(self):
        """LLM returns a valid category but with confidence < 0.5 →
        keyword path is consulted; for a clear-keyword question the
        keyword choice wins."""
        backend = _ScriptedBackend({"category": "politics", "confidence": 0.3})
        router = CategoryRouter(llm_backend=backend)
        m = router.route("Will the Lakers win the championship final this season?")
        assert backend.calls == 1
        assert m.category_id == "sports"   # keyword fallback caught the strong hit
        assert m.llm_used is False


class TestCategoryMatchShape:
    def test_match_has_primary_traits_for_politics(self):
        m = default_router().route("Will Trump be re-elected in 2028?")
        assert "political_spectrum" in m.primary_traits
        assert "authority_compliance" in m.primary_traits

    def test_match_carries_default_horizon(self):
        m = default_router().route("Will the Fed cut interest rates in June?")
        assert m.default_horizon_ticks == 30
