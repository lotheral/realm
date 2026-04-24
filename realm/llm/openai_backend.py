"""OpenAI-compatible backends: OpenAI + Moonshot.

Both use the `openai` Python SDK. Moonshot is wire-compatible with the OpenAI
chat-completions API — we just swap the base_url and API key.

Env vars:
    OPENAI_API_KEY          — OpenAI credential
    REALM_OPENAI_MODEL      — model id (default: "gpt-5.4")
    REALM_OPENAI_BASE_URL   — override base URL if hitting a proxy
    MOONSHOT_API_KEY        — Moonshot credential
    REALM_MOONSHOT_MODEL    — model id (default: "kimi-k2.6")
    REALM_MOONSHOT_BASE_URL — default: "https://api.moonshot.ai/v1"
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from realm.core.logging import get_logger

from .interfaces import (
    ILLMBackend,
    InMemoryCache,
    LLMBackendError,
    LLMResponse,
    prompt_key,
    retry_with_backoff,
)

logger = get_logger(__name__)


# Reasoning-style models that only accept temperature=1 (i.e. reject any
# custom temperature). We skip sending `temperature` entirely for these so
# the API uses its internal default. New identifiers can be added here as
# providers ship more reasoning families.
_FIXED_TEMPERATURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^o1(\b|-|$)"),          # OpenAI o1*
    re.compile(r"^o3(\b|-|$)"),          # OpenAI o3*
    re.compile(r"^o4(\b|-|$)"),          # OpenAI o4*
    re.compile(r"^gpt-5\.?5"),           # gpt-5.5* (reasoning)
    re.compile(r"^kimi-k2"),             # Moonshot Kimi K2*
    re.compile(r"^kimi-k3"),             # Moonshot Kimi K3*
)

# Models that use `max_completion_tokens` instead of `max_tokens`. OpenAI
# switched the parameter name for all reasoning + gpt-5 era models.
_USES_MAX_COMPLETION_TOKENS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^o1(\b|-|$)"),
    re.compile(r"^o3(\b|-|$)"),
    re.compile(r"^o4(\b|-|$)"),
    re.compile(r"^gpt-5"),
)


def _model_accepts_custom_temperature(model_id: str) -> bool:
    m = (model_id or "").lower()
    return not any(p.search(m) for p in _FIXED_TEMPERATURE_PATTERNS)


def _max_tokens_param_name(model_id: str) -> str:
    """Return the right parameter name for token limits on this model."""
    m = (model_id or "").lower()
    if any(p.search(m) for p in _USES_MAX_COMPLETION_TOKENS):
        return "max_completion_tokens"
    return "max_tokens"


def _is_temperature_rejection(err: Exception) -> bool:
    """True if the API complained about the temperature parameter specifically."""
    msg = str(err).lower()
    return "temperature" in msg and ("invalid" in msg or "only 1" in msg or "must be" in msg)


def _is_max_tokens_rejection(err: Exception) -> bool:
    """True if the API says 'max_tokens is not supported, use max_completion_tokens'."""
    msg = str(err).lower()
    return "max_tokens" in msg and ("not supported" in msg or "unsupported" in msg
                                    or "max_completion_tokens" in msg)


def _is_max_completion_tokens_rejection(err: Exception) -> bool:
    """Reverse case: provider rejects the newer name and wants max_tokens."""
    msg = str(err).lower()
    return "max_completion_tokens" in msg and ("not supported" in msg or "unsupported" in msg
                                               or "unrecognized" in msg)


def _try_fix_bad_kwargs(kwargs: dict, err: Exception) -> bool:
    """Mutate `kwargs` in place to work around a known provider-parameter
    rejection. Returns True if a fix was applied — caller should retry once."""
    if "temperature" in kwargs and _is_temperature_rejection(err):
        kwargs.pop("temperature")
        return True
    if "max_tokens" in kwargs and _is_max_tokens_rejection(err):
        kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        return True
    if "max_completion_tokens" in kwargs and _is_max_completion_tokens_rejection(err):
        kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
        return True
    return False


@dataclass
class OpenAICompatibleBackend(ILLMBackend):
    """Shared base for OpenAI + Moonshot (+ any other OpenAI-compatible provider)."""

    _backend_name: str = "openai"
    _model: str = "gpt-5.4"
    api_key: str | None = None
    base_url: str | None = None
    cache: InMemoryCache | None = field(default_factory=InMemoryCache)
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not self.api_key:
            raise LLMBackendError(
                f"{self._backend_name}: API key missing. "
                f"Set the relevant environment variable."
            )
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMBackendError(
                "openai package not installed. Run: pip install openai"
            ) from e
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self, system: str, user: str, *,
        max_tokens: int = 512, temperature: float = 0.7, json_mode: bool = False,
    ) -> LLMResponse:
        key = prompt_key(system, user, self._model, json_mode, temperature)
        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return LLMResponse(
                    content=cached.content, model=cached.model,
                    tokens_in=cached.tokens_in, tokens_out=cached.tokens_out,
                    cached=True,
                )

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Use max_tokens for legacy chat models, max_completion_tokens for
            # OpenAI reasoning + gpt-5 era. Wrong guesses are corrected by the
            # reactive-retry loop below.
            _max_tokens_param_name(self._model): max_tokens,
        }
        # Reasoning-style models (o1/o3/kimi-k2/…) only allow temperature=1.
        # For those, skip the parameter entirely and let the API use its default.
        if _model_accepts_custom_temperature(self._model):
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        def _call():
            return self._client.chat.completions.create(**kwargs)

        # Call + reactive-fix loop. Each iteration fixes ONE provider-parameter
        # rejection (temperature, max_tokens ↔ max_completion_tokens, …) and
        # retries. Capped at 3 fixes to avoid an infinite loop on pathological
        # 400s that our heuristics can't map.
        resp = None
        for attempt in range(4):
            try:
                resp = retry_with_backoff(_call, attempts=3, base_delay=1.0, max_delay=10.0)
                break
            except Exception as e:
                if attempt < 3 and _try_fix_bad_kwargs(kwargs, e):
                    logger.info(
                        "Model %r rejected a parameter; retrying with corrected kwargs.",
                        self._model,
                    )
                    continue
                raise
        assert resp is not None
        content = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0

        result = LLMResponse(
            content=content, model=self._model,
            tokens_in=tokens_in, tokens_out=tokens_out, cached=False,
        )
        if self.cache is not None:
            self.cache.set(key, result)
        return result


# ---- Concrete backends ---------------------------------------------------

class OpenAIBackend(OpenAICompatibleBackend):
    """OpenAI (api.openai.com)."""

    def __init__(
        self, model: str | None = None,
        api_key: str | None = None, base_url: str | None = None,
        cache: InMemoryCache | None = None,
    ):
        super().__init__(
            _backend_name="openai",
            _model=model or os.getenv("REALM_OPENAI_MODEL", "gpt-5.4"),
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("REALM_OPENAI_BASE_URL"),
            cache=cache if cache is not None else InMemoryCache(),
        )


class MoonshotBackend(OpenAICompatibleBackend):
    """Moonshot (Kimi) — wire-compatible with OpenAI chat completions API."""

    DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"

    def __init__(
        self, model: str | None = None,
        api_key: str | None = None, base_url: str | None = None,
        cache: InMemoryCache | None = None,
    ):
        super().__init__(
            _backend_name="moonshot",
            _model=model or os.getenv("REALM_MOONSHOT_MODEL", "kimi-k2.6"),
            api_key=api_key or os.getenv("MOONSHOT_API_KEY"),
            base_url=base_url or os.getenv("REALM_MOONSHOT_BASE_URL", self.DEFAULT_BASE_URL),
            cache=cache if cache is not None else InMemoryCache(),
        )
