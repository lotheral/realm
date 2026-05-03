"""Sprint 19.2 hotfix — delta decomposition tests.

The dual-blend-weight design (Sprint 19 WP1) introduces a mechanical
shift component into the scenario delta because baseline weights
(LLM-dominant) and scenario weights (sim-dominant) put different
emphasis on the same LLM prior. The decomposition splits the total
delta into:

    delta_total = delta_blend_shift + delta_sim_movement

where ``delta_blend_shift`` is what the probability would have moved
just by switching weights (sim staying at the baseline level), and
``delta_sim_movement`` is the residual — the actual simulation
response to the perturbation.

These tests exercise ``_blend_with_llm_prior`` directly and verify
the decomposition math, without spinning up the full predict
pipeline (the integration tests in ``test_calibration_spread.py``
exercise the wired path).
"""

from __future__ import annotations

import pytest

from realm.api.predict import _blend_with_llm_prior

# ---- Decomposition math ---------------------------------------------------


def test_decomposition_sums_to_total() -> None:
    """delta_blend_shift + delta_sim_movement == delta_total"""
    llm_prior = 0.32
    baseline_sim = 0.50
    scenario_sim = 0.45
    baseline_w_llm = 0.90
    scenario_w_llm = 0.40

    baseline_prob, _ = _blend_with_llm_prior(baseline_sim, llm_prior, baseline_w_llm)
    scenario_prob, _ = _blend_with_llm_prior(scenario_sim, llm_prior, scenario_w_llm)
    mechanical, _ = _blend_with_llm_prior(baseline_sim, llm_prior, scenario_w_llm)

    delta_total = scenario_prob - baseline_prob
    delta_blend_shift = mechanical - baseline_prob
    delta_sim_movement = scenario_prob - mechanical

    assert abs((delta_blend_shift + delta_sim_movement) - delta_total) < 1e-9


def test_blend_shift_positive_when_llm_prior_below_half() -> None:
    """LLM prior < 0.5 + sim ≈ 0.5 → switching from LLM-dominant
    to sim-dominant blend mechanically pulls probability UP toward 0.5."""
    llm_prior = 0.30
    baseline_sim = 0.50
    baseline_w = 0.90
    scenario_w = 0.40

    baseline_prob, _ = _blend_with_llm_prior(baseline_sim, llm_prior, baseline_w)
    mechanical, _ = _blend_with_llm_prior(baseline_sim, llm_prior, scenario_w)
    delta_blend_shift = mechanical - baseline_prob

    assert delta_blend_shift > 0


def test_blend_shift_negative_when_llm_prior_above_half() -> None:
    """LLM prior > 0.5 + sim ≈ 0.5 → switching to sim-dominant blend
    mechanically pulls probability DOWN toward 0.5."""
    llm_prior = 0.75
    baseline_sim = 0.50
    baseline_w = 0.90
    scenario_w = 0.40

    baseline_prob, _ = _blend_with_llm_prior(baseline_sim, llm_prior, baseline_w)
    mechanical, _ = _blend_with_llm_prior(baseline_sim, llm_prior, scenario_w)
    delta_blend_shift = mechanical - baseline_prob

    assert delta_blend_shift < 0


def test_blend_shift_is_zero_when_weights_equal() -> None:
    """Same blend weight for baseline and scenario → no mechanical shift."""
    llm_prior = 0.32
    baseline_sim = 0.50

    baseline_prob, _ = _blend_with_llm_prior(baseline_sim, llm_prior, 0.5)
    mechanical, _ = _blend_with_llm_prior(baseline_sim, llm_prior, 0.5)
    assert abs(mechanical - baseline_prob) < 1e-9


def test_blend_shift_is_zero_when_llm_prior_equals_sim() -> None:
    """When LLM prior matches the sim probability, ANY weight change
    leaves the blended result unchanged → mechanical shift is zero."""
    llm_prior = 0.50
    baseline_sim = 0.50
    baseline_w = 0.90
    scenario_w = 0.40

    baseline_prob, _ = _blend_with_llm_prior(baseline_sim, llm_prior, baseline_w)
    mechanical, _ = _blend_with_llm_prior(baseline_sim, llm_prior, scenario_w)
    assert abs(mechanical - baseline_prob) < 1e-9


def test_decomposition_matches_iran_example() -> None:
    """Sprint 19.2 motivating example. LLM_prior = 0.32, baseline_sim ≈
    0.50, scenario_sim ≈ 0.45 (mild downward sim response). Expected
    decomposition: blend_shift ≈ +9pp (mechanical), sim_movement ≈ -3pp."""
    llm_prior = 0.32
    baseline_sim = 0.50
    scenario_sim = 0.45

    baseline_prob, _ = _blend_with_llm_prior(baseline_sim, llm_prior, 0.90)
    scenario_prob, _ = _blend_with_llm_prior(scenario_sim, llm_prior, 0.40)
    mechanical, _ = _blend_with_llm_prior(baseline_sim, llm_prior, 0.40)

    delta_blend_shift = mechanical - baseline_prob
    delta_sim_movement = scenario_prob - mechanical

    # baseline = 0.90 × 0.32 + 0.10 × 0.50 = 0.338
    # mechanical = 0.40 × 0.32 + 0.60 × 0.50 = 0.428
    # scenario = 0.40 × 0.32 + 0.60 × 0.45 = 0.398
    # blend_shift = 0.428 - 0.338 = +0.090 (+9pp mechanical)
    # sim_movement = 0.398 - 0.428 = -0.030 (-3pp sim)
    assert delta_blend_shift == pytest.approx(0.090, abs=1e-3)
    assert delta_sim_movement == pytest.approx(-0.030, abs=1e-3)
    assert (delta_blend_shift + delta_sim_movement) == pytest.approx(
        scenario_prob - baseline_prob, abs=1e-9,
    )
