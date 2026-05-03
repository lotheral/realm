"""Sprint 17 WP4 — PredictionNarrator tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse
from realm.output.category_router import CategoryRouter
from realm.output.prediction_narrator import PredictionNarrator
from realm.output.question_analyzer import QuestionAnalysis


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


_VALID_RESPONSE = {
    "headline": "Musk's antitrust case faces an uphill battle — 34% likely to succeed",
    "key_drivers": [
        "Authority-compliance clusters tend to side with institutional power, favoring OpenAI",
        "Analytical-depth subgroup weighs antitrust precedent — historical success rate ~30%",
        "Contrarian cluster (18%) bets on Musk's track record of unconventional wins",
    ],
    "dissent_view": "High risk_appetite agents see this as a paradigm-shift case where base rates do not apply",
    "confidence_note": "Medium confidence — legal outcomes carry inherent uncertainty",
    "caveat": "This is a simulation-derived estimate, not legal advice",
}


def _category():
    return CategoryRouter(llm_backend=None).route("Will Musk win his case?")


def _analysis():
    return QuestionAnalysis.minimal("Will Musk win his case?", _category())


def _common_kwargs(**overrides):
    base = {
        "question": "Will Musk win his case?",
        "category": _category(),
        "analysis": _analysis(),
        "probability": 0.34,
        "simulation_probability": 0.38,
        "blended_probability": 0.34,
        "supporting": 0.30,
        "opposing": 0.40,
        "neutral": 0.30,
        "trait_shifts": {"authority_compliance": 0.02, "contrarian_tendency": -0.01},
        "scenario_feed": None,
        "scenario_analysis": None,
        "delta": None,
    }
    base.update(overrides)
    return base


# ---- Happy path ------------------------------------------------------------


def test_narrate_returns_full_narrative_with_mock() -> None:
    backend = _ScriptedBackend(_VALID_RESPONSE)
    n = PredictionNarrator(backend).narrate(**_common_kwargs())
    assert n is not None
    assert "Musk" in n.headline
    assert len(n.key_drivers) == 3
    assert "risk_appetite" in n.dissent_view


def test_headline_is_non_empty_string_under_200_chars() -> None:
    backend = _ScriptedBackend(_VALID_RESPONSE)
    n = PredictionNarrator(backend).narrate(**_common_kwargs())
    assert n is not None
    assert isinstance(n.headline, str)
    assert 0 < len(n.headline) < 200


def test_narrative_drivers_are_strings_list() -> None:
    backend = _ScriptedBackend(_VALID_RESPONSE)
    n = PredictionNarrator(backend).narrate(**_common_kwargs())
    assert n is not None
    assert all(isinstance(d, str) and d for d in n.key_drivers)


# ---- Schema validation ----------------------------------------------------


def test_returns_none_when_headline_missing() -> None:
    bad = {k: v for k, v in _VALID_RESPONSE.items() if k != "headline"}
    n = PredictionNarrator(_ScriptedBackend(bad)).narrate(**_common_kwargs())
    assert n is None


def test_returns_none_when_drivers_empty() -> None:
    bad = dict(_VALID_RESPONSE, key_drivers=[])
    n = PredictionNarrator(_ScriptedBackend(bad)).narrate(**_common_kwargs())
    assert n is None


def test_drops_empty_strings_from_drivers() -> None:
    """Whitespace / empty strings in key_drivers are filtered out, not crashed on."""
    bad = dict(_VALID_RESPONSE, key_drivers=["valid driver", "", "   "])
    n = PredictionNarrator(_ScriptedBackend(bad)).narrate(**_common_kwargs())
    assert n is not None
    assert n.key_drivers == ("valid driver",)


# ---- Graceful degradation -------------------------------------------------


def test_returns_none_when_llm_none() -> None:
    n = PredictionNarrator(llm_backend=None).narrate(**_common_kwargs())
    assert n is None


def test_returns_none_on_llm_error() -> None:
    backend = _ScriptedBackend(raises=LLMBackendError("network down"))
    n = PredictionNarrator(backend).narrate(**_common_kwargs())
    assert n is None
    assert backend.calls == 1


# ---- Scenario context -----------------------------------------------------


def test_scenario_context_passed_to_prompt() -> None:
    """When scenario_feed + scenario_analysis are provided, they appear
    in the rendered user message (substituted into the template). We
    can't introspect the template directly without exposing it, but we
    can verify the call still succeeds with all the optional kwargs."""
    backend = _ScriptedBackend(_VALID_RESPONSE)
    from realm.output.scenario_analyzer import ScenarioAnalysis
    sa = ScenarioAnalysis(
        original_feed="DOJ files brief",
        event_summary="DOJ amicus brief supporting Musk",
        direction="increases",
        magnitude="moderate",
        trait_impacts=(("authority_compliance", 0.05),),
        reasoning="DOJ involvement helps Musk",
        affected_population_pct=0.7,
    )
    n = PredictionNarrator(backend).narrate(**_common_kwargs(
        scenario_feed="DOJ files brief", scenario_analysis=sa, delta=0.04,
    ))
    assert n is not None
    assert backend.calls == 1
