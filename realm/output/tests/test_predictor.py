"""Tests for PredictionEngine + QuestionParser."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from realm.output.predictor import (
    BranchSpec,
    PredictionEngine,
    QuestionParser,
    observe_engagement_rate,
    observe_mean_trait,
    observe_topic_share,
)


class TestQuestionParser:
    def test_topic_dominance(self):
        p = QuestionParser().parse("Will tech dominate the topic mix?")
        assert p.spec.name == "tech_share"

    def test_trait_question(self):
        p = QuestionParser().parse("Will mean empathy rise above 0.7 in 10 ticks?")
        assert p.spec.name == "mean_empathy"
        assert p.spec.threshold == 0.7
        assert p.spec.horizon_ticks == 10

    def test_engagement(self):
        p = QuestionParser().parse("Will engagement rate stay above 1.5?")
        assert p.spec.name == "engagement_rate"
        assert p.spec.threshold == 1.5

    def test_fallback_to_default(self):
        p = QuestionParser().parse("What's the weather?")
        # Falls back to financial_optimism
        assert p.spec.name == "mean_financial_optimism"

    def test_agent_count_extraction(self):
        p = QuestionParser().parse("Will tech dominate with 500 agents in 20 ticks?")
        assert p.spec.n_agents == 500
        assert p.spec.horizon_ticks == 20


class TestObservers:
    def test_mean_trait_observer(self):
        """Observer should read a specific trait from all agents."""
        # Smoke-level: sim must run through PredictionEngine branches
        engine = PredictionEngine(master_seed=42)
        spec = BranchSpec(
            name="mean_empathy",
            observe=observe_mean_trait("empathy"),
            threshold=0.55,
            horizon_ticks=2,
            n_branches=2,
            n_agents=30,
        )
        outcome = engine.run(spec, question="Will mean empathy rise?")
        assert len(outcome.branch_values) == 2
        for v in outcome.branch_values:
            assert 0.0 <= v <= 1.0

    def test_topic_share_observer(self):
        engine = PredictionEngine(master_seed=42)
        spec = BranchSpec(
            name="tech_share",
            observe=observe_topic_share("tech"),
            threshold=0.25,
            horizon_ticks=2,
            n_branches=2,
            n_agents=30,
        )
        outcome = engine.run(spec)
        for v in outcome.branch_values:
            assert 0.0 <= v <= 1.0


class TestPredictionEngineDeterminism:
    def test_same_inputs_same_outcome(self):
        engine = PredictionEngine(master_seed=42)
        spec = BranchSpec(
            name="eng_rate",
            observe=observe_engagement_rate(),
            threshold=1.0,
            horizon_ticks=2,
            n_branches=2,
            n_agents=30,
        )
        a = engine.run(spec)
        b = engine.run(spec)
        assert a.branch_values == b.branch_values
        assert a.probability == b.probability
