"""Sprint 18 WP2 — LLM-driven web research for question priors.

The Sprint 17 LLM prior used the model's training data only — leading
to historical-base-rate answers that miss current context (e.g. the
Strait of Hormuz transit collapse, where REALM said 58% but Polymarket
priced 32% based on real-time IMF Portwatch data).

This module wires an optional web search step BEFORE the question
analyzer's LLM call. The LLM generates 2-3 targeted queries → search
provider returns snippets → snippets are concatenated into a context
string → context is injected into the question-analysis prompt so
the LLM prior reflects current conditions.

Search providers:
- ``tavily`` (https://tavily.com) — purpose-built for LLM workflows,
  returns clean JSON with ``content`` snippets. Set
  ``REALM_WEB_SEARCH_PROVIDER=tavily`` and ``TAVILY_API_KEY=...``.
- ``brave`` (https://api.search.brave.com) — generous free tier. Set
  ``REALM_WEB_SEARCH_PROVIDER=brave`` and ``BRAVE_API_KEY=...``.
- ``none`` (default) — silently skip web research. The engine works
  exactly like Sprint 17 in this case (LLM prior = training data only).

When the search call fails (network, rate limit, malformed response)
the researcher returns ``None`` and the question analyzer falls
through to the no-web-context path — graceful degrade everywhere.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx

from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_split_prompt

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SEC = 8.0
_MAX_QUERIES = 3
_MAX_RESULTS_PER_QUERY = 4
_MAX_SNIPPET_CHARS = 400          # truncate long snippets
_MAX_CONTEXT_CHARS = 4000         # cap total context fed to LLM


@dataclass(frozen=True)
class WebResearchSource:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebResearchResult:
    queries: tuple[str, ...]
    sources: tuple[WebResearchSource, ...]
    context: str               # concatenated context for LLM prompt
    provider: str              # "tavily" | "brave" | "none"


# ---- Search-provider backends ----------------------------------------------


class _SearchBackend:
    name: str = "abstract"

    def search(self, query: str, max_results: int) -> list[WebResearchSource]:
        raise NotImplementedError


class TavilyBackend(_SearchBackend):
    name = "tavily"
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
                 client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = client if client is not None else httpx.Client(timeout=timeout_sec)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, query: str, max_results: int) -> list[WebResearchSource]:
        body = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }
        resp = self._client.post(self.ENDPOINT, json=body)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, Mapping):
            return []
        results = data.get("results")
        if not isinstance(results, list):
            return []
        out: list[WebResearchSource] = []
        for r in results[:max_results]:
            if not isinstance(r, Mapping):
                continue
            url = str(r.get("url", "")).strip()
            title = str(r.get("title", "")).strip()
            content = str(r.get("content", "")).strip()
            if not url or not content:
                continue
            out.append(WebResearchSource(
                title=title[:200], url=url, snippet=content[:_MAX_SNIPPET_CHARS],
            ))
        return out


class BraveBackend(_SearchBackend):
    name = "brave"
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
                 client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = client if client is not None else httpx.Client(timeout=timeout_sec)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, query: str, max_results: int) -> list[WebResearchSource]:
        headers = {
            "X-Subscription-Token": self._api_key,
            "Accept": "application/json",
        }
        params = {"q": query, "count": str(max_results)}
        resp = self._client.get(self.ENDPOINT, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, Mapping):
            return []
        web = data.get("web", {})
        results = web.get("results") if isinstance(web, Mapping) else None
        if not isinstance(results, list):
            return []
        out: list[WebResearchSource] = []
        for r in results[:max_results]:
            if not isinstance(r, Mapping):
                continue
            url = str(r.get("url", "")).strip()
            title = str(r.get("title", "")).strip()
            description = str(r.get("description", "")).strip()
            if not url or not description:
                continue
            out.append(WebResearchSource(
                title=title[:200], url=url, snippet=description[:_MAX_SNIPPET_CHARS],
            ))
        return out


def _build_search_backend() -> _SearchBackend | None:
    """Read env vars and construct the configured backend, or return
    None when no search provider is set up. Importing this module is
    safe regardless of env state.

    Sprint 19 hotfix: when ``REALM_WEB_SEARCH_PROVIDER`` is unset but
    a provider key is present (``TAVILY_API_KEY`` or ``BRAVE_API_KEY``),
    auto-detect the provider. Avoids the foot-gun where a user adds a
    key to .env but forgets the provider line.
    """
    provider = os.environ.get("REALM_WEB_SEARCH_PROVIDER", "").strip().lower()
    if not provider:
        if os.environ.get("TAVILY_API_KEY", "").strip():
            provider = "tavily"
        elif os.environ.get("BRAVE_API_KEY", "").strip():
            provider = "brave"
    if provider == "tavily":
        key = os.environ.get("TAVILY_API_KEY", "").strip()
        if not key:
            logger.warning("REALM_WEB_SEARCH_PROVIDER=tavily but TAVILY_API_KEY is empty")
            return None
        logger.info("[REALM] Web research ACTIVE — provider=tavily")
        return TavilyBackend(api_key=key)
    if provider == "brave":
        key = os.environ.get("BRAVE_API_KEY", "").strip()
        if not key:
            logger.warning("REALM_WEB_SEARCH_PROVIDER=brave but BRAVE_API_KEY is empty")
            return None
        logger.info("[REALM] Web research ACTIVE — provider=brave")
        return BraveBackend(api_key=key)
    return None  # not configured = silent skip


# ---- Researcher orchestrator ----------------------------------------------


@dataclass
class WebResearcher:
    """Orchestrates query generation + multi-query search + context build."""

    llm_backend: ILLMBackend | None
    search_backend: _SearchBackend | None = None
    max_queries: int = _MAX_QUERIES
    max_results_per_query: int = _MAX_RESULTS_PER_QUERY
    _seen_urls: set[str] = field(default_factory=set, init=False)

    def is_available(self) -> bool:
        """True when both an LLM (for query gen) and a search backend
        are wired. Callers can short-circuit rather than constructing
        a no-op researcher path."""
        return self.llm_backend is not None and self.search_backend is not None

    def research(self, question: str, category_id: str) -> WebResearchResult | None:
        """Returns a populated ``WebResearchResult`` or None on any
        failure path. Caller treats None as "no web context — use
        training data only."""
        if not self.is_available():
            return None

        # 1. LLM generates targeted queries
        queries = self._generate_queries(question, category_id)
        if not queries:
            return None

        # 2. Execute searches, dedupe by URL
        sources: list[WebResearchSource] = []
        self._seen_urls.clear()
        for q in queries:
            try:
                results = self.search_backend.search(q, self.max_results_per_query)
            except (httpx.HTTPError, LLMBackendError, ValueError) as e:
                logger.warning("web search failed for query %r (%s); skipping", q, e)
                continue
            for r in results:
                if r.url in self._seen_urls:
                    continue
                self._seen_urls.add(r.url)
                sources.append(r)

        if not sources:
            logger.info("web research returned no usable sources")
            return None

        # 3. Build context string for the question-analysis prompt
        context = _build_context(sources)

        return WebResearchResult(
            queries=tuple(queries),
            sources=tuple(sources),
            context=context,
            provider=self.search_backend.name,
        )

    def _generate_queries(self, question: str, category_id: str) -> list[str]:
        try:
            prompt = load_split_prompt("web_researcher/generate_queries")
        except Exception as e:
            logger.warning("query-generation prompt load failed (%s)", e)
            return []
        user = prompt.render_user(question=question, category_id=category_id)
        try:
            data = self.llm_backend.complete_json(
                prompt.system, user, temperature=0.3, max_tokens=512,
            )
        except (LLMBackendError, ValueError, KeyError) as e:
            logger.warning("query generation LLM call failed (%s)", e)
            return []
        if not isinstance(data, Mapping):
            return []
        raw = data.get("queries", [])
        if not isinstance(raw, Sequence):
            return []
        out = [str(q).strip() for q in raw if isinstance(q, str) and q.strip()]
        return out[:self.max_queries]


def _build_context(sources: list[WebResearchSource]) -> str:
    """Concatenate sources into a context block for the LLM prompt.
    Truncated at ``_MAX_CONTEXT_CHARS`` to fit the model's budget."""
    parts: list[str] = []
    used = 0
    for i, s in enumerate(sources, 1):
        block = f"[{i}] {s.title}\n  {s.snippet}\n  source: {s.url}\n"
        if used + len(block) > _MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        used += len(block)
    return "".join(parts)


def default_web_researcher(llm_backend: ILLMBackend | None) -> WebResearcher:
    """Build the production WebResearcher: env-configured search backend
    + caller-provided LLM. Returns a researcher that .is_available()
    iff both pieces are wired."""
    search_backend = _build_search_backend()
    return WebResearcher(llm_backend=llm_backend, search_backend=search_backend)
