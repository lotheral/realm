"""Sprint 15 WP4: per-category sigmoid_sensitivity_multiplier scales the
predict.py base sigmoid sensitivity (8.0). Higher → steeper probability
curve; lower → flatter (probability stays closer to 50% for the same
weighted deviation).
"""

from __future__ import annotations

import math

from realm.api.predict import _SIGMOID_SENSITIVITY


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def test_default_sensitivity_matches_sprint13() -> None:
    """When sigmoid_sensitivity_multiplier=1.0, σ(8.0×dev) is the
    Sprint 13 baseline. A 0.10 weighted deviation maps to ~69%."""
    sens = _SIGMOID_SENSITIVITY * 1.0
    p = _sigmoid(sens * 0.10)
    assert 0.685 < p < 0.695


def test_higher_multiplier_amplifies_probability_swing() -> None:
    """sigmoid_sensitivity_multiplier=1.4 (crypto) — same 0.10 deviation
    maps to a STRONGER probability move than the default."""
    base = _sigmoid(_SIGMOID_SENSITIVITY * 1.0 * 0.05)
    crypto = _sigmoid(_SIGMOID_SENSITIVITY * 1.4 * 0.05)
    assert crypto > base


def test_lower_multiplier_dampens_probability_swing() -> None:
    """sigmoid_sensitivity_multiplier=0.5 (politics) — same 0.05 deviation
    maps to a SMALLER probability move; result stays closer to 50%."""
    base = _sigmoid(_SIGMOID_SENSITIVITY * 1.0 * 0.05)
    politics = _sigmoid(_SIGMOID_SENSITIVITY * 0.5 * 0.05)
    assert abs(politics - 0.5) < abs(base - 0.5)


def test_zero_deviation_always_50pct() -> None:
    """No deviation → probability = 0.5 regardless of multiplier."""
    for mult in (0.5, 1.0, 1.4, 2.0):
        assert _sigmoid(_SIGMOID_SENSITIVITY * mult * 0.0) == 0.5


def test_category_match_carries_sigmoid_field() -> None:
    """CategoryRouter loads sigmoid_sensitivity_multiplier from JSON."""
    from realm.output.category_router import CategoryRouter
    router = CategoryRouter()
    crypto_match = router.route("Will Bitcoin hit 200K?")
    politics_match = router.route("Will the incumbent win the election?")
    assert crypto_match.sigmoid_sensitivity_multiplier > 1.0
    assert politics_match.sigmoid_sensitivity_multiplier < 1.0
