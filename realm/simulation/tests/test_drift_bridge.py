"""Tests for Sprint 10 WP3 — config-driven DriftEventBridge + new event types."""

from __future__ import annotations

from pathlib import Path

import pytest

from realm.agents.decision import Decision
from realm.personality.trait_vector import TraitVector
from realm.simulation.drift import (
    _BASE_DRIFT_COEFFICIENT,
    DriftEventBridge,
    ExperienceDriftEngine,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "drift_events.json"


@pytest.fixture
def bridge() -> DriftEventBridge:
    return DriftEventBridge.from_json(CONFIG_PATH)


@pytest.fixture
def traits() -> TraitVector:
    """Mid-range trait vector that fires fallbacks on most rules."""
    return TraitVector.from_dict({
        "empathy": 0.5,
        "agreeableness": 0.5,
        "social_dominance": 0.3,
        "neuroticism": 0.3,
        "contrarian_tendency": 0.3,
        "herd_susceptibility": 0.3,
        "individualism": 0.5,
        "analytical_depth": 0.5,
        "openness": 0.5,
        "risk_appetite": 0.3,
        "loss_aversion": 0.3,
        "financial_optimism": 0.5,
        "spirituality": 0.3,
        "tradition_vs_progress": 0.5,
        "persuasion_skill": 0.4,
        "communication_assertiveness": 0.4,
        "authority_compliance": 0.4,
        "impulsivity": 0.3,
        "patience": 0.5,
        "fomo_susceptibility": 0.3,
        "information_sharing": 0.5,
    })


def _post(topic: str, sentiment: float = 0.5, virality: float = 1.0) -> Decision:
    return Decision(
        action="post", topic=topic, sentiment=sentiment,
        virality=virality, political_lean=0.5,
    )


def _engage(kind: str = "like") -> Decision:
    return Decision(action="engage", target_post_id="p1", engagement_kind=kind)


# ---- Bridge rule-matching ------------------------------------------------


class TestLeadershipAct:
    def test_fires_on_political_post_with_high_dominance(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        high = traits.apply_modifier({"social_dominance": 0.4})  # 0.3 -> 0.7
        event = bridge.event_for(_post("politics", sentiment=0.5), high)
        assert event is not None and event[0] == "leadership_act"

    def test_does_not_fire_on_low_dominance(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        event = bridge.event_for(_post("politics", sentiment=0.5), traits)
        assert event is not None and event[0] != "leadership_act"

    def test_trait_weights_reinforce_dominance(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        engine = ExperienceDriftEngine(event_map=bridge.event_map)
        engine.record_event("a", "leadership_act", 1.0, traits)
        drift = engine.drift_vector("a")
        assert drift["social_dominance"] > 0
        assert drift["authority_compliance"] < 0  # leader doesn't defer


class TestGroupConformityAndDissent:
    def test_conformity_fires_on_share_with_high_herd(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        herder = traits.apply_modifier({"herd_susceptibility": 0.3})  # 0.3->0.6
        event = bridge.event_for(_engage("share"), herder)
        assert event is not None and event[0] == "group_conformity"

    def test_dissent_fires_on_political_post_with_high_contrarian(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        dissenter = traits.apply_modifier({"contrarian_tendency": 0.4})  # 0.3->0.7
        event = bridge.event_for(_post("politics", sentiment=-0.4), dissenter)
        assert event is not None and event[0] == "group_dissent"

    def test_conformity_opposes_dissent_in_weights(self, bridge: DriftEventBridge) -> None:
        conformity = bridge.event_map["group_conformity"]
        dissent = bridge.event_map["group_dissent"]
        # Signs should be opposite on herd_susceptibility / individualism
        assert conformity["herd_susceptibility"] > 0
        assert dissent["individualism"] > 0
        assert conformity["contrarian_tendency"] < 0
        assert dissent["contrarian_tendency"] > 0


class TestFinancialEvents:
    def test_financial_gain_fires_on_positive_finance_post_with_risk(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        risky = traits.apply_modifier({"risk_appetite": 0.5})  # 0.3->0.8
        event = bridge.event_for(_post("finance", sentiment=0.3), risky)
        assert event is not None and event[0] == "financial_gain"

    def test_financial_loss_fires_on_finance_post_with_high_loss_aversion(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        cautious = traits.apply_modifier({"loss_aversion": 0.5})  # 0.3->0.8
        event = bridge.event_for(_post("finance", sentiment=-0.1), cautious)
        assert event is not None and event[0] == "financial_loss"

    def test_gain_weights_reinforce_optimism_loss_weights_reinforce_aversion(
        self, bridge: DriftEventBridge,
    ) -> None:
        gain = bridge.event_map["financial_gain"]
        loss = bridge.event_map["financial_loss"]
        assert gain["financial_optimism"] > 0
        assert gain["loss_aversion"] < 0
        assert loss["loss_aversion"] > 0
        assert loss["financial_optimism"] < 0


class TestCulturalExperience:
    def test_fires_on_culture_post_with_high_spirituality(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        spiritual = traits.apply_modifier({"spirituality": 0.4})  # 0.3->0.7
        event = bridge.event_for(_post("culture", sentiment=0.2), spiritual)
        # leadership_act could preempt — verify social_dominance is low enough
        assert spiritual.social_dominance < 0.6
        assert event is not None and event[0] == "cultural_experience"

    def test_weights_reinforce_spirituality(self, bridge: DriftEventBridge) -> None:
        cult = bridge.event_map["cultural_experience"]
        assert cult["spirituality"] > 0
        assert cult["openness"] > 0


class TestKnowledgeAcquisitionEvents:
    def test_fires_on_tech_post_with_high_analytical_depth(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        smart = traits.apply_modifier({"analytical_depth": 0.3})  # 0.5->0.8
        event = bridge.event_for(_post("tech", sentiment=0.2), smart)
        assert event is not None and event[0] == "knowledge_acquisition"

    def test_fires_lightly_on_engage_with_high_analytical(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        smart = traits.apply_modifier({"analytical_depth": 0.2})  # 0.5->0.7
        event = bridge.event_for(_engage("like"), smart)
        # engagement knowledge rule has intensity 0.3, lighter than the post one
        assert event is not None
        assert event[0] == "knowledge_acquisition"
        assert event[1] < 0.5


class TestRiskEvents:
    def test_successful_risk_fires_on_viral_post_with_risk_appetite(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        risky = traits.apply_modifier({"risk_appetite": 0.5})  # 0.3->0.8
        # Use personal topic so finance rules don't preempt
        event = bridge.event_for(_post("personal", sentiment=0.3, virality=2.0), risky)
        assert event is not None and event[0] == "successful_risk"

    def test_failed_risk_fires_on_timid_post_with_risk_appetite(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        risky = traits.apply_modifier({"risk_appetite": 0.5})  # 0.3->0.8
        event = bridge.event_for(_post("personal", sentiment=0.0, virality=0.8), risky)
        assert event is not None and event[0] == "failed_risk"


class TestStressCrisis:
    def test_fires_on_distressed_negative_post(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        neurotic = traits.apply_modifier({"neuroticism": 0.6})  # 0.3->0.9
        event = bridge.event_for(_post("personal", sentiment=-0.7), neurotic)
        assert event is not None and event[0] == "stress_crisis"


class TestFallbacks:
    def test_normal_post_falls_back_to_positive_social(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        event = bridge.event_for(_post("personal", sentiment=0.4), traits)
        assert event is not None and event[0] == "positive_social"

    def test_sad_post_falls_back_to_negative_social(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        event = bridge.event_for(_post("personal", sentiment=-0.5), traits)
        assert event is not None and event[0] == "negative_social"

    def test_engage_falls_back_to_positive_social(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        event = bridge.event_for(_engage("like"), traits)
        assert event is not None and event[0] == "positive_social"

    def test_lurk_emits_no_event(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        assert bridge.event_for(Decision(action="lurk"), traits) is None


class TestFirstMatchWins:
    def test_leadership_preempts_dissent(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        # High social_dominance AND high contrarian_tendency AND positive politics post
        strong = traits.apply_modifier({
            "social_dominance": 0.5,        # 0.3 -> 0.8
            "contrarian_tendency": 0.5,     # 0.3 -> 0.8
        })
        event = bridge.event_for(_post("politics", sentiment=0.4), strong)
        assert event is not None and event[0] == "leadership_act"

    def test_financial_gain_preempts_loss_on_mixed_signals(
        self, bridge: DriftEventBridge, traits: TraitVector,
    ) -> None:
        both = traits.apply_modifier({
            "risk_appetite": 0.5,      # 0.3 -> 0.8
            "loss_aversion": 0.5,      # 0.3 -> 0.8
        })
        # Positive sentiment on finance — gain rule is declared before loss rule
        event = bridge.event_for(_post("finance", sentiment=0.3), both)
        assert event is not None and event[0] == "financial_gain"


# ---- Config + engine-integration smoke tests -----------------------------


class TestConfigLoading:
    def test_default_loads_from_config_path(self) -> None:
        b = DriftEventBridge.default()
        # The 6 Sprint 9 types + 6 Sprint 10 types
        for name in [
            "positive_social", "negative_social",
            "successful_risk", "failed_risk",
            "knowledge_acquisition", "stress_crisis",
            "leadership_act", "group_conformity", "group_dissent",
            "financial_loss", "financial_gain", "cultural_experience",
        ]:
            assert name in b.event_map, f"missing event type: {name}"

    def test_rules_are_compiled_in_declaration_order(
        self, bridge: DriftEventBridge,
    ) -> None:
        # First rule is leadership_act by construction
        assert bridge.rules[0].event_type == "leadership_act"
        # Sprint 16: original Sprint 10 fallbacks (positive_social_fallback_post,
        # positive_social_fallback_engage) sit between the specific rules and
        # the new geopolitics-pool fallbacks (regime_consolidation_*,
        # diplomatic_stalemate_*, sanctions_pressure_*). Last rule is now
        # sanctions_pressure_engage — the final entry in the declaration.
        assert bridge.rules[-1].event_type == "sanctions_pressure"
        assert bridge.rules[-1].action == "engage"


class TestNewEventTraitDirections:
    """For each new event type, verify its weights push traits as documented."""

    @pytest.mark.parametrize("event,up_trait,down_trait", [
        ("leadership_act",      "social_dominance",  "authority_compliance"),
        ("group_conformity",    "herd_susceptibility", "contrarian_tendency"),
        ("group_dissent",       "contrarian_tendency", "agreeableness"),
        ("financial_loss",      "loss_aversion",      "financial_optimism"),
        ("financial_gain",      "financial_optimism", "loss_aversion"),
        ("cultural_experience", "spirituality",       None),
    ])
    def test_trait_directions(
        self, bridge: DriftEventBridge, traits: TraitVector,
        event: str, up_trait: str, down_trait: str | None,
    ) -> None:
        engine = ExperienceDriftEngine(event_map=bridge.event_map)
        engine.record_event("a", event, 1.0, traits)
        drift = engine.drift_vector("a")
        assert drift[up_trait] > 0, f"{event} should push {up_trait} up"
        if down_trait is not None:
            assert drift[down_trait] < 0, f"{event} should push {down_trait} down"


class TestMaxDriftRatioStillClampsNewEvents:
    """WP3 must not break the Sprint 9 cumulative ratio cap."""

    def test_cumulative_cap_holds_for_leadership_act(self, traits: TraitVector) -> None:
        bridge = DriftEventBridge.default()
        engine = ExperienceDriftEngine(max_drift_ratio=0.10, event_map=bridge.event_map)
        # 500 events — would overflow linearly without the cap
        for _ in range(500):
            engine.record_event("a", "leadership_act", 1.0, traits)
        drift = engine.drift_vector("a")
        # social_dominance original 0.3 -> cap +0.03
        assert drift["social_dominance"] <= 0.30 * 0.10 + 1e-9

    def test_cumulative_cap_holds_for_financial_loss(self, traits: TraitVector) -> None:
        bridge = DriftEventBridge.default()
        engine = ExperienceDriftEngine(max_drift_ratio=0.10, event_map=bridge.event_map)
        for _ in range(500):
            engine.record_event("a", "financial_loss", 1.0, traits)
        drift = engine.drift_vector("a")
        # loss_aversion original 0.3 -> cap +0.03
        assert drift["loss_aversion"] == pytest.approx(0.30 * 0.10, abs=1e-6)


class TestLegacyBehaviourUnchanged:
    """Sprint 9 behaviour must remain intact when no bridge is installed."""

    def test_default_event_map_matches_sprint9(self, traits: TraitVector) -> None:
        engine = ExperienceDriftEngine()
        engine.record_event("a", "positive_social", 1.0, traits)
        # positive_social: empathy +1.0 * 0.01 intensity=1.0 -> +0.01
        assert engine.drift_vector("a")["empathy"] == pytest.approx(
            1.0 * _BASE_DRIFT_COEFFICIENT
        )

    def test_legacy_event_from_decision_still_works(self) -> None:
        from realm.simulation.drift import event_from_decision
        assert event_from_decision("post", 0.5) == "positive_social"
        assert event_from_decision("post", -0.3) == "negative_social"
        assert event_from_decision("engage", None) == "positive_social"
        assert event_from_decision("lurk", None) is None


class TestBuildEngine:
    """Sprint 20 — DriftEventBridge.build_engine() makes the
    bridge/engine event_map invariant unbreakable by construction."""

    def test_engine_carries_the_bridges_full_event_map(self, bridge) -> None:
        engine = bridge.build_engine()
        assert set(engine.event_map) == set(bridge.event_map)
        # Full catalog, not the 6-event legacy literal.
        assert "leadership_act" in engine.event_map

    def test_volatility_couples_cap_and_intensity(self, bridge) -> None:
        engine = bridge.build_engine(drift_volatility=1.6)
        assert engine.max_drift_ratio == pytest.approx(0.16)
        assert engine.intensity_scale == pytest.approx(1.6)

    def test_asymmetry_and_primaries_are_wired(self, bridge) -> None:
        engine = bridge.build_engine(
            drift_volatility=0.5,
            positive_multiplier=1.3,
            negative_multiplier=0.7,
            primary_traits=("confidence", "optimism"),
        )
        assert engine.positive_multiplier == pytest.approx(1.3)
        assert engine.negative_multiplier == pytest.approx(0.7)
        assert engine.primary_trait_set == frozenset({"confidence", "optimism"})

    def test_defaults_preserve_sprint14_neutral_knobs(self, bridge) -> None:
        engine = bridge.build_engine()
        assert engine.max_drift_ratio == pytest.approx(0.10)
        assert engine.intensity_scale == pytest.approx(1.0)
        assert engine.positive_multiplier == pytest.approx(1.0)
        assert engine.negative_multiplier == pytest.approx(1.0)
        assert engine.primary_trait_set == frozenset()
