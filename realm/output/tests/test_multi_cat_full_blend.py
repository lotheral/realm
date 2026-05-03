"""Sprint 19 WP3 — multi-category FULL parameter blending tests.

Sprint 18's blend_drift_event_weights only blended drift event weights
across categories. Sprint 19's blend_category_parameters extends to
sigmoid sensitivity, drift volatility, drift asymmetry, and
baseline_probability_offset.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from realm.llm.interfaces import ILLMBackend, LLMResponse
from realm.output.category_router import (
    CategoryRouter,
    blend_category_parameters,
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


def _hormuz_router() -> tuple[CategoryRouter, dict]:
    """Build a router that LLM-routes Hormuz to geopolitics(0.6) +
    economics(0.25) + markets(0.15). Returns (router, by_id_data)."""
    backend = _ScriptedBackend({
        "categories": [
            {"id": "geopolitics", "weight": 0.6},
            {"id": "economics", "weight": 0.25},
            {"id": "markets", "weight": 0.15},
        ],
        "confidence": 0.9,
    })
    router = CategoryRouter(llm_backend=backend)
    return router, {c["id"]: c for c in router.categories}


# ---- Single-category passthrough -----------------------------------------


def test_single_category_passes_through_unchanged() -> None:
    """When secondary_categories is empty, blend_category_parameters
    returns values identical to the primary CategoryMatch."""
    router = CategoryRouter(llm_backend=None)
    geo = router.route("Will war break out before 2030?")
    blended = blend_category_parameters(geo, {})
    assert blended["drift_volatility"] == geo.drift_volatility
    assert blended["sigmoid_sensitivity_multiplier"] == geo.sigmoid_sensitivity_multiplier
    assert blended["drift_asymmetry_positive"] == geo.drift_asymmetry_positive
    assert blended["drift_asymmetry_negative"] == geo.drift_asymmetry_negative
    assert blended["baseline_probability_offset"] == geo.baseline_probability_offset


# ---- Multi-cat blends scalars per weights -------------------------------


def test_multi_cat_sigmoid_is_weighted_average() -> None:
    """sigmoid blended = 0.6*geo + 0.25*econ + 0.15*markets"""
    router, by_id = _hormuz_router()
    primary = router.route("Will the Strait of Hormuz reopen?")
    blended = blend_category_parameters(primary, by_id)
    expected = (
        0.6 * float(by_id["geopolitics"]["sigmoid_sensitivity_multiplier"])
        + 0.25 * float(by_id["economics"]["sigmoid_sensitivity_multiplier"])
        + 0.15 * float(by_id["markets"]["sigmoid_sensitivity_multiplier"])
    )
    assert abs(blended["sigmoid_sensitivity_multiplier"] - expected) < 1e-9


def test_multi_cat_volatility_is_weighted_average() -> None:
    router, by_id = _hormuz_router()
    primary = router.route("Will the Strait of Hormuz reopen?")
    blended = blend_category_parameters(primary, by_id)
    expected = (
        0.6 * float(by_id["geopolitics"]["drift_volatility"])
        + 0.25 * float(by_id["economics"]["drift_volatility"])
        + 0.15 * float(by_id["markets"]["drift_volatility"])
    )
    assert abs(blended["drift_volatility"] - expected) < 1e-9


def test_multi_cat_asymmetry_is_weighted_average() -> None:
    router, by_id = _hormuz_router()
    primary = router.route("Will the Strait of Hormuz reopen?")
    blended = blend_category_parameters(primary, by_id)
    expected_pos = (
        0.6 * float(by_id["geopolitics"]["drift_asymmetry"]["positive_multiplier"])
        + 0.25 * float(by_id["economics"]["drift_asymmetry"]["positive_multiplier"])
        + 0.15 * float(by_id["markets"]["drift_asymmetry"]["positive_multiplier"])
    )
    expected_neg = (
        0.6 * float(by_id["geopolitics"]["drift_asymmetry"]["negative_multiplier"])
        + 0.25 * float(by_id["economics"]["drift_asymmetry"]["negative_multiplier"])
        + 0.15 * float(by_id["markets"]["drift_asymmetry"]["negative_multiplier"])
    )
    assert abs(blended["drift_asymmetry_positive"] - expected_pos) < 1e-9
    assert abs(blended["drift_asymmetry_negative"] - expected_neg) < 1e-9


def test_multi_cat_baseline_offset_is_weighted_average() -> None:
    """Geopolitics has -0.005 offset; others have 0.0. Blended should
    be 0.6 * -0.005 = -0.003."""
    router, by_id = _hormuz_router()
    primary = router.route("Will the Strait of Hormuz reopen?")
    blended = blend_category_parameters(primary, by_id)
    expected = (
        0.6 * float(by_id["geopolitics"]["baseline_probability_offset"])
        + 0.25 * float(by_id["economics"].get("baseline_probability_offset", 0.0))
        + 0.15 * float(by_id["markets"].get("baseline_probability_offset", 0.0))
    )
    assert abs(blended["baseline_probability_offset"] - expected) < 1e-9


def test_multi_cat_drift_events_blended_weighted() -> None:
    """Drift events also blended (Sprint 18 logic, here as regression)."""
    router, by_id = _hormuz_router()
    primary = router.route("Will the Strait of Hormuz reopen?")
    blended = blend_category_parameters(primary, by_id)
    blended_dew = dict(blended["drift_event_weights"])

    expected = {}
    for cat_id, w in (("geopolitics", 0.6), ("economics", 0.25), ("markets", 0.15)):
        for event, ew in by_id[cat_id]["drift_event_weights"].items():
            expected[event] = expected.get(event, 0.0) + w * float(ew)
    for event, ev_weight in expected.items():
        assert abs(blended_dew.get(event, 0.0) - ev_weight) < 1e-9
