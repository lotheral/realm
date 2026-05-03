"""Sprint 18 WP3 — multi-category routing tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from realm.llm.interfaces import ILLMBackend, LLMResponse
from realm.output.category_router import (
    CategoryRouter,
    _parse_multi_categories,
    blend_drift_event_weights,
)


class _ScriptedBackend(ILLMBackend):
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
        return LLMResponse(content=json.dumps(self._response), model=self.model)


# ---- _parse_multi_categories ----------------------------------------------


def _by_id_sample() -> dict:
    """Minimal fixture matching what _parse_multi_categories needs."""
    return {
        "geopolitics": {"id": "geopolitics"},
        "economics": {"id": "economics"},
        "markets": {"id": "markets"},
        "crypto": {"id": "crypto"},
    }


def test_parse_multi_categories_single_entry() -> None:
    raw = [{"id": "crypto", "weight": 1.0}]
    result = _parse_multi_categories(raw, _by_id_sample())
    assert result is not None
    primary, secondary = result
    assert primary == "crypto"
    assert secondary == ()


def test_parse_multi_categories_three_way_blend() -> None:
    raw = [
        {"id": "geopolitics", "weight": 0.6},
        {"id": "economics", "weight": 0.25},
        {"id": "markets", "weight": 0.15},
    ]
    result = _parse_multi_categories(raw, _by_id_sample())
    assert result is not None
    primary, secondary = result
    assert primary == "geopolitics"
    assert secondary == (("economics", 0.25), ("markets", 0.15))


def test_parse_multi_categories_sorts_by_weight() -> None:
    """Highest-weight category becomes primary regardless of input order."""
    raw = [
        {"id": "markets", "weight": 0.2},
        {"id": "geopolitics", "weight": 0.5},
        {"id": "economics", "weight": 0.3},
    ]
    result = _parse_multi_categories(raw, _by_id_sample())
    assert result is not None
    primary, secondary = result
    assert primary == "geopolitics"


def test_parse_multi_categories_rejects_unknown_id() -> None:
    raw = [
        {"id": "geopolitics", "weight": 0.7},
        {"id": "fictional", "weight": 0.3},
    ]
    # Filter drops "fictional"; remaining has weight 0.7 → not ~1.0 → reject
    result = _parse_multi_categories(raw, _by_id_sample())
    assert result is None


def test_parse_multi_categories_rejects_bad_weight_sum() -> None:
    raw = [
        {"id": "geopolitics", "weight": 0.4},
        {"id": "economics", "weight": 0.3},
    ]
    # Sum = 0.7, outside ±0.05 of 1.0 → reject
    assert _parse_multi_categories(raw, _by_id_sample()) is None


def test_parse_multi_categories_accepts_within_tolerance() -> None:
    raw = [
        {"id": "geopolitics", "weight": 0.5},
        {"id": "economics", "weight": 0.49},  # sum = 0.99 (within ±0.05)
    ]
    result = _parse_multi_categories(raw, _by_id_sample())
    assert result is not None


# ---- LLM router multi-cat path -------------------------------------------


def test_llm_returns_multi_category_routes_to_primary() -> None:
    """Hormuz-style cross-domain question → LLM returns categories list,
    router picks geopolitics as primary, secondary populated."""
    backend = _ScriptedBackend({
        "categories": [
            {"id": "geopolitics", "weight": 0.6},
            {"id": "economics", "weight": 0.25},
            {"id": "markets", "weight": 0.15},
        ],
        "subcategory": None,
        "confidence": 0.9,
        "reasoning": "Cross-domain shipping/oil/military question",
    })
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will the Strait of Hormuz traffic return to normal?")
    assert m.category_id == "geopolitics"
    assert m.llm_used is True
    assert m.secondary_categories == (("economics", 0.25), ("markets", 0.15))


def test_llm_returns_single_category_legacy_form() -> None:
    """Backward-compat: old single-category JSON form still works."""
    backend = _ScriptedBackend({"category": "crypto", "confidence": 0.95})
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will BTC hit 200K?")
    assert m.category_id == "crypto"
    assert m.secondary_categories == ()


def test_llm_returns_empty_categories_falls_back() -> None:
    """Multi-cat list with all unknown ids → router falls back to keyword."""
    backend = _ScriptedBackend({
        "categories": [{"id": "fictional", "weight": 1.0}],
        "confidence": 0.9,
    })
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will BTC hit 200K?")
    # Falls back to keyword routing — crypto should win on BTC
    assert m.category_id == "crypto"
    assert m.llm_used is False


# ---- blend_drift_event_weights -------------------------------------------


def test_blend_drift_event_weights_passes_through_for_single_category() -> None:
    """When secondary_categories is empty, weights pass through unchanged."""
    router = CategoryRouter(llm_backend=None)
    geo = router.route("Will war break out before 2030?")
    blended = blend_drift_event_weights(geo, secondary_categories_data={})
    # Tuple ordering preserved → bit-identical
    assert blended == geo.drift_event_weights


def test_blend_drift_event_weights_combines_across_categories() -> None:
    """Multi-cat blend produces weighted sum across categories."""
    backend = _ScriptedBackend({
        "categories": [
            {"id": "geopolitics", "weight": 0.6},
            {"id": "economics", "weight": 0.4},
        ],
        "confidence": 0.9,
    })
    router = CategoryRouter(llm_backend=backend)
    primary = router.route("Will Hormuz reopen?")
    assert primary.category_id == "geopolitics"
    secondary_data = {c["id"]: c for c in router.categories}
    blended = blend_drift_event_weights(primary, secondary_data)
    blended_dict = dict(blended)

    # Each event should equal: 0.6 * geopolitics_weight + 0.4 * economics_weight
    geo_dew = dict(primary.drift_event_weights)
    econ_dew = next(c["drift_event_weights"] for c in router.categories if c["id"] == "economics")
    for event in geo_dew:
        expected = 0.6 * float(geo_dew[event]) + 0.4 * float(econ_dew[event])
        assert blended_dict[event] == abs(expected) or abs(blended_dict[event] - expected) < 1e-9
