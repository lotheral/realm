"""Sprint 17 WP1 — LLM-first category routing tests.

These tests use ``MockLLMBackend``-style stubs (subclass ``ILLMBackend``,
return canned JSON) so the test suite stays hermetic. NO test calls the
real LLM API.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

import pytest

from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse
from realm.output.category_router import CategoryRouter


class _ScriptedBackend(ILLMBackend):
    """Hermetic backend returning a pre-set JSON dict."""

    def __init__(self, response: Mapping[str, Any]):
        self._response = response
        self.calls = 0

    @property
    def backend_name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return "scripted-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls += 1
        return LLMResponse(
            content=json.dumps(self._response),
            model=self.model,
            cached=False,
        )


class _SleepyBackend(ILLMBackend):
    """Hermetic backend that sleeps before responding — used to test
    the per-call timeout path in CategoryRouter."""

    def __init__(self, sleep_sec: float, response: Mapping[str, Any]):
        self._sleep = sleep_sec
        self._response = response
        self.calls = 0

    @property
    def backend_name(self) -> str:
        return "sleepy"

    @property
    def model(self) -> str:
        return "sleepy-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls += 1
        time.sleep(self._sleep)
        return LLMResponse(content=json.dumps(self._response), model=self.model)


class _RaisingBackend(ILLMBackend):
    """Hermetic backend that raises an LLMBackendError on every call."""

    def __init__(self):
        self.calls = 0

    @property
    def backend_name(self) -> str:
        return "raising"

    @property
    def model(self) -> str:
        return "raising-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls += 1
        raise LLMBackendError("simulated backend failure")


# ---- Routing decisions: LLM is primary --------------------------------------


def test_legal_question_routes_to_politics_via_llm() -> None:
    """The original Sprint 17 motivating example. Pre-Sprint-17 the keyword
    'win' would have routed this to sports. With LLM-first, the classifier
    correctly identifies it as a legal/political dispute."""
    backend = _ScriptedBackend({
        "category": "politics",
        "subcategory": "legislation",
        "confidence": 0.9,
        "reasoning": "Legal dispute between two individuals — antitrust case",
    })
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will Elon Musk win his case against Sam Altman?")
    assert m.category_id == "politics"
    assert m.llm_used is True
    assert m.confidence == pytest.approx(0.9)
    assert backend.calls == 1


def test_keyword_only_question_still_routes_correctly() -> None:
    """A question that keyword-routes cleanly to crypto: the LLM should
    agree (and confirms via the mock). Result is crypto either way."""
    backend = _ScriptedBackend({"category": "crypto", "confidence": 0.95})
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will Bitcoin hit 200K by end of 2026?")
    assert m.category_id == "crypto"
    assert m.llm_used is True


def test_llm_low_confidence_falls_back_to_keyword() -> None:
    """LLM picks politics with confidence 0.3 (< 0.5 floor) → router
    consults keyword path; the strong sports keyword match wins."""
    backend = _ScriptedBackend({"category": "politics", "confidence": 0.3})
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will the Lakers win the championship final this season?")
    assert backend.calls == 1
    assert m.category_id == "sports"
    assert m.llm_used is False


def test_llm_invalid_category_falls_back_to_keyword() -> None:
    """LLM returns a category id not in config → keyword fallback runs."""
    backend = _ScriptedBackend({"category": "nonexistent", "confidence": 0.9})
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will the Lakers win the championship final this season?")
    assert backend.calls == 1
    assert m.category_id == "sports"  # keyword fallback caught the hit
    assert m.llm_used is False


def test_llm_timeout_falls_back_to_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the LLM call exceeds the per-route timeout, keyword routing
    runs as fallback. Monkeypatches the timeout constant to 0.05s and
    pairs with a backend that sleeps 0.3s."""
    import realm.output.category_router as cr_mod
    monkeypatch.setattr(cr_mod, "_LLM_ROUTE_TIMEOUT_SEC", 0.05)
    backend = _SleepyBackend(0.3, {"category": "politics", "confidence": 0.9})
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will the Lakers win the championship final this season?")
    assert m.category_id == "sports"  # keyword fallback
    assert m.llm_used is False


def test_llm_error_falls_back_to_keyword() -> None:
    """LLM raises any LLMBackendError → keyword fallback runs."""
    backend = _RaisingBackend()
    router = CategoryRouter(llm_backend=backend)
    m = router.route("Will the Lakers win the championship final this season?")
    assert backend.calls == 1
    assert m.category_id == "sports"
    assert m.llm_used is False


# ---- Caching ---------------------------------------------------------------


def test_route_with_llm_caches_repeated_questions() -> None:
    """Repeating the same question hits the in-process cache; backend
    is called only once."""
    backend = _ScriptedBackend({"category": "politics", "confidence": 0.9})
    router = CategoryRouter(llm_backend=backend)
    q = "Will Elon Musk win his case against Sam Altman?"
    m1 = router.route(q)
    m2 = router.route(q)
    assert backend.calls == 1
    assert m1.category_id == m2.category_id == "politics"
    assert m1.llm_used and m2.llm_used


def test_cache_keyed_by_normalized_question() -> None:
    """Two questions differing only in whitespace / casing map to the
    same cache entry — proves normalization happens before cache lookup."""
    backend = _ScriptedBackend({"category": "politics", "confidence": 0.9})
    router = CategoryRouter(llm_backend=backend)
    router.route("Will Musk win his case?")
    router.route("  WILL MUSK WIN HIS CASE?  ")
    assert backend.calls == 1


# ---- No-LLM path (degradation) ---------------------------------------------


def test_route_unchanged_when_llm_backend_none() -> None:
    """Router constructed with llm_backend=None → keyword routing path;
    behavior identical to the pre-Sprint-17 default."""
    router = CategoryRouter(llm_backend=None)
    m = router.route("Will the Lakers win the championship final this season?")
    assert m.category_id == "sports"
    assert m.llm_used is False


def test_legal_keyword_expansion_works_without_llm() -> None:
    """Sprint 17 also expanded the politics keyword list with legal terms.
    Without an LLM, a question about an antitrust lawsuit settlement
    should now keyword-route correctly to politics."""
    router = CategoryRouter(llm_backend=None)
    m = router.route("Will the antitrust lawsuit between the DOJ and Google settle this year?")
    assert m.category_id == "politics"
    assert m.llm_used is False
