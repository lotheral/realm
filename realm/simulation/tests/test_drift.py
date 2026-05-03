"""Tests for ExperienceDriftEngine — Sprint 9 WP3."""

from __future__ import annotations

import pytest

from realm.personality.trait_vector import TraitVector
from realm.simulation.drift import (
    _BASE_DRIFT_COEFFICIENT,
    ExperienceDriftEngine,
    event_from_decision,
)


@pytest.fixture
def traits() -> TraitVector:
    return TraitVector.from_dict({
        "empathy": 0.5,
        "agreeableness": 0.5,
        "social_dominance": 0.5,
        "neuroticism": 0.5,
        "risk_appetite": 0.5,
        "loss_aversion": 0.5,
        "analytical_depth": 0.5,
        "openness": 0.5,
    })


class TestRecordEvent:
    def test_single_event_shifts_mapped_traits(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a1", "positive_social", 1.0, traits)
        drift = engine.drift_vector("a1")
        # positive_social: empathy +1.0, agreeableness +0.7, social_dominance +0.3, neuroticism -0.4
        assert drift["empathy"] == pytest.approx(1.0 * _BASE_DRIFT_COEFFICIENT)
        assert drift["agreeableness"] == pytest.approx(0.7 * _BASE_DRIFT_COEFFICIENT)
        assert drift["neuroticism"] == pytest.approx(-0.4 * _BASE_DRIFT_COEFFICIENT)

    def test_unknown_event_is_noop(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a1", "nonexistent_event_xyz", 1.0, traits)
        assert engine.drift_vector("a1") == {}
        assert engine.event_count("a1") == 0

    def test_unmapped_trait_is_skipped(self, traits: TraitVector) -> None:
        # empathy is in the default map but our custom has no such trait
        engine = ExperienceDriftEngine(
            event_map={"custom_event": {"nonexistent_trait": 1.0}},
        )
        engine.record_event("a1", "custom_event", 1.0, traits)
        assert engine.drift_vector("a1") == {}

    def test_intensity_clamped_to_unit_interval(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a1", "positive_social", 2.5, traits)  # > 1
        engine.record_event("a2", "positive_social", 1.0, traits)
        # Intensity 2.5 should clamp to 1.0, so deltas should match 1.0 case
        assert engine.drift_vector("a1")["empathy"] == pytest.approx(
            engine.drift_vector("a2")["empathy"]
        )

    def test_negative_intensity_clamped_to_zero(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a1", "positive_social", -0.5, traits)
        assert engine.drift_vector("a1") == {}  # no movement


class TestCumulativeClamp:
    def test_drift_clamped_to_max_drift_ratio_of_original(self, traits: TraitVector) -> None:
        # empathy original = 0.5, max_drift_ratio = 0.10 → cap ±0.05
        engine = ExperienceDriftEngine(max_drift_ratio=0.10)
        for _ in range(200):
            engine.record_event("a1", "positive_social", 1.0, traits)
        drift = engine.drift_vector("a1")
        # Cap on empathy is 0.5 * 0.10 = 0.05
        assert drift["empathy"] <= 0.05 + 1e-9
        assert drift["empathy"] >= 0.05 - 1e-6

    def test_negative_direction_respects_cap(self, traits: TraitVector) -> None:
        # failed_risk drives loss_aversion up (+1.0) and risk_appetite down (-0.9)
        engine = ExperienceDriftEngine(max_drift_ratio=0.10)
        for _ in range(200):
            engine.record_event("a1", "failed_risk", 1.0, traits)
        drift = engine.drift_vector("a1")
        cap = 0.5 * 0.10
        assert drift["loss_aversion"] == pytest.approx(cap, abs=1e-6)
        assert drift["risk_appetite"] == pytest.approx(-cap, abs=1e-6)

    def test_never_pushes_trait_out_of_unit_interval(self) -> None:
        # Extreme original value near ceiling
        ceiling_traits = TraitVector.from_dict({"empathy": 0.98})
        engine = ExperienceDriftEngine(max_drift_ratio=0.10)
        # hypothetically 0.98 * 0.10 = 0.098 upward cap → pushes empathy past 1.0
        # engine must additionally clamp to stay within [0, 1] after apply_modifier
        for _ in range(300):
            engine.record_event("a1", "positive_social", 1.0, ceiling_traits)
        drifted = engine.current_traits(
            _DummyAgent("a1", ceiling_traits)
        )
        assert 0.0 <= drifted.empathy <= 1.0


class TestDeterminism:
    def test_same_event_sequence_same_drift(self, traits: TraitVector) -> None:
        e1 = ExperienceDriftEngine()
        e2 = ExperienceDriftEngine()
        events = [("positive_social", 0.8),
                  ("failed_risk", 0.6),
                  ("knowledge_acquisition", 1.0),
                  ("stress_crisis", 0.4),
                  ("negative_social", 0.5)]
        for et, inten in events:
            e1.record_event("x", et, inten, traits)
            e2.record_event("x", et, inten, traits)
        assert e1.drift_vector("x") == e2.drift_vector("x")

    def test_agent_with_no_events_has_no_drift(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("other_agent", "positive_social", 1.0, traits)
        assert engine.drift_vector("unchanged_agent") == {}
        # current_traits returns original unchanged
        agent = _DummyAgent("unchanged_agent", traits)
        assert engine.current_traits(agent) is traits

    def test_cumulative_magnitude_grows_monotonically_until_cap(
        self, traits: TraitVector
    ) -> None:
        engine = ExperienceDriftEngine()
        mags = []
        for _ in range(20):
            engine.record_event("a1", "positive_social", 1.0, traits)
            mags.append(engine.cumulative_magnitude("a1"))
        # Strictly non-decreasing
        assert all(mags[i] <= mags[i + 1] + 1e-9 for i in range(len(mags) - 1))


class TestCurrentTraitsAndImmutability:
    def test_original_traits_never_mutated(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        original_dict = traits.to_dict()
        for _ in range(50):
            engine.record_event("a1", "failed_risk", 1.0, traits)
        # original TraitVector untouched (dataclass is frozen)
        assert traits.to_dict() == original_dict

    def test_current_traits_reflects_accumulated_drift(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        for _ in range(200):
            engine.record_event("a1", "knowledge_acquisition", 1.0, traits)
        agent = _DummyAgent("a1", traits)
        drifted = engine.current_traits(agent)
        # analytical_depth direction +1, cap +0.05 → drifted value = 0.55
        assert drifted.analytical_depth == pytest.approx(0.55, abs=1e-6)


class TestStateRoundTrip:
    def test_to_state_from_state_is_identity(self, traits: TraitVector) -> None:
        e1 = ExperienceDriftEngine(max_drift_ratio=0.08)
        e1.record_event("a1", "positive_social", 0.7, traits)
        e1.record_event("a2", "failed_risk", 1.0, traits)
        e2 = ExperienceDriftEngine.from_state(e1.to_state())
        assert e2.max_drift_ratio == 0.08
        assert e2.drift_vector("a1") == e1.drift_vector("a1")
        assert e2.drift_vector("a2") == e1.drift_vector("a2")
        assert e2.event_count("a1") == e1.event_count("a1")


class TestEventFromDecision:
    def test_post_positive_sentiment_is_positive_social(self) -> None:
        assert event_from_decision("post", 0.5) == "positive_social"

    def test_post_negative_sentiment_is_negative_social(self) -> None:
        assert event_from_decision("post", -0.3) == "negative_social"

    def test_post_no_sentiment_defaults_to_positive(self) -> None:
        assert event_from_decision("post", None) == "positive_social"

    def test_engage_is_positive_social(self) -> None:
        assert event_from_decision("engage", None) == "positive_social"

    def test_lurk_emits_no_drift(self) -> None:
        assert event_from_decision("lurk", None) is None

    def test_unknown_action_emits_no_drift(self) -> None:
        assert event_from_decision("unknown_weird_action", None) is None


class TestResetPaths:
    def test_reset_agent_clears_only_that_agent(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a1", "positive_social", 1.0, traits)
        engine.record_event("a2", "positive_social", 1.0, traits)
        engine.reset_agent("a1")
        assert engine.drift_vector("a1") == {}
        assert engine.drift_vector("a2") != {}

    def test_reset_all_clears_everyone(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a1", "positive_social", 1.0, traits)
        engine.record_event("a2", "failed_risk", 1.0, traits)
        engine.reset_all()
        assert engine.drift_vector("a1") == {}
        assert engine.drift_vector("a2") == {}


# ---- helpers ---------------------------------------------------------------


class _DummyAgent:
    """Minimal stand-in with .agent_id and .traits — avoids full Agent construction."""

    def __init__(self, agent_id: str, traits: TraitVector) -> None:
        self.agent_id = agent_id
        self.traits = traits
