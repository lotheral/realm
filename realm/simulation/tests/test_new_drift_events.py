"""Sprint 16 WP1 / WP4: tests for the three new geopolitics-pool drift events
(regime_consolidation, diplomatic_stalemate, sanctions_pressure) plus the
expanded 15-event bridge bookkeeping.

Pattern matches realm/simulation/tests/test_drift_bridge.py — same fixtures,
same Decision helpers, same event-direction parametrize style.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import pytest

from realm.agents.decision import Decision
from realm.personality.trait_vector import TraitVector
from realm.simulation.drift import DriftEventBridge

CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "config"
    / "drift_events.json"
)
CATEGORIES_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "config"
    / "prediction_categories.json"
)

NEW_EVENTS = ("regime_consolidation", "diplomatic_stalemate", "sanctions_pressure")


@pytest.fixture
def bridge() -> DriftEventBridge:
    return DriftEventBridge.from_json(CONFIG_PATH)


@pytest.fixture
def event_types() -> dict:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return payload["event_types"]


@pytest.fixture
def categories() -> list[dict]:
    payload = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    return payload["categories"]


def _post() -> Decision:
    return Decision(action="post", topic="politics", sentiment=0.0, virality=1.0)


def _engage() -> Decision:
    return Decision(action="engage", target_post_id="p1", engagement_kind="like")


def _generic_traits() -> TraitVector:
    """Mid-range traits that don't fire any specific rule — exercises the
    fallback paths where the new geopolitics-pool events live."""
    return TraitVector.from_dict({
        "empathy": 0.5, "agreeableness": 0.5, "social_dominance": 0.3,
        "neuroticism": 0.3, "contrarian_tendency": 0.3,
        "herd_susceptibility": 0.3, "individualism": 0.5,
        "analytical_depth": 0.4, "openness": 0.5, "risk_appetite": 0.3,
        "loss_aversion": 0.3, "financial_optimism": 0.5, "spirituality": 0.3,
        "tradition_vs_progress": 0.5, "persuasion_skill": 0.4,
        "communication_assertiveness": 0.4, "authority_compliance": 0.4,
        "impulsivity": 0.3, "patience": 0.5, "fomo_susceptibility": 0.3,
        "information_sharing": 0.5,
    })


# ---- WP1 event_types schema ---------------------------------------------


def test_total_event_count_is_fifteen(event_types: dict) -> None:
    """Sprint 9 → 6, Sprint 10 → 12, Sprint 16 → 15."""
    assert len(event_types) == 15


@pytest.mark.parametrize("event_name", NEW_EVENTS)
def test_new_event_present_in_config(event_name: str, event_types: dict) -> None:
    assert event_name in event_types
    assert "traits" in event_types[event_name]
    assert isinstance(event_types[event_name]["traits"], dict)
    assert len(event_types[event_name]["traits"]) >= 3


@pytest.mark.parametrize("event_name,trait,expected_sign", [
    # regime_consolidation: power consolidation is net-negative on geopolitics
    # primary set (authority_compliance ↓ from apathy, social_dominance ↓
    # from agency erosion, empathy ↓ from desensitization, contrarian ↑).
    ("regime_consolidation", "authority_compliance", "negative"),
    ("regime_consolidation", "social_dominance", "negative"),
    ("regime_consolidation", "empathy", "negative"),
    ("regime_consolidation", "contrarian_tendency", "positive"),
    # diplomatic_stalemate: stalled negotiations.
    ("diplomatic_stalemate", "risk_appetite", "negative"),
    ("diplomatic_stalemate", "social_dominance", "negative"),
    ("diplomatic_stalemate", "contrarian_tendency", "positive"),
    ("diplomatic_stalemate", "authority_compliance", "positive"),
    # sanctions_pressure: economic + political pain.
    ("sanctions_pressure", "financial_optimism", "negative"),
    ("sanctions_pressure", "risk_appetite", "negative"),
    ("sanctions_pressure", "loss_aversion", "positive"),
    ("sanctions_pressure", "authority_compliance", "positive"),
])
def test_new_event_trait_directions(
    event_name: str, trait: str, expected_sign: str, event_types: dict,
) -> None:
    """Every trait coefficient on the new events points the direction the
    real-world dynamic predicts — see _doc fields in drift_events.json."""
    coef = event_types[event_name]["traits"][trait]
    if expected_sign == "negative":
        assert coef < 0.0, f"{event_name}.{trait}={coef} expected negative"
    else:
        assert coef > 0.0, f"{event_name}.{trait}={coef} expected positive"


def test_event_map_loaded_from_config(bridge: DriftEventBridge) -> None:
    """Bridge auto-discovers new events without code changes."""
    for event_name in NEW_EVENTS:
        assert event_name in bridge.event_map
        traits = bridge.event_map[event_name]
        assert len(traits) >= 3


# ---- WP1 rule wiring ----------------------------------------------------


def test_each_new_event_has_post_and_engage_rule(bridge: DriftEventBridge) -> None:
    """Each new event has 2 rules (post + engage), mirroring the
    positive_social_fallback pattern."""
    by_event: dict[str, list[str]] = {ev: [] for ev in NEW_EVENTS}
    for rule in bridge.rules:
        if rule.event_type in by_event:
            by_event[rule.event_type].append(rule.action)
    for ev, actions in by_event.items():
        assert "post" in actions, f"{ev} missing post rule"
        assert "engage" in actions, f"{ev} missing engage rule"


def test_new_rules_positioned_after_legacy_fallbacks(bridge: DriftEventBridge) -> None:
    """Legacy first-match-wins behavior is preserved: the original
    positive_social_fallback_post / positive_social_fallback_engage rules
    sit BEFORE the new geopolitics-pool fallbacks, so legacy callers
    (no event_weights provided) still see positive_social as the default."""
    indexed = {(r.event_type, r.action): i for i, r in enumerate(bridge.rules)}
    legacy_post = indexed[("positive_social", "post")]
    new_post = indexed[("regime_consolidation", "post")]
    assert legacy_post < new_post


# ---- WP1 weighted sampling for geopolitics ------------------------------


def test_geopolitics_drift_event_weights_include_new_events(
    categories: list[dict],
) -> None:
    """Geopolitics category gives the new events the dominant weights
    (≥2.0), per the Sprint 16 plan — regime 3.5 / diplomatic 3.0 / sanctions 2.5."""
    geo = next(c for c in categories if c["id"] == "geopolitics")
    weights = geo["drift_event_weights"]
    assert weights["regime_consolidation"] >= 2.0
    assert weights["diplomatic_stalemate"] >= 2.0
    assert weights["sanctions_pressure"] >= 2.0


def test_weighted_sampling_fires_new_events_for_geopolitics(
    bridge: DriftEventBridge, categories: list[dict],
) -> None:
    """With geopolitics weights applied, the 3 new events together should
    account for a substantial share of fired events on a fallback-path
    decision (post with mid-range traits → no specific rule matches, so
    weighted sampling chooses among all matching rules)."""
    geo = next(c for c in categories if c["id"] == "geopolitics")
    weighted = bridge.with_weights(geo["drift_event_weights"])
    rng = random.Random(42)
    traits = _generic_traits()
    fires: Counter[str] = Counter()
    for _ in range(2000):
        resolved = weighted.event_for(_post(), traits, rng=rng)
        if resolved is not None:
            fires[resolved[0]] += 1
    total = sum(fires.values())
    assert total > 0
    new_event_share = sum(fires[e] for e in NEW_EVENTS) / total
    # geopolitics gives new events 9.0 weight total (3.5+3.0+2.5) vs
    # positive_social 0.3 + negative_social 0.5; in fallback-path samples
    # the new events should dominate decisively.
    assert new_event_share > 0.5, (
        f"new events captured only {new_event_share:.2%} of geopolitics "
        f"fallback fires (expected >50%); fires={dict(fires)}"
    )


def test_all_categories_include_new_event_weights(categories: list[dict]) -> None:
    """Every category must provide weights for all 15 events (no zeros — the
    CategoryRouter validator rejects missing entries; this test guards
    against accidental schema regression)."""
    for cat in categories:
        weights = cat["drift_event_weights"]
        for ev in NEW_EVENTS:
            assert ev in weights, (
                f"category {cat['id']!r} missing drift_event_weights[{ev!r}]"
            )
            assert weights[ev] > 0.0, (
                f"category {cat['id']!r} has non-positive weight for {ev!r}"
            )
