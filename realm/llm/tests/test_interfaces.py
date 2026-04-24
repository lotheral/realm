"""Tests for LLM interface layer: cache, retry, JSON extraction."""

from __future__ import annotations

import pytest

from realm.core.exceptions import REALMError
from realm.llm.interfaces import (
    InMemoryCache,
    LLMBackendError,
    LLMResponse,
    _extract_first_json,
    prompt_key,
    retry_with_backoff,
)


class TestPromptKey:
    def test_same_inputs_same_key(self):
        a = prompt_key("sys", "user", "gpt", False, 0.3)
        b = prompt_key("sys", "user", "gpt", False, 0.3)
        assert a == b

    def test_different_inputs_different_keys(self):
        assert prompt_key("a", "u", "m", False, 0.0) != prompt_key("b", "u", "m", False, 0.0)
        assert prompt_key("s", "a", "m", False, 0.0) != prompt_key("s", "b", "m", False, 0.0)

    def test_temperature_rounded(self):
        """Small numerical drift in temperature shouldn't invalidate cache."""
        assert prompt_key("s", "u", "m", False, 0.30001) == prompt_key("s", "u", "m", False, 0.30)


class TestInMemoryCache:
    def test_get_miss_returns_none(self):
        c = InMemoryCache()
        assert c.get("k") is None

    def test_set_get(self):
        c = InMemoryCache()
        r = LLMResponse(content="x", model="m")
        c.set("k", r)
        assert c.get("k") is r

    def test_max_size_evicts(self):
        c = InMemoryCache(max_size=3)
        for i in range(5):
            c.set(f"k{i}", LLMResponse(content=f"v{i}", model="m"))
        assert len(c) == 3


class TestRetry:
    def test_returns_on_success(self):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return 42
        assert retry_with_backoff(fn, attempts=3, base_delay=0.01) == 42
        assert call_count == 1

    def test_retries_transient(self):
        calls = []
        class FakeRateLimitError(Exception):
            pass
        def fn():
            calls.append(1)
            if len(calls) < 2:
                raise FakeRateLimitError("boom")
            return "ok"
        result = retry_with_backoff(fn, attempts=3, base_delay=0.01)
        assert result == "ok"
        assert len(calls) == 2

    def test_gives_up_on_non_transient(self):
        class RegularError(ValueError):
            pass
        def fn():
            raise RegularError("nope")
        with pytest.raises(RegularError):
            retry_with_backoff(fn, attempts=3, base_delay=0.01)


class TestJSONExtraction:
    def test_plain_json(self):
        assert _extract_first_json('{"a": 1}') == {"a": 1}

    def test_json_in_prose(self):
        text = 'Sure! Here is the result: {"trait": 0.5, "other": 0.7} — hope it helps.'
        assert _extract_first_json(text) == {"trait": 0.5, "other": 0.7}

    def test_handles_quoted_braces(self):
        text = 'Prose { "key": "{inside}" } done'
        assert _extract_first_json(text) == {"key": "{inside}"}

    def test_no_json_returns_none(self):
        assert _extract_first_json("just some words") is None


class TestLLMBackendErrorHierarchy:
    def test_is_realm_error(self):
        assert issubclass(LLMBackendError, REALMError)
