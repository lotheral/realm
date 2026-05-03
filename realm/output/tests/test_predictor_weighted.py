"""Tests for category-weighted predictor consensus (Sprint 11)."""

from __future__ import annotations

from types import SimpleNamespace

from realm.output.category_router import CategoryMatch, default_router
from realm.output.predictor import (
    BranchSpec,
    PredictionEngine,
    observe_category_consensus,
    observe_mean_trait,
    predict,
)


def _category(primary=(), secondary=(), suppressed=(), cid="x") -> CategoryMatch:
    return CategoryMatch(
        category_id=cid, label=cid,
        confidence=1.0, matched_keywords=(),
        primary_traits=tuple(primary),
        secondary_traits=tuple(secondary),
        suppressed_traits=tuple(suppressed),
        default_horizon_ticks=30,
    )


def _fake_sim(traits_dict):
    """Build a SimulationEngine-shaped stub holding agents with given trait
    values. SimpleNamespace is used (not MagicMock) so missing attribute
    lookups raise AttributeError and observe_category_consensus's getattr
    default of 0.5 actually fires."""
    agents = [SimpleNamespace(traits=SimpleNamespace(**vals)) for vals in traits_dict]
    return SimpleNamespace(agents=agents)


class TestObserveCategoryConsensus:
    def test_primary_trait_dominates_consensus(self):
        """A category with one primary + one suppressed should weight the
        primary 8x more than the suppressed (2.0 / 0.25 = 8)."""
        cat = _category(primary=["openness"], suppressed=["empathy"])
        observer = observe_category_consensus(cat)
        # 3 agents, openness=1.0, empathy=0.0
        sim = _fake_sim([
            {"openness": 1.0, "empathy": 0.0},
            {"openness": 1.0, "empathy": 0.0},
            {"openness": 1.0, "empathy": 0.0},
        ])
        # weighted = (2.0 * 1.0 + 0.25 * 0.0) / (2.0 + 0.25) = 2.0 / 2.25 ≈ 0.889
        result = observer(sim)
        assert abs(result - (2.0 / 2.25)) < 1e-6

    def test_suppressed_trait_barely_moves_consensus(self):
        """If only suppressed traits are listed, they fully drive the result."""
        cat = _category(suppressed=["openness"])
        observer = observe_category_consensus(cat)
        sim = _fake_sim([{"openness": 1.0}, {"openness": 0.0}, {"openness": 0.5}])
        # weighted = (0.25 * x) / 0.25 = x — same as plain mean
        result = observer(sim)
        assert abs(result - 0.5) < 1e-6

    def test_different_categories_yield_different_consensus(self):
        """Same population — politics vs sports must produce DIFFERENT means
        because the trait sets and weights differ. This is the whole point."""
        politics = _category(
            primary=["political_spectrum"], secondary=["empathy"],
            suppressed=["risk_appetite"],
        )
        sports = _category(
            primary=["risk_appetite"], secondary=["empathy"],
            suppressed=["political_spectrum"],
        )
        # Population: high political_spectrum, low risk_appetite, neutral empathy
        sim = _fake_sim([{
            "political_spectrum": 0.9, "risk_appetite": 0.2, "empathy": 0.5,
        } for _ in range(5)])
        pol_score = observe_category_consensus(politics)(sim)
        spt_score = observe_category_consensus(sports)(sim)
        assert pol_score != spt_score
        # Politics weights political_spectrum 2.0 — score should be high.
        assert pol_score > 0.6
        # Sports weights risk_appetite 2.0 — score should be low.
        assert spt_score < 0.4

    def test_empty_population_returns_neutral(self):
        cat = _category(primary=["openness"])
        observer = observe_category_consensus(cat)
        sim = SimpleNamespace(agents=[])
        assert observer(sim) == 0.5

    def test_balanced_category_with_no_traits_returns_neutral(self):
        cat = _category()  # no primary/secondary/suppressed
        observer = observe_category_consensus(cat)
        sim = _fake_sim([{"openness": 1.0}])
        assert observer(sim) == 0.5

    def test_handles_missing_trait_attribute_via_default(self):
        cat = _category(primary=["openness", "made_up_trait"])
        observer = observe_category_consensus(cat)
        sim = _fake_sim([{"openness": 1.0}])
        # made_up_trait absent -> default 0.5; weighted (2*1 + 2*0.5)/(2+2) = 0.75
        assert abs(observer(sim) - 0.75) < 1e-6


class TestQuestionRoundTrip:
    def test_predict_with_route_category_attaches_match(self):
        """End-to-end smoke: predict() with route_category=True returns an
        outcome carrying the matched category. Uses a small population to
        keep the test fast."""
        outcome = predict(
            "Will Trump be re-elected in 2028?",
            master_seed=42,
            route_category=True,
        )
        assert outcome.category is not None
        assert outcome.category.category_id == "politics"

    def test_predict_without_route_category_keeps_category_none(self):
        outcome = predict(
            "Will the topic finance dominate?",
            master_seed=42,
            route_category=False,
        )
        assert outcome.category is None

    def test_engine_run_passes_category_through(self):
        cat = default_router().route("Will BTC hit 200K?")
        spec = BranchSpec(
            name="test",
            observe=observe_mean_trait("openness"),
            threshold=0.55,
            horizon_ticks=1,
            n_branches=1,
            n_agents=30,
        )
        engine = PredictionEngine(master_seed=42)
        outcome = engine.run(spec, question="bla", category=cat)
        assert outcome.category is cat
