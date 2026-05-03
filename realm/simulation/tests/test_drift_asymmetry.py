"""Sprint 15 WP3: drift_asymmetry scales the WHOLE event by primary-net sign.

The asymmetry multipliers fire only when ``primary_trait_set`` is non-empty
(category context). When unset (Sprint 14 path), behavior is bit-identical.
"""

from __future__ import annotations

from realm.personality.trait_vector import TraitVector
from realm.simulation.drift import _BASE_DRIFT_COEFFICIENT, ExperienceDriftEngine


def _traits() -> TraitVector:
    return TraitVector(
        empathy=0.5, agreeableness=0.5, social_dominance=0.5,
        neuroticism=0.5, openness=0.5, analytical_depth=0.5,
        information_sharing=0.5, risk_appetite=0.5, patience=0.5,
    )


def test_no_primary_set_no_scaling() -> None:
    """primary_trait_set=frozenset() → event_scale=1.0 (Sprint 14 path)."""
    asym = ExperienceDriftEngine(positive_multiplier=1.5, negative_multiplier=0.5)
    base = ExperienceDriftEngine()
    asym.record_event("a", "knowledge_acquisition", intensity=1.0, original_traits=_traits())
    base.record_event("a", "knowledge_acquisition", intensity=1.0, original_traits=_traits())
    assert asym.drift_vector("a") == base.drift_vector("a")


def test_primary_positive_event_amplified_by_pos_mul() -> None:
    """knowledge_acquisition net on science primary = +2.0 → scale by pos_mul."""
    science_primary = frozenset({"analytical_depth", "openness", "patience",
                                 "risk_appetite", "information_sharing"})
    eng = ExperienceDriftEngine(
        positive_multiplier=1.5,
        negative_multiplier=0.5,
        primary_trait_set=science_primary,
    )
    eng.record_event("a", "knowledge_acquisition", intensity=1.0, original_traits=_traits())
    drift = eng.drift_vector("a")
    # analytical_depth direction +1.0 × intensity 1.0 × coeff × pos_mul 1.5
    expected = 1.0 * 1.0 * _BASE_DRIFT_COEFFICIENT * 1.5
    assert abs(drift["analytical_depth"] - expected) < 1e-9


def test_primary_negative_event_dampened_by_neg_mul() -> None:
    """failed_risk net on science primary = risk_appetite -0.9 + patience +0.5
    = -0.4 → negative net → scale by neg_mul (0.5)."""
    science_primary = frozenset({"analytical_depth", "openness", "patience",
                                 "risk_appetite", "information_sharing"})
    eng = ExperienceDriftEngine(
        positive_multiplier=1.5,
        negative_multiplier=0.5,
        primary_trait_set=science_primary,
    )
    eng.record_event("a", "failed_risk", intensity=1.0, original_traits=_traits())
    drift = eng.drift_vector("a")
    # risk_appetite direction -0.9 × intensity 1.0 × coeff × neg_mul 0.5
    expected = -0.9 * 1.0 * _BASE_DRIFT_COEFFICIENT * 0.5
    assert abs(drift["risk_appetite"] - expected) < 1e-9


def test_neutral_event_no_scaling() -> None:
    """Event with zero net on primary → event_scale=1.0 unchanged."""
    # group_conformity on politics primary: herd_susceptibility (PRIMARY) +0.6
    # contrarian_tendency (PRIMARY) -0.5; net = +0.1 → positive scaling
    # On a primary set EXCLUDING all group_conformity-affected traits, net=0
    primary_no_overlap = frozenset({"empathy", "agreeableness"})
    eng = ExperienceDriftEngine(
        positive_multiplier=1.5,
        negative_multiplier=0.5,
        primary_trait_set=primary_no_overlap,
    )
    eng.record_event("a", "knowledge_acquisition", intensity=1.0, original_traits=_traits())
    # net on primary = 0 → event_scale=1.0; analytical drift = base coeff × 1.0
    expected = 1.0 * 1.0 * _BASE_DRIFT_COEFFICIENT * 1.0
    assert abs(eng.drift_vector("a")["analytical_depth"] - expected) < 1e-9


def test_asymmetry_persists_across_multiple_events() -> None:
    """Asymmetry applied per-event, not cumulative — every event scales
    independently based on its own primary-net sign."""
    science_primary = frozenset({"analytical_depth", "openness", "patience",
                                 "risk_appetite", "information_sharing"})
    eng = ExperienceDriftEngine(
        positive_multiplier=1.5,
        negative_multiplier=0.5,
        primary_trait_set=science_primary,
        max_drift_ratio=10.0,  # disable cap for this test
    )
    traits = _traits()
    # Two consecutive knowledge_acquisition events both get pos_mul scaling
    eng.record_event("a", "knowledge_acquisition", intensity=1.0, original_traits=traits)
    eng.record_event("a", "knowledge_acquisition", intensity=1.0, original_traits=traits)
    drift = eng.drift_vector("a")
    expected = 2 * 1.0 * 1.0 * _BASE_DRIFT_COEFFICIENT * 1.5
    assert abs(drift["analytical_depth"] - expected) < 1e-9
