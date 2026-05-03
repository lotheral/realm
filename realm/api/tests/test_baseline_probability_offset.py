"""Sprint 16 WP2 / WP4: per-category baseline_probability_offset is applied
after sigmoid + clamp in realm/api/predict.py and re-clamped to [0.05, 0.95].

Validation range is [-0.05, +0.05]; the field defaults to 0.0 and is loaded
from config/prediction_categories.json into CategoryMatch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from realm.api.predict import _PROBABILITY_CLAMP
from realm.output.category_router import (
    _OFFSET_RANGE,
    CategoryRouter,
    _validate_categories,
)

CATEGORIES_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "config"
    / "prediction_categories.json"
)


def _apply_offset(prob: float, offset: float) -> float:
    """Mirrors the predict.py production wiring: add offset, then re-clamp."""
    if offset == 0.0:
        return prob
    return max(_PROBABILITY_CLAMP[0], min(_PROBABILITY_CLAMP[1], prob + offset))


# ---- Math: offset application + clamping --------------------------------


def test_offset_zero_preserves_sigmoid_result() -> None:
    for prob in (0.10, 0.30, 0.50, 0.69, 0.90):
        assert _apply_offset(prob, 0.0) == prob


def test_positive_offset_shifts_probability_up() -> None:
    assert _apply_offset(0.50, 0.03) == pytest.approx(0.53)
    assert _apply_offset(0.40, 0.05) == pytest.approx(0.45)


def test_negative_offset_shifts_probability_down() -> None:
    assert _apply_offset(0.50, -0.03) == pytest.approx(0.47)
    assert _apply_offset(0.55, -0.05) == pytest.approx(0.50)


def test_offset_clamped_to_upper_bound() -> None:
    """Probability that would exceed 0.95 after offset gets clamped."""
    assert _apply_offset(0.94, 0.05) == pytest.approx(_PROBABILITY_CLAMP[1])
    assert _apply_offset(0.95, 0.05) == _PROBABILITY_CLAMP[1]


def test_offset_clamped_to_lower_bound() -> None:
    """Probability that would drop below 0.05 after offset gets clamped."""
    assert _apply_offset(0.06, -0.05) == pytest.approx(_PROBABILITY_CLAMP[0])
    assert _apply_offset(0.05, -0.05) == _PROBABILITY_CLAMP[0]


# ---- Config validation --------------------------------------------------


def test_validation_rejects_offset_above_range() -> None:
    payload = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    payload["categories"][0]["baseline_probability_offset"] = 0.1
    with pytest.raises(ValueError, match="baseline_probability_offset"):
        _validate_categories(payload)


def test_validation_rejects_offset_below_range() -> None:
    payload = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    payload["categories"][0]["baseline_probability_offset"] = -0.1
    with pytest.raises(ValueError, match="baseline_probability_offset"):
        _validate_categories(payload)


def test_validation_rejects_non_numeric_offset() -> None:
    payload = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    payload["categories"][0]["baseline_probability_offset"] = "negative"
    with pytest.raises(ValueError, match="baseline_probability_offset"):
        _validate_categories(payload)


def test_validation_accepts_offset_at_boundary() -> None:
    payload = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    for boundary in _OFFSET_RANGE:
        payload["categories"][0]["baseline_probability_offset"] = float(boundary)
        # Should not raise.
        _validate_categories(payload)


# ---- CategoryMatch field ------------------------------------------------


def test_category_match_carries_offset_field() -> None:
    """CategoryRouter loads baseline_probability_offset from JSON and
    surfaces it on every CategoryMatch."""
    router = CategoryRouter()
    geo = router.route("Will NATO expand further before 2030?")
    politics = router.route("Will the incumbent president win the 2028 election?")
    # Both categories have the field present (default 0.0 in the shipped config).
    assert hasattr(geo, "baseline_probability_offset")
    assert hasattr(politics, "baseline_probability_offset")
    # Field is a float within the validation range.
    assert _OFFSET_RANGE[0] <= geo.baseline_probability_offset <= _OFFSET_RANGE[1]
    assert _OFFSET_RANGE[0] <= politics.baseline_probability_offset <= _OFFSET_RANGE[1]


def test_offset_only_geopolitics_carries_nonzero_default() -> None:
    """Sprint 16 WP3 result: only geopolitics ships with a non-zero default
    offset (last-mile fine-tune to push the strict <49.5% target after
    WP1 events + 5× magnitude scaling left the mean at 49.70%). Every
    other category ships with offset = 0.0 — guards against accidental
    drift of fine-tuning into other categories."""
    router = CategoryRouter()
    for cat in router.categories:
        offset = float(cat.get("baseline_probability_offset", 0.0))
        if cat["id"] == "geopolitics":
            assert -0.05 <= offset < 0.0, (
                f"geopolitics offset {offset} expected in [-0.05, 0) — Sprint 16 "
                f"hit <49.5% target by combining WP1 events with a small negative "
                f"fine-tune; non-negative offset would mean target wasn't reached."
            )
        else:
            assert offset == 0.0, (
                f"category {cat['id']!r} ships with non-zero offset={offset}; "
                f"only geopolitics should carry a calibration offset post-Sprint 16."
            )
