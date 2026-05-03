"""Sprint 18 WP2 — WebResearcher tests.

Hermetic — uses ``MockLLMBackend`` for query generation and a
hand-rolled ``_FakeSearchBackend`` so no live API calls.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse
from realm.llm.web_researcher import (
    WebResearcher,
    WebResearchResult,
    WebResearchSource,
    _build_context,
    _SearchBackend,
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


class _FakeSearchBackend(_SearchBackend):
    name = "fake"

    def __init__(self, results: list[WebResearchSource] | Exception):
        self._results = results
        self.calls: list[str] = []

    def search(self, query: str, max_results: int) -> list[WebResearchSource]:
        self.calls.append(query)
        if isinstance(self._results, Exception):
            raise self._results
        return self._results[:max_results]


_QUERIES_RESPONSE = {
    "queries": [
        "Strait of Hormuz transit volume current 2026",
        "Hormuz tanker insurance war risk premium latest",
        "Iran US military escalation Hormuz May 2026",
    ],
}


def _make_sources(n: int) -> list[WebResearchSource]:
    return [
        WebResearchSource(
            title=f"Source {i}",
            url=f"https://example.com/article-{i}",
            snippet=f"Snippet body for source {i} with relevant facts.",
        )
        for i in range(1, n + 1)
    ]


# ---- Availability ---------------------------------------------------------


def test_is_available_false_without_llm() -> None:
    r = WebResearcher(llm_backend=None, search_backend=_FakeSearchBackend(_make_sources(3)))
    assert r.is_available() is False
    assert r.research("q", "geopolitics") is None


def test_is_available_false_without_search_backend() -> None:
    r = WebResearcher(llm_backend=_ScriptedBackend(_QUERIES_RESPONSE), search_backend=None)
    assert r.is_available() is False
    assert r.research("q", "geopolitics") is None


def test_is_available_true_with_both() -> None:
    r = WebResearcher(
        llm_backend=_ScriptedBackend(_QUERIES_RESPONSE),
        search_backend=_FakeSearchBackend(_make_sources(3)),
    )
    assert r.is_available() is True


# ---- Happy path -----------------------------------------------------------


def test_research_returns_populated_result() -> None:
    sources = _make_sources(3)
    fake_search = _FakeSearchBackend(sources)
    llm = _ScriptedBackend(_QUERIES_RESPONSE)
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    result = r.research("Will Hormuz reopen?", "geopolitics")
    assert result is not None
    assert isinstance(result, WebResearchResult)
    assert len(result.queries) == 3
    assert len(result.sources) == 3
    assert "Source 1" in result.context
    assert result.provider == "fake"
    # LLM called exactly once for query gen
    assert llm.calls == 1


def test_research_dedupes_urls_across_queries() -> None:
    """Same URL appearing in multiple search results is collected only once."""
    duplicate_source = WebResearchSource(
        title="Dupe", url="https://example.com/same", snippet="x",
    )
    fake_search = _FakeSearchBackend([duplicate_source])
    llm = _ScriptedBackend(_QUERIES_RESPONSE)
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    result = r.research("q", "cat")
    assert result is not None
    assert len(result.sources) == 1  # deduped despite 3 queries


def test_research_truncates_context_to_budget() -> None:
    """A flood of long snippets is truncated at _MAX_CONTEXT_CHARS."""
    long_sources = [
        WebResearchSource(
            title=f"S{i}",
            url=f"https://example.com/{i}",
            snippet="X" * 1000,  # huge snippet
        )
        for i in range(20)
    ]
    fake_search = _FakeSearchBackend(long_sources)
    llm = _ScriptedBackend(_QUERIES_RESPONSE)
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    result = r.research("q", "cat")
    assert result is not None
    assert len(result.context) <= 4500  # _MAX_CONTEXT_CHARS=4000 + small overhead


# ---- Failure paths --------------------------------------------------------


def test_research_returns_none_when_query_gen_fails() -> None:
    llm = _ScriptedBackend(raises=LLMBackendError("network down"))
    fake_search = _FakeSearchBackend(_make_sources(3))
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    assert r.research("q", "cat") is None
    assert fake_search.calls == []  # never reached search


def test_research_returns_none_when_query_response_malformed() -> None:
    llm = _ScriptedBackend({"unrelated": "stuff"})
    fake_search = _FakeSearchBackend(_make_sources(3))
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    assert r.research("q", "cat") is None


def test_research_returns_none_when_all_searches_fail() -> None:
    llm = _ScriptedBackend(_QUERIES_RESPONSE)
    fake_search = _FakeSearchBackend(LLMBackendError("search 500"))
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    assert r.research("q", "cat") is None


def test_research_returns_none_when_no_usable_sources() -> None:
    """Search succeeded but returned 0 results."""
    llm = _ScriptedBackend(_QUERIES_RESPONSE)
    fake_search = _FakeSearchBackend([])
    r = WebResearcher(llm_backend=llm, search_backend=fake_search)
    assert r.research("q", "cat") is None


# ---- _build_context helper ------------------------------------------------


def test_build_context_includes_url_and_snippet() -> None:
    sources = [WebResearchSource(
        title="T1", url="https://a.com", snippet="snippet1",
    )]
    ctx = _build_context(sources)
    assert "T1" in ctx
    assert "snippet1" in ctx
    assert "https://a.com" in ctx


def test_build_context_handles_empty_list() -> None:
    assert _build_context([]) == ""
