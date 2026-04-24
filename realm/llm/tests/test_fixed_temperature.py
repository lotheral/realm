"""Tests for the fixed-temperature model detection + reactive retry."""

from __future__ import annotations

import pytest

from realm.llm.openai_backend import (
    _is_max_completion_tokens_rejection,
    _is_max_tokens_rejection,
    _is_temperature_rejection,
    _max_tokens_param_name,
    _model_accepts_custom_temperature,
    _try_fix_bad_kwargs,
)


class TestFixedTemperatureDetection:
    @pytest.mark.parametrize("model", [
        "o1", "o1-preview", "o1-mini", "o3", "o3-mini", "o4-preview",
        "kimi-k2", "kimi-k2.6", "kimi-k2-0905-preview", "kimi-k3-base",
        "gpt-5.5", "gpt-5.5-turbo",
    ])
    def test_known_fixed_temp_models(self, model):
        assert _model_accepts_custom_temperature(model) is False

    @pytest.mark.parametrize("model", [
        "gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-5", "gpt-5.4", "gpt-5-turbo",
        "moonshot-v1-8k", "moonshot-v1-32k", "kimi-latest", "kimi-k1",
        "llama-3-70b", "qwen2.5:14b",
    ])
    def test_regular_models_accept_custom_temperature(self, model):
        assert _model_accepts_custom_temperature(model) is True

    def test_empty_model_name_tolerated(self):
        assert _model_accepts_custom_temperature("") is True


class TestTemperatureRejectionMatcher:
    def test_moonshot_error_matches(self):
        err = Exception(
            "Error code: 400 - {'error': {'message': 'invalid temperature: "
            "only 1 is allowed for this model', 'type': 'invalid_request_error'}}"
        )
        assert _is_temperature_rejection(err) is True

    def test_openai_temperature_error_matches(self):
        err = Exception(
            "BadRequestError: Invalid temperature value: must be 1 for o1 models"
        )
        assert _is_temperature_rejection(err) is True

    def test_unrelated_400_doesnt_match(self):
        err = Exception("Error code: 400 - invalid model 'gpt-99'")
        assert _is_temperature_rejection(err) is False

    def test_auth_error_doesnt_match(self):
        err = Exception("AuthenticationError: Incorrect API key")
        assert _is_temperature_rejection(err) is False


class TestMaxTokensParamName:
    @pytest.mark.parametrize("model", [
        "o1", "o1-preview", "o3-mini", "o4-preview",
        "gpt-5", "gpt-5.4", "gpt-5-turbo", "gpt-5-mini",
    ])
    def test_reasoning_era_uses_max_completion_tokens(self, model):
        assert _max_tokens_param_name(model) == "max_completion_tokens"

    @pytest.mark.parametrize("model", [
        "gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo",
        "kimi-k2.6", "moonshot-v1-8k", "kimi-latest", "qwen2.5:14b",
    ])
    def test_legacy_models_use_max_tokens(self, model):
        assert _max_tokens_param_name(model) == "max_tokens"


class TestMaxTokensRejection:
    def test_openai_max_tokens_rejection(self):
        err = Exception(
            "Unsupported parameter: 'max_tokens' is not supported with this model. "
            "Use 'max_completion_tokens' instead."
        )
        assert _is_max_tokens_rejection(err) is True

    def test_reverse_max_completion_tokens_rejection(self):
        err = Exception(
            "Error: 'max_completion_tokens' is not supported by this model."
        )
        assert _is_max_completion_tokens_rejection(err) is True

    def test_unrelated_400_ignored(self):
        err = Exception("Invalid model 'gpt-99' requested.")
        assert _is_max_tokens_rejection(err) is False
        assert _is_max_completion_tokens_rejection(err) is False


class TestTryFixBadKwargs:
    def test_fixes_temperature(self):
        kwargs = {"temperature": 0.7, "max_tokens": 100}
        err = Exception("invalid temperature: only 1 is allowed")
        assert _try_fix_bad_kwargs(kwargs, err) is True
        assert "temperature" not in kwargs
        assert kwargs["max_tokens"] == 100

    def test_swaps_max_tokens_to_max_completion_tokens(self):
        kwargs = {"temperature": 0.7, "max_tokens": 100}
        err = Exception("'max_tokens' is not supported. Use 'max_completion_tokens'")
        assert _try_fix_bad_kwargs(kwargs, err) is True
        assert "max_tokens" not in kwargs
        assert kwargs["max_completion_tokens"] == 100

    def test_swaps_back_when_needed(self):
        kwargs = {"max_completion_tokens": 200}
        err = Exception("'max_completion_tokens' is not supported")
        assert _try_fix_bad_kwargs(kwargs, err) is True
        assert kwargs["max_tokens"] == 200
        assert "max_completion_tokens" not in kwargs

    def test_no_op_when_error_unmatched(self):
        kwargs = {"temperature": 0.7, "max_tokens": 100}
        err = Exception("model not found")
        assert _try_fix_bad_kwargs(kwargs, err) is False
        assert kwargs == {"temperature": 0.7, "max_tokens": 100}

    def test_fix_chain_temperature_then_max_tokens(self):
        """Simulate two sequential 400 errors; caller loops, we fix each in turn."""
        kwargs = {"temperature": 0.7, "max_tokens": 100}
        err1 = Exception("temperature: only 1 is allowed")
        assert _try_fix_bad_kwargs(kwargs, err1) is True
        err2 = Exception("'max_tokens' is not supported, use 'max_completion_tokens'")
        assert _try_fix_bad_kwargs(kwargs, err2) is True
        assert "temperature" not in kwargs
        assert "max_tokens" not in kwargs
        assert kwargs["max_completion_tokens"] == 100
