"""Backend + router tests using a MockLLMBackend — no network calls."""

from __future__ import annotations

import json

import pytest

from realm.llm.interfaces import ILLMBackend, InMemoryCache, LLMBackendError, LLMResponse
from realm.llm.router import LLMRouter, build_backend


class MockLLMBackend(ILLMBackend):
    """Canned-response backend for unit tests."""

    def __init__(self, name: str = "mock", model: str = "mock-1",
                 canned: str = '{"ok": true}'):
        self._name = name
        self._model = model
        self._canned = canned
        self.calls: list[tuple[str, str, bool]] = []

    @property
    def backend_name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls.append((system, user, json_mode))
        return LLMResponse(content=self._canned, model=self._model, tokens_in=10, tokens_out=20)


class TestMockBackendFlow:
    def test_complete_returns_canned(self):
        b = MockLLMBackend(canned="hello world")
        r = b.complete("sys", "hi")
        assert r.content == "hello world"
        assert len(b.calls) == 1

    def test_complete_json_parses(self):
        b = MockLLMBackend(canned='{"x": 1, "y": 2}')
        data = b.complete_json("sys", "hi")
        assert data == {"x": 1, "y": 2}

    def test_complete_json_tolerates_prose(self):
        b = MockLLMBackend(canned='Sure! {"key": 42}')
        data = b.complete_json("sys", "hi")
        assert data == {"key": 42}

    def test_complete_json_rejects_bad_output(self):
        b = MockLLMBackend(canned="totally not json")
        with pytest.raises(LLMBackendError):
            b.complete_json("sys", "hi")


class TestBuildBackend:
    def test_unknown_name_raises(self):
        with pytest.raises(LLMBackendError):
            build_backend("pigeon-transfer")

    def test_openai_requires_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(LLMBackendError, match="API key"):
            build_backend("openai")

    def test_moonshot_requires_key(self, monkeypatch):
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        with pytest.raises(LLMBackendError, match="API key"):
            build_backend("moonshot")


class TestRouter:
    def test_fallback_when_primary_missing(self, monkeypatch):
        """If configured backend is unavailable, router falls back."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        monkeypatch.setenv("REALM_LLM_PERSONALITY_BACKEND", "openai")
        router = LLMRouter(fallback_backend="moonshot")
        with pytest.raises(LLMBackendError):
            # Both unavailable — should raise
            router.for_task("personality")

    def test_cached_instance_reuse(self):
        router = LLMRouter()
        router._instances["personality"] = MockLLMBackend("m1")
        a = router.for_task("personality")
        b = router.for_task("personality")
        assert a is b


class TestCacheInBackend:
    """Verify the backend caches responses per prompt+model."""

    def test_cache_hit_marked(self):
        class CountingBackend(ILLMBackend):
            def __init__(self):
                self._call_count = 0
                self._cache = InMemoryCache()

            @property
            def backend_name(self): return "counter"
            @property
            def model(self): return "c-1"

            def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
                from realm.llm.interfaces import prompt_key
                key = prompt_key(system, user, self.model, json_mode, temperature)
                cached = self._cache.get(key)
                if cached is not None:
                    return LLMResponse(content=cached.content, model=cached.model, cached=True)
                self._call_count += 1
                r = LLMResponse(content=json.dumps({"n": self._call_count}), model=self.model)
                self._cache.set(key, r)
                return r

        b = CountingBackend()
        r1 = b.complete("sys", "q")
        r2 = b.complete("sys", "q")
        assert r1.cached is False
        assert r2.cached is True
        assert b._call_count == 1
