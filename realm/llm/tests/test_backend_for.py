"""Sprint 20 — centralized LLM gate semantics (realm.llm.router.backend_for).

Before Sprint 20, predict.py used bare-truthiness on the gate env var while
category_router.py parsed it strictly — so ``REALM_LLM_CATEGORY_BACKEND=0``
produced a half-LLM state (router off, analyzers on). These tests pin the
single strict interpretation everything now shares.
"""

from __future__ import annotations

import pytest

from realm.llm.router import backend_for, env_gate_enabled

_GATE = "REALM_LLM_CATEGORY_BACKEND"


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_gate_truthy_values_enable(monkeypatch, value) -> None:
    monkeypatch.setenv(_GATE, value)
    assert env_gate_enabled(_GATE) is True


@pytest.mark.parametrize("value", ["0", "false", "off", "no", "", "  ", "enabled"])
def test_gate_other_values_disable(monkeypatch, value) -> None:
    monkeypatch.setenv(_GATE, value)
    assert env_gate_enabled(_GATE) is False


def test_gate_unset_disables(monkeypatch) -> None:
    monkeypatch.delenv(_GATE, raising=False)
    assert env_gate_enabled(_GATE) is False


def test_backend_for_returns_none_when_gate_off_despite_key(monkeypatch) -> None:
    """The half-LLM regression: gate=0 with a valid key must yield NO backend."""
    monkeypatch.setenv(_GATE, "0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert backend_for("category") is None


def test_backend_for_returns_none_when_no_key(monkeypatch) -> None:
    monkeypatch.setenv(_GATE, "1")
    for var in ("OPENAI_API_KEY", "MOONSHOT_API_KEY", "OLLAMA_HOST"):
        monkeypatch.delenv(var, raising=False)
    assert backend_for("category") is None


def test_backend_for_swallows_construction_errors(monkeypatch) -> None:
    """Gate open + key present but router construction blows up → None,
    never an exception escaping to the caller."""
    monkeypatch.setenv(_GATE, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import realm.llm.router as router_mod

    class _Boom:
        def for_task(self, task):
            raise RuntimeError("backend construction failed")

    monkeypatch.setattr(router_mod, "LLMRouter", lambda: _Boom())
    assert backend_for("category") is None
