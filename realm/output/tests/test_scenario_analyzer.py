"""Sprint 17 WP3 — ScenarioAnalyzer tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse
from realm.output.category_router import CategoryRouter
from realm.output.scenario_analyzer import (
    _AFFECTED_PCT_CLAMP,
    _TRAIT_IMPACT_CLAMP,
    ScenarioAnalyzer,
)


class _ScriptedBackend(ILLMBackend):
    def __init__(self, response: Mapping[str, Any] | None = None,
                 raises: Exception | None = None):
        self._response = response
        self._raises = raises
        self.calls = 0

    @property
    def backend_name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return "scripted-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return LLMResponse(
            content=json.dumps(self._response or {}), model=self.model,
        )


_GEOPOLITICS = CategoryRouter(llm_backend=None).route(
    "Will there be a military conflict between major powers before 2030?"
)


_VALID_RESPONSE = {
    "event_summary": "DOJ files amicus brief supporting Musks antitrust claims",
    "direction": "increases",
    "magnitude": "moderate",
    "trait_impacts": {
        "authority_compliance": 0.05,
        "analytical_depth": 0.04,
        "contrarian_tendency": -0.03,
    },
    "affected_population_pct": 0.7,
    "reasoning": "DOJ involvement signals federal-level support that shifts authority-compliant agents toward the plaintiffs side.",
}


# ---- Direction handling ----------------------------------------------------


def test_positive_scenario_direction_increases() -> None:
    backend = _ScriptedBackend(_VALID_RESPONSE)
    a = ScenarioAnalyzer(backend).analyze("DOJ files brief", "q", _GEOPOLITICS)
    assert a is not None
    assert a.direction == "increases"
    assert a.magnitude == "moderate"


def test_negative_scenario_direction_decreases() -> None:
    resp = dict(_VALID_RESPONSE, direction="decreases")
    a = ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "Negative news", "q", _GEOPOLITICS,
    )
    assert a is not None and a.direction == "decreases"


def test_mixed_scenario_direction_accepted() -> None:
    resp = dict(_VALID_RESPONSE, direction="mixed")
    a = ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "Ambiguous news", "q", _GEOPOLITICS,
    )
    assert a is not None and a.direction == "mixed"


def test_invalid_direction_returns_none() -> None:
    """Direction not in {increases, decreases, mixed} → analysis rejected."""
    resp = dict(_VALID_RESPONSE, direction="upward")
    assert ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "x", "q", _GEOPOLITICS,
    ) is None


# ---- Trait_impacts sanitization -------------------------------------------


def test_trait_impacts_clamped_to_pm_015() -> None:
    """LLM-returned values outside ±0.15 are clamped, not rejected."""
    resp = dict(
        _VALID_RESPONSE,
        trait_impacts={
            "authority_compliance": 0.5,    # over upper clamp
            "risk_appetite": -0.9,          # under lower clamp
            "analytical_depth": 0.1,        # in-range
        },
    )
    a = ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "x", "q", _GEOPOLITICS,
    )
    assert a is not None
    impacts = a.trait_impacts_dict
    assert impacts["authority_compliance"] == _TRAIT_IMPACT_CLAMP[1]
    assert impacts["risk_appetite"] == _TRAIT_IMPACT_CLAMP[0]
    assert impacts["analytical_depth"] == 0.1


def test_invalid_trait_names_dropped() -> None:
    resp = dict(
        _VALID_RESPONSE,
        trait_impacts={
            "nonexistent_trait": 0.1,
            "also_fake": 0.05,
            "authority_compliance": 0.04,
        },
    )
    a = ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "x", "q", _GEOPOLITICS,
    )
    assert a is not None
    assert a.trait_impacts_dict == {"authority_compliance": 0.04}


def test_all_trait_names_hallucinated_returns_none() -> None:
    """If every trait_impact key is invalid, the analysis is unusable."""
    resp = dict(
        _VALID_RESPONSE,
        trait_impacts={"fake_a": 0.1, "fake_b": 0.05},
    )
    assert ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "x", "q", _GEOPOLITICS,
    ) is None


# ---- affected_population_pct clamping -------------------------------------


def test_affected_population_clamped() -> None:
    """Values outside [0.1, 0.95] are clamped."""
    resp_high = dict(_VALID_RESPONSE, affected_population_pct=1.5)
    resp_low = dict(_VALID_RESPONSE, affected_population_pct=-0.2)
    high = ScenarioAnalyzer(_ScriptedBackend(resp_high)).analyze(
        "x", "q", _GEOPOLITICS,
    )
    low = ScenarioAnalyzer(_ScriptedBackend(resp_low)).analyze(
        "x", "q", _GEOPOLITICS,
    )
    assert high is not None and high.affected_population_pct == _AFFECTED_PCT_CLAMP[1]
    assert low is not None and low.affected_population_pct == _AFFECTED_PCT_CLAMP[0]


# ---- Graceful degradation -------------------------------------------------


def test_returns_none_when_llm_unavailable() -> None:
    assert ScenarioAnalyzer(llm_backend=None).analyze(
        "feed", "q", _GEOPOLITICS,
    ) is None


def test_returns_none_on_llm_error() -> None:
    backend = _ScriptedBackend(raises=LLMBackendError("network down"))
    assert ScenarioAnalyzer(backend).analyze(
        "feed", "q", _GEOPOLITICS,
    ) is None
    assert backend.calls == 1


def test_empty_feed_returns_none() -> None:
    backend = _ScriptedBackend(_VALID_RESPONSE)
    assert ScenarioAnalyzer(backend).analyze("   ", "q", _GEOPOLITICS) is None
    assert backend.calls == 0  # didn't even hit the LLM


def test_invalid_magnitude_defaults_to_moderate() -> None:
    """Unrecognized magnitude is salvaged with a safe default."""
    resp = dict(_VALID_RESPONSE, magnitude="catastrophic")
    a = ScenarioAnalyzer(_ScriptedBackend(resp)).analyze(
        "x", "q", _GEOPOLITICS,
    )
    assert a is not None and a.magnitude == "moderate"
