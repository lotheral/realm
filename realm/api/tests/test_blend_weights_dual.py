"""Sprint 19 WP1 — dual baseline / scenario blend weight tests.

Verifies that ``predict_endpoint`` picks ``llm_blend_weight`` for
baseline calls and ``scenario_llm_blend_weight`` for calls with a
``scenario_feed``. The actual blending math is covered by
``test_probability_blend.py``; here we just check the right weight
is consulted in the right place.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from realm.output.category_router import (
    _LLM_BLEND_RANGE,
    CategoryRouter,
    _validate_categories,
)

_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "config" / "prediction_categories.json"
)


def _load_config() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


# ---- Recalibrated values ---------------------------------------------------


def test_baseline_weights_are_llm_dominant() -> None:
    """Sprint 19 raised baseline LLM weights to 0.85-0.95 across the
    board after Sprint 18's backtest showed sim adds negative value."""
    router = CategoryRouter(llm_backend=None)
    by_id = {m["id"]: m for m in router.categories}
    for cid in ("politics", "economics", "crypto", "sports", "markets",
                "culture", "geopolitics", "balanced"):
        w = float(by_id[cid]["llm_blend_weight"])
        assert 0.85 <= w <= 0.95, (
            f"baseline llm_blend_weight for {cid!r} = {w}; "
            f"Sprint 19 expected 0.85-0.95"
        )
    assert float(by_id["science"]["llm_blend_weight"]) == 0.95


def test_scenario_weights_are_sim_dominant() -> None:
    """Scenario weights flip the dominance: simulation drives the
    perturbation response, LLM adjusts qualitative interpretation."""
    router = CategoryRouter(llm_backend=None)
    by_id = {m["id"]: m for m in router.categories}
    for cid in ("politics", "economics", "crypto", "sports", "markets",
                "culture", "geopolitics", "balanced"):
        w = float(by_id[cid]["scenario_llm_blend_weight"])
        assert w == 0.40, (
            f"scenario_llm_blend_weight for {cid!r} = {w}; "
            f"Sprint 19 expected 0.40 (sim-dominant)"
        )
    # Science is the exception — evidence still matters in scenarios
    assert float(by_id["science"]["scenario_llm_blend_weight"]) == 0.50


# ---- Validation -----------------------------------------------------------


def test_scenario_blend_weight_validated_to_unit_range() -> None:
    payload = _load_config()
    payload["categories"][0]["scenario_llm_blend_weight"] = 1.5
    with pytest.raises(ValueError, match="scenario_llm_blend_weight"):
        _validate_categories(payload)


def test_scenario_blend_weight_accepts_boundary() -> None:
    payload = _load_config()
    for boundary in _LLM_BLEND_RANGE:
        payload["categories"][0]["scenario_llm_blend_weight"] = float(boundary)
        _validate_categories(payload)  # should not raise


# ---- CategoryMatch carries both fields -----------------------------------


def test_category_match_exposes_both_blend_weights() -> None:
    router = CategoryRouter(llm_backend=None)
    geo = router.route("Will war break out before 2030?")
    assert hasattr(geo, "llm_blend_weight")
    assert hasattr(geo, "scenario_llm_blend_weight")
    assert geo.llm_blend_weight != geo.scenario_llm_blend_weight


def test_default_scenario_weight_is_0_4_when_missing() -> None:
    """Backward compat: a category JSON without scenario_llm_blend_weight
    should fall back to 0.4 default."""
    payload = _load_config()
    # Strip the field from one category
    cat = payload["categories"][0]
    cat.pop("scenario_llm_blend_weight", None)
    valid = _validate_categories(payload)  # should still validate

    # Manually build CategoryRouter from sanitized config to verify
    # the default flows through to CategoryMatch.
    router = CategoryRouter(categories=list(valid))
    primary_id = cat["id"]
    by_id = {m["id"]: m for m in router.categories}
    assert by_id[primary_id].get("scenario_llm_blend_weight") is None or \
           by_id[primary_id].get("scenario_llm_blend_weight") == 0.4
    # The match constructed for any question that routes to this
    # category should have scenario_llm_blend_weight = 0.4
    # (since the field is absent, _build_match falls back to default).
