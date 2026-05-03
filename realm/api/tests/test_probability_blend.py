"""Sprint 17 WP2 — probability blending (LLM prior + simulation).

The blender lives in ``realm.api.predict._blend_with_llm_prior`` and is
called once per ``predict_endpoint`` invocation (separately for the
baseline and scenario probabilities) when an LLM-derived prior is
available.
"""

from __future__ import annotations

import json

import pytest

from realm.api.predict import _PROBABILITY_CLAMP, _blend_with_llm_prior
from realm.output.category_router import (
    _LLM_BLEND_RANGE,
    CategoryRouter,
    _validate_categories,
)

# ---- Math: blend_weight semantics + clamping --------------------------------


def test_blend_returns_sim_prob_when_llm_prior_none() -> None:
    """When the analyzer produced no usable prior (LLM unavailable / failed
    schema), the simulation probability passes through unchanged AND
    blended_prob is None so callers can detect the no-blend case."""
    final, blended = _blend_with_llm_prior(
        sim_prob=0.6, llm_prior=None, blend_weight=0.5,
    )
    assert final == 0.6
    assert blended is None


def test_blend_60_40_default_weight() -> None:
    """Default weight 0.6 means LLM 60% / sim 40%. With sim=0.5 and
    prior=0.3, blended = 0.4*0.5 + 0.6*0.3 = 0.38."""
    final, blended = _blend_with_llm_prior(
        sim_prob=0.5, llm_prior=0.3, blend_weight=0.6,
    )
    assert final == pytest.approx(0.38)
    assert blended == pytest.approx(0.38)


def test_blend_at_zero_weight_uses_sim_only() -> None:
    """blend_weight=0 → blended equals sim (LLM contributes 0%) but
    blended_prob is still a number (not None) so callers can tell the
    blend ran."""
    final, blended = _blend_with_llm_prior(
        sim_prob=0.7, llm_prior=0.2, blend_weight=0.0,
    )
    assert final == pytest.approx(0.7)
    assert blended == pytest.approx(0.7)


def test_blend_at_one_weight_uses_llm_only() -> None:
    final, blended = _blend_with_llm_prior(
        sim_prob=0.7, llm_prior=0.2, blend_weight=1.0,
    )
    assert final == pytest.approx(0.2)
    assert blended == pytest.approx(0.2)


def test_blend_clamped_to_lower_bound() -> None:
    """Blended result that falls below the [0.05, 0.95] clamp is pulled in."""
    final, blended = _blend_with_llm_prior(
        sim_prob=0.04, llm_prior=0.04, blend_weight=0.5,
    )
    assert final == _PROBABILITY_CLAMP[0]
    assert blended == _PROBABILITY_CLAMP[0]


def test_blend_clamped_to_upper_bound() -> None:
    final, blended = _blend_with_llm_prior(
        sim_prob=0.96, llm_prior=0.96, blend_weight=0.5,
    )
    assert final == _PROBABILITY_CLAMP[1]
    assert blended == _PROBABILITY_CLAMP[1]


# ---- Per-category weight loading + validation ------------------------------


def test_per_category_weight_loaded_from_config() -> None:
    """CategoryRouter exposes the per-category llm_blend_weight set in the
    shipped config. Sprint 19 recalibrated baseline weights to be
    LLM-dominant (0.85-0.95) after Sprint 18 backtesting showed sim
    adds negative value to baselines."""
    router = CategoryRouter(llm_backend=None)
    by_id = {m["id"]: m for m in router.categories}
    # Baseline LLM weight (existing field)
    assert float(by_id["science"]["llm_blend_weight"]) == 0.95
    assert float(by_id["sports"]["llm_blend_weight"]) == 0.85
    assert float(by_id["crypto"]["llm_blend_weight"]) == 0.85
    assert float(by_id["geopolitics"]["llm_blend_weight"]) == 0.90
    assert float(by_id["balanced"]["llm_blend_weight"]) == 0.90
    # Sprint 19 WP1: scenario weights are sim-dominant (0.40 LLM)
    # except science where evidence still matters (0.50)
    assert float(by_id["science"]["scenario_llm_blend_weight"]) == 0.50
    assert float(by_id["crypto"]["scenario_llm_blend_weight"]) == 0.40
    assert float(by_id["geopolitics"]["scenario_llm_blend_weight"]) == 0.40


def test_validation_rejects_blend_weight_above_one() -> None:
    """Validator catches weights outside [0.0, 1.0]."""
    from pathlib import Path
    payload = json.loads(
        (Path(__file__).resolve().parent.parent.parent.parent
         / "config" / "prediction_categories.json").read_text(encoding="utf-8")
    )
    payload["categories"][0]["llm_blend_weight"] = 1.5
    with pytest.raises(ValueError, match="llm_blend_weight"):
        _validate_categories(payload)


def test_validation_accepts_boundary_weights() -> None:
    from pathlib import Path
    payload = json.loads(
        (Path(__file__).resolve().parent.parent.parent.parent
         / "config" / "prediction_categories.json").read_text(encoding="utf-8")
    )
    for boundary in _LLM_BLEND_RANGE:
        payload["categories"][0]["llm_blend_weight"] = float(boundary)
        # Should not raise.
        _validate_categories(payload)
