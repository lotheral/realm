"""Sprint 17 WP2 — QuestionAnalyzer tests.

Hermetic — all tests use a scripted ``ILLMBackend`` stub. No real LLM
calls.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse
from realm.output.category_router import CategoryRouter
from realm.output.question_analyzer import QuestionAnalysis, QuestionAnalyzer


class _ScriptedBackend(ILLMBackend):
    def __init__(self, response: Mapping[str, Any] | None = None,
                 raises: Exception | None = None,
                 raw: str | None = None):
        self._response = response
        self._raises = raises
        self._raw = raw
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
        body = self._raw if self._raw is not None else json.dumps(self._response or {})
        return LLMResponse(content=body, model=self.model)


_VALID_RESPONSE = {
    "subject": "Musk vs Altman antitrust case",
    "outcome_variable": "Musk wins the case",
    "yes_means": "The court rules in favor of Musk's antitrust claims.",
    "no_means": "The case is dismissed or Altman/OpenAI prevails.",
    "key_factors": [
        "DOJ involvement",
        "judge's track record on antitrust",
        "strength of internal OpenAI documents",
    ],
    "relevant_traits": [
        "authority_compliance", "analytical_depth", "contrarian_tendency",
    ],
    "time_horizon": "months",
    "llm_prior": 0.32,
    "prior_reasoning": "Antitrust suits against major tech firms historically succeed about 30% of the time.",
}


def _category(question: str = "Will Musk win his case?"):
    """Use the production router (no LLM) to get a real CategoryMatch
    with a realistic category_id/label/primary_traits."""
    router = CategoryRouter(llm_backend=None)
    return router.route(question)


# ---- Happy path -------------------------------------------------------------


def test_analyze_returns_full_analysis_with_mock_llm() -> None:
    backend = _ScriptedBackend(_VALID_RESPONSE)
    analyzer = QuestionAnalyzer(backend)
    cat = _category()
    a = analyzer.analyze("Will Musk win his case?", cat)
    assert a is not None
    assert a.subject == "Musk vs Altman antitrust case"
    assert a.llm_prior == 0.32
    assert "DOJ involvement" in a.key_factors
    assert a.time_horizon == "months"
    assert a.category_id == cat.category_id


# ---- Validation / sanitization ---------------------------------------------


def test_llm_prior_clamped_to_unit_interval() -> None:
    """LLM returning prior > 0.95 or < 0.05 is clamped, not rejected."""
    high = dict(_VALID_RESPONSE, llm_prior=1.5)
    low = dict(_VALID_RESPONSE, llm_prior=-0.2)
    cat = _category()
    a_high = QuestionAnalyzer(_ScriptedBackend(high)).analyze("q", cat)
    a_low = QuestionAnalyzer(_ScriptedBackend(low)).analyze("q", cat)
    assert a_high is not None and a_high.llm_prior == 0.95
    assert a_low is not None and a_low.llm_prior == 0.05


def test_relevant_traits_filtered_to_valid_names() -> None:
    """Hallucinated trait names are silently dropped from relevant_traits."""
    bad = dict(
        _VALID_RESPONSE,
        relevant_traits=["nonexistent_trait", "also_fake", "analytical_depth"],
    )
    a = QuestionAnalyzer(_ScriptedBackend(bad)).analyze("q", _category())
    assert a is not None
    assert a.relevant_traits == ("analytical_depth",)


def test_invalid_time_horizon_defaults_to_unknown() -> None:
    bad = dict(_VALID_RESPONSE, time_horizon="aeons")
    a = QuestionAnalyzer(_ScriptedBackend(bad)).analyze("q", _category())
    assert a is not None
    assert a.time_horizon == "unknown"


# ---- Graceful degradation --------------------------------------------------


def test_analyze_returns_none_when_llm_unavailable() -> None:
    """No backend wired → analyze() returns None (caller uses minimal())."""
    analyzer = QuestionAnalyzer(llm_backend=None)
    assert analyzer.analyze("q", _category()) is None


def test_analyze_returns_none_on_llm_error() -> None:
    """LLM raises → analyze() catches and returns None."""
    backend = _ScriptedBackend(raises=LLMBackendError("network down"))
    analyzer = QuestionAnalyzer(backend)
    assert analyzer.analyze("q", _category()) is None
    assert backend.calls == 1


def test_analyze_returns_none_on_malformed_json_schema() -> None:
    """LLM returns JSON without llm_prior → analyze() returns None."""
    backend = _ScriptedBackend({"unrelated": "stuff"})
    assert QuestionAnalyzer(backend).analyze("q", _category()) is None


# ---- Minimal degradation construction --------------------------------------


def test_minimal_carries_only_routing_fields() -> None:
    cat = _category()
    a = QuestionAnalysis.minimal("Will X happen?", cat)
    assert a.original_question == "Will X happen?"
    assert a.category_id == cat.category_id
    assert a.category_label == cat.label
    # All LLM-derived fields are None
    assert a.subject is None
    assert a.llm_prior is None
    assert a.relevant_traits == ()
    assert a.key_factors == ()
