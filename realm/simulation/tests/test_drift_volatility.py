"""Sprint 15 WP2: drift_volatility scales both the cumulative cap and the
per-event intensity_scale. Default 1.0 preserves Sprint 14 behavior."""

from __future__ import annotations

from realm.personality.trait_vector import TraitVector
from realm.simulation.drift import _BASE_DRIFT_COEFFICIENT, ExperienceDriftEngine


def _agent_traits() -> TraitVector:
    return TraitVector(
        empathy=0.5, agreeableness=0.5, social_dominance=0.5,
        neuroticism=0.5, openness=0.5, risk_appetite=0.5,
    )


def test_default_volatility_matches_sprint14() -> None:
    """max_drift_ratio=0.10, intensity_scale=1.0 — bit-identical to Sprint 14."""
    eng = ExperienceDriftEngine()
    assert eng.max_drift_ratio == 0.10
    assert eng.intensity_scale == 1.0
    assert eng.positive_multiplier == 1.0
    assert eng.negative_multiplier == 1.0
    eng.record_event("a1", "positive_social", intensity=0.5,
                     original_traits=_agent_traits())
    drift = eng.drift_vector("a1")
    # Empathy direction +1.0 × intensity 0.5 × _BASE_DRIFT_COEFFICIENT
    assert abs(drift["empathy"] - (1.0 * 0.5 * _BASE_DRIFT_COEFFICIENT)) < 1e-9


def test_volatility_widens_cap() -> None:
    """drift_volatility 2.0 → max_drift_ratio 0.20 → cap 2× higher."""
    low = ExperienceDriftEngine(max_drift_ratio=0.05, intensity_scale=1.0)
    high = ExperienceDriftEngine(max_drift_ratio=0.20, intensity_scale=1.0)
    traits = _agent_traits()
    # Fire many events on the same agent so the cap binds.
    for _ in range(50):
        low.record_event("a", "positive_social", intensity=1.0, original_traits=traits)
        high.record_event("a", "positive_social", intensity=1.0, original_traits=traits)
    low_drift = abs(low.drift_vector("a")["empathy"])
    high_drift = abs(high.drift_vector("a")["empathy"])
    # Both should be capped — high cap > low cap
    assert high_drift > low_drift
    # Approximate cap (original 0.5 × ratio):
    assert abs(low_drift - 0.5 * 0.05) < 1e-6
    assert abs(high_drift - 0.5 * 0.20) < 1e-6


def test_intensity_scale_speeds_drift() -> None:
    """intensity_scale=2.0 → drift accumulates 2× faster per event."""
    slow = ExperienceDriftEngine(intensity_scale=1.0)
    fast = ExperienceDriftEngine(intensity_scale=2.0)
    traits = _agent_traits()
    slow.record_event("a", "positive_social", intensity=0.5, original_traits=traits)
    fast.record_event("a", "positive_social", intensity=0.5, original_traits=traits)
    slow_d = slow.drift_vector("a")["empathy"]
    fast_d = fast.drift_vector("a")["empathy"]
    assert abs(fast_d - 2.0 * slow_d) < 1e-9


def test_intensity_scale_default_preserves_event_size() -> None:
    """intensity_scale=1.0 → identical numbers to before Sprint 15."""
    eng = ExperienceDriftEngine(intensity_scale=1.0)
    traits = _agent_traits()
    eng.record_event("a", "positive_social", intensity=1.0, original_traits=traits)
    # +1.0 × 1.0 × _BASE_DRIFT_COEFFICIENT → empathy delta
    assert abs(eng.drift_vector("a")["empathy"] - _BASE_DRIFT_COEFFICIENT) < 1e-9
