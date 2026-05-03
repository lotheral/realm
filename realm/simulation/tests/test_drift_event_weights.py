"""Sprint 14 WP1: weighted drift event sampling tests.

Verifies that:
1. event_weights=None preserves the legacy first-match-wins semantics
   (every existing drift test passes — see test_drift.py + test_drift_bridge.py).
2. When event_weights is supplied along with an rng, ALL matching rules are
   collected and one is sampled weighted by event_type weight.
3. The DriftEventBridge.with_weights() helper is round-trippable and frozen.
"""

from __future__ import annotations

import random
from collections import Counter

from realm.agents.decision import Decision
from realm.personality.trait_vector import TraitVector
from realm.simulation.drift import DriftEventBridge, _Rule


def _decision(
    *, action: str = "post", topic: str = "politics",
    sentiment: float = 0.5, virality: float = 1.5,
    engagement_kind: str | None = None,
) -> Decision:
    return Decision(
        action=action,
        topic=topic,
        sentiment=sentiment,
        virality=virality,
        engagement_kind=engagement_kind,
    )


def _multi_match_traits() -> TraitVector:
    """A TraitVector that satisfies leadership_act, group_dissent, AND
    successful_risk rules from drift_events.json simultaneously, so the
    weighted sampler has multiple options to choose between."""
    return TraitVector(
        social_dominance=0.9,
        contrarian_tendency=0.8,
        risk_appetite=0.9,
        loss_aversion=0.4,
        spirituality=0.3,
        analytical_depth=0.4,
        herd_susceptibility=0.4,
        neuroticism=0.5,
    )


def test_event_weights_none_preserves_first_match() -> None:
    """When event_weights is None (legacy default), event_for() returns the
    first matching rule deterministically, identical to pre-Sprint-14
    behavior. The presence of an rng MUST NOT change anything."""
    bridge = DriftEventBridge.default()
    decision = _decision(action="post", topic="politics", sentiment=0.6)
    traits = _multi_match_traits()

    # Without rng
    resolved_a = bridge.event_for(decision, traits)
    # With rng (still no weights → first-match path is taken)
    rng = random.Random(42)
    resolved_b = bridge.event_for(decision, traits, rng=rng)

    assert resolved_a == resolved_b
    assert resolved_a is not None
    # leadership_act is the first rule in drift_events.json that matches a
    # politics-topic, sentiment_gte=0.2, social_dominance>=0.6 post.
    assert resolved_a[0] == "leadership_act"


def test_with_weights_returns_new_frozen_bridge() -> None:
    """with_weights() returns a new DriftEventBridge (frozen dataclass).
    The original instance must remain unchanged."""
    bridge = DriftEventBridge.default()
    assert bridge.event_weights is None

    weighted = bridge.with_weights({"leadership_act": 5.0, "group_dissent": 1.0})
    assert weighted is not bridge
    assert bridge.event_weights is None
    assert weighted.event_weights is not None
    assert dict(weighted.event_weights)["leadership_act"] == 5.0

    # Round-trip None
    cleared = weighted.with_weights(None)
    assert cleared.event_weights is None


def test_weighted_sampling_distribution_matches_weights() -> None:
    """Chi-squared-light: when leadership_act:group_dissent weights are 9:1,
    leadership_act should dominate (>~75% of fires). Multiple rules match
    the same decision, so the weighted sampler chooses among them."""
    weights = {
        "positive_social": 1.0, "negative_social": 1.0,
        "successful_risk": 1.0, "failed_risk": 1.0,
        "knowledge_acquisition": 1.0, "stress_crisis": 1.0,
        "leadership_act": 9.0, "group_conformity": 1.0, "group_dissent": 1.0,
        "financial_loss": 1.0, "financial_gain": 1.0, "cultural_experience": 1.0,
    }
    bridge = DriftEventBridge.default().with_weights(weights)
    decision = _decision(action="post", topic="politics", sentiment=0.6)
    traits = _multi_match_traits()
    rng = random.Random(13)

    fires: Counter[str] = Counter()
    for _ in range(1000):
        resolved = bridge.event_for(decision, traits, rng=rng)
        if resolved is not None:
            fires[resolved[0]] += 1

    total = sum(fires.values())
    assert total >= 990, f"expected ~1000 firings, got {total}"
    # leadership_act has 9× the weight of any other matching rule's event,
    # so it should win the lion's share of samples.
    leadership_share = fires["leadership_act"] / total
    assert leadership_share > 0.6, (
        f"leadership_act share={leadership_share:.3f}, expected >0.6 with 9:1 weight"
    )


def test_weighted_sampling_inverted_distribution() -> None:
    """Same matching set, but now group_dissent gets 9× the weight — it
    should now dominate, not leadership_act. Confirms the weighted path
    actually consults the weights and isn't just picking by rule order."""
    # Sprint 16: include the 3 new geopolitics-pool events at weight 0 so they
    # don't act as default-1.0 candidates and dilute the 9:1 ratio under test.
    weights = {
        "positive_social": 1.0, "negative_social": 1.0,
        "successful_risk": 1.0, "failed_risk": 1.0,
        "knowledge_acquisition": 1.0, "stress_crisis": 1.0,
        "leadership_act": 1.0, "group_conformity": 1.0, "group_dissent": 9.0,
        "financial_loss": 1.0, "financial_gain": 1.0, "cultural_experience": 1.0,
        "regime_consolidation": 0.0, "diplomatic_stalemate": 0.0,
        "sanctions_pressure": 0.0,
    }
    bridge = DriftEventBridge.default().with_weights(weights)
    decision = _decision(action="post", topic="politics", sentiment=0.6)
    traits = _multi_match_traits()
    rng = random.Random(27)

    fires: Counter[str] = Counter()
    for _ in range(1000):
        resolved = bridge.event_for(decision, traits, rng=rng)
        if resolved is not None:
            fires[resolved[0]] += 1

    total = sum(fires.values())
    dissent_share = fires["group_dissent"] / total
    assert dissent_share > 0.6, (
        f"group_dissent share={dissent_share:.3f} with 9:1 weight, expected >0.6"
    )


def test_weighted_sampling_no_matches_returns_none() -> None:
    """Even with weights set, if no rule matches the decision the bridge
    must return None — there is no synthetic event firing."""
    weights = dict.fromkeys([
        "positive_social", "negative_social", "successful_risk", "failed_risk",
        "knowledge_acquisition", "stress_crisis", "leadership_act",
        "group_conformity", "group_dissent", "financial_loss",
        "financial_gain", "cultural_experience",
    ], 1.0)
    bridge = DriftEventBridge.default().with_weights(weights)
    rng = random.Random(0)
    # Lurk action returns None unconditionally (handled before rule loop).
    assert bridge.event_for(_decision(action="lurk"), _multi_match_traits(), rng=rng) is None


def test_weighted_zero_total_falls_back_to_first_match() -> None:
    """Pathological case: every weight is zero. The sampler must not crash;
    it falls back to returning the first matching rule's event. This is a
    safety net — config-load validation rejects zero weights, but a runtime
    `with_weights({all: 0})` could still construct one."""
    # Sprint 16: include all 15 event types (original 12 + new 3) at zero so
    # the bridge's "all weights zero → first-match fallback" path is exercised.
    weights = dict.fromkeys([
        "positive_social", "negative_social", "successful_risk", "failed_risk",
        "knowledge_acquisition", "stress_crisis", "leadership_act",
        "group_conformity", "group_dissent", "financial_loss",
        "financial_gain", "cultural_experience",
        "regime_consolidation", "diplomatic_stalemate", "sanctions_pressure",
    ], 0.0)
    bridge = DriftEventBridge.default().with_weights(weights)
    rng = random.Random(0)
    decision = _decision(action="post", topic="politics", sentiment=0.6)
    resolved = bridge.event_for(decision, _multi_match_traits(), rng=rng)
    assert resolved is not None
    assert resolved[0] == "leadership_act"  # first matching rule


def test_synthetic_rules_weighted_path() -> None:
    """A small synthetic 2-rule bridge to confirm the weighted-collect-all
    semantics independently of the production drift_events.json content."""
    rule_a = _Rule(name="A", event_type="event_a", intensity=0.5, action="post")
    rule_b = _Rule(name="B", event_type="event_b", intensity=0.5, action="post")
    bridge = DriftEventBridge(
        event_map={"event_a": {"openness": 1.0}, "event_b": {"openness": -1.0}},
        rules=(rule_a, rule_b),
    ).with_weights({"event_a": 4.0, "event_b": 1.0})
    rng = random.Random(99)
    fires = Counter()
    for _ in range(1000):
        resolved = bridge.event_for(_decision(), _multi_match_traits(), rng=rng)
        if resolved is not None:
            fires[resolved[0]] += 1
    assert fires.total() == 1000
    # event_a:event_b = 4:1 → expect ~80% event_a, ±5pp tolerance.
    assert 0.72 < fires["event_a"] / 1000 < 0.88
