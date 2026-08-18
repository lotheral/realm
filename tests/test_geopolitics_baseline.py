"""Sprint 16 WP4: small-scale geopolitics baseline regression test.

The full <49.5% acceptance gate is exercised by
`scripts/calibrate_categories.py` at 200×30×10 with `geopolitics mean < 50%`
asserted. This test guards against gross geopolitics-baseline regression
in the CI fast-path (50×10×3 — too small to assert <49.5% reliably, but
tight enough to catch a return to the >51% Sprint 14 baseline).
"""

from __future__ import annotations

from realm.api.predict import PredictRequest, predict_endpoint

GEOPOLITICS_QUESTION = "Will NATO expand further before 2030?"
# Sprint 20: the scenario text must carry lexically-clear sentiment.
# The old wording ("military exercises... carrier groups") parsed as
# neutral, and the pre-Sprint-20 code masked that by fabricating a +0.08
# positive nudge on neutral parses. That fabrication is gone (neutral →
# zero perturbation, honestly no delta), so this test's escalation
# scenario now says what an escalation headline actually says.
GEOPOLITICS_SCENARIO = (
    "China launches major military exercises around Taiwan, US deploys "
    "three carrier groups in response; fears of open conflict and a "
    "threat of regional war escalate."
)


def _run(question: str, *, scenario_feed: str | None = None) -> float:
    req = PredictRequest(
        question=question,
        n_agents=50,
        n_ticks=10,
        n_branches=3,
        master_seed=42,
        scenario_feed=scenario_feed,
    )
    return predict_endpoint(req).probability


def test_geopolitics_baseline_below_50_5pct_at_small_scale() -> None:
    """At 50×10×3 the new drift events have only ~10 ticks to push the
    population, so we relax the production <49.5% target to <50.5%.
    A regression to the Sprint 14 baseline (>51%) is still caught."""
    p = _run(GEOPOLITICS_QUESTION)
    assert p < 0.505, (
        f"geopolitics baseline {p*100:.2f}% above 50.5% — Sprint 16 "
        f"structural fix regressed (Sprint 15 hotfix sat at 50.10%)."
    )


def test_geopolitics_scenario_delta_is_meaningful() -> None:
    """Injecting a clear escalation scenario should move the geopolitics
    probability — the magnitude depends on agent count and ticks but the
    direction and absolute size must clear noise."""
    baseline = _run(GEOPOLITICS_QUESTION)
    with_scenario = _run(GEOPOLITICS_QUESTION, scenario_feed=GEOPOLITICS_SCENARIO)
    delta = with_scenario - baseline
    assert abs(delta) > 0.01, (
        f"geopolitics scenario delta {delta*100:+.2f}pp is below noise floor "
        f"(baseline={baseline*100:.2f}%, scenario={with_scenario*100:.2f}%)"
    )
