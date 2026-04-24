"""Tests for runtime fallback behaviour."""

from __future__ import annotations

import pytest

from realm.llm.fallback import FallbackBackend
from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse


class Scripted(ILLMBackend):
    """Returns a canned response OR raises a pre-arranged exception."""

    def __init__(self, name: str, behaviour):
        self._name = name
        self._behaviour = behaviour   # str = canned content, or Exception to raise
        self.calls = 0

    @property
    def backend_name(self): return self._name
    @property
    def model(self): return f"{self._name}-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.calls += 1
        if isinstance(self._behaviour, Exception):
            raise self._behaviour
        return LLMResponse(content=self._behaviour, model=self.model)


class TestFallbackBackend:
    def test_primary_success_no_fallback_call(self):
        primary = Scripted("openai", "primary ok")
        secondary = Scripted("moonshot", "secondary ok")
        wrapper = FallbackBackend(primary=primary, fallbacks=[secondary])

        resp = wrapper.complete("sys", "hi")
        assert resp.content == "primary ok"
        assert primary.calls == 1
        assert secondary.calls == 0

    def test_primary_failure_falls_back(self):
        primary = Scripted("openai", RuntimeError("boom"))
        secondary = Scripted("moonshot", "rescued")
        wrapper = FallbackBackend(primary=primary, fallbacks=[secondary])

        resp = wrapper.complete("sys", "hi")
        assert resp.content == "rescued"
        assert primary.calls == 1
        assert secondary.calls == 1

    def test_chain_of_failures(self):
        primary = Scripted("openai", RuntimeError("a"))
        second = Scripted("moonshot", RuntimeError("b"))
        third = Scripted("ollama", "third-rescued")
        wrapper = FallbackBackend(primary=primary, fallbacks=[second, third])

        resp = wrapper.complete("sys", "hi")
        assert resp.content == "third-rescued"
        assert primary.calls == 1 and second.calls == 1 and third.calls == 1

    def test_all_fail_raises(self):
        primary = Scripted("openai", RuntimeError("a"))
        second = Scripted("moonshot", RuntimeError("b"))
        wrapper = FallbackBackend(primary=primary, fallbacks=[second])

        with pytest.raises(LLMBackendError, match="all 2 backends failed"):
            wrapper.complete("sys", "hi")

    def test_backend_name_shows_chain(self):
        primary = Scripted("openai", "x")
        second = Scripted("moonshot", "y")
        wrapper = FallbackBackend(primary=primary, fallbacks=[second])
        assert wrapper.backend_name == "fallback[openai→moonshot]"

    def test_model_reports_primary(self):
        primary = Scripted("openai", "x")
        second = Scripted("moonshot", "y")
        wrapper = FallbackBackend(primary=primary, fallbacks=[second])
        assert wrapper.model == "openai-1"

    def test_complete_json_via_wrapper(self):
        """complete_json defined on ABC should work through the wrapper."""
        primary = Scripted("openai", RuntimeError("bad"))
        second = Scripted("moonshot", '{"ok": 1}')
        wrapper = FallbackBackend(primary=primary, fallbacks=[second])
        data = wrapper.complete_json("sys", "hi")
        assert data == {"ok": 1}


class TestRouterIntegration:
    def test_router_wraps_different_primary_and_fallback(self, monkeypatch):
        """When primary and fallback differ and both build, router yields FallbackBackend."""
        import realm.llm.router as router_mod

        calls = {"build": []}

        def fake_build(name):
            calls["build"].append(name)
            return Scripted(name, f"{name}-ok")

        monkeypatch.setattr(router_mod, "build_backend", fake_build)
        monkeypatch.setattr(router_mod, "_resolve_backend_name", lambda task: "openai")

        r = router_mod.LLMRouter(fallback_backend="moonshot")
        backend = r.for_task("personality")
        assert isinstance(backend, FallbackBackend)
        assert backend.primary.backend_name == "openai"
        assert backend.fallbacks[0].backend_name == "moonshot"

    def test_router_no_wrap_when_same_primary_and_fallback(self, monkeypatch):
        import realm.llm.router as router_mod

        def fake_build(name):
            return Scripted(name, "ok")

        monkeypatch.setattr(router_mod, "build_backend", fake_build)
        monkeypatch.setattr(router_mod, "_resolve_backend_name", lambda task: "moonshot")

        r = router_mod.LLMRouter(fallback_backend="moonshot")
        backend = r.for_task("personality")
        # Primary == fallback → no wrapper (plain Scripted)
        assert not isinstance(backend, FallbackBackend)

    def test_router_falls_back_at_build_time_still_works(self, monkeypatch):
        """If primary can't build (no API key), router uses fallback directly."""
        import realm.llm.router as router_mod

        def fake_build(name):
            if name == "openai":
                raise LLMBackendError("openai: API key missing")
            return Scripted(name, "ok")

        monkeypatch.setattr(router_mod, "build_backend", fake_build)
        monkeypatch.setattr(router_mod, "_resolve_backend_name", lambda task: "openai")

        r = router_mod.LLMRouter(fallback_backend="moonshot")
        backend = r.for_task("personality")
        # Build-time fallback: plain Moonshot, no FallbackBackend wrapper.
        assert not isinstance(backend, FallbackBackend)
        assert backend.backend_name == "moonshot"
