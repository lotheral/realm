"""LLM backend interface + simple in-memory cache + retry helper.

Design contract:
    - `complete(system, user, …)` is the primary entrypoint (chat-style).
    - Backends must be deterministic per (prompt, model, temperature=0) so
      cached replies are safe to reuse across sessions.
    - `complete_json(system, user, schema_hint)` is a convenience that forces
      JSON output and validates/parses the response.
    - Missing credentials raise LLMBackendError — callers decide fallback.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from realm.core.exceptions import REALMError
from realm.core.logging import get_logger

logger = get_logger(__name__)


class LLMBackendError(REALMError):
    """Backend misconfigured, network failed, or response malformed."""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cached: bool = False


class ILLMBackend(ABC):
    """Chat-style text-completion backend."""

    @property
    @abstractmethod
    def backend_name(self) -> str: ...

    @property
    @abstractmethod
    def model(self) -> str: ...

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Return a completion for (system, user) messages."""

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Mapping[str, Any]:
        """Like complete() but returns parsed JSON. Raises on malformed output."""
        resp = self.complete(
            system, user,
            max_tokens=max_tokens, temperature=temperature, json_mode=True,
        )
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError as e:
            # Try to extract the first JSON object from the text (some models
            # include prose around it even in "json mode")
            extracted = _extract_first_json(resp.content)
            if extracted is not None:
                return extracted
            raise LLMBackendError(
                f"{self.backend_name} returned non-JSON: {resp.content[:200]}"
            ) from e


# ---- Cache ----------------------------------------------------------------

def prompt_key(system: str, user: str, model: str, json_mode: bool, temperature: float) -> str:
    """Deterministic hash for (prompt, model, mode). Temperature rounded to 2 dp
    so small numerical drift doesn't invalidate the cache."""
    payload = json.dumps(
        {
            "s": system, "u": user, "m": model, "j": json_mode,
            "t": round(temperature, 2),
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class InMemoryCache:
    """Tiny LRU-ish cache (dict-backed). For persistent caching, wrap a real
    store here."""
    max_size: int = 1024
    _store: dict[str, LLMResponse] = field(default_factory=dict)

    def get(self, key: str) -> LLMResponse | None:
        return self._store.get(key)

    def set(self, key: str, value: LLMResponse) -> None:
        if len(self._store) >= self.max_size:
            # Drop an arbitrary entry — good enough for MVP
            self._store.pop(next(iter(self._store)))
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


# ---- Retry with jittered backoff -----------------------------------------

def retry_with_backoff(
    fn, *, attempts: int = 3, base_delay: float = 1.0, max_delay: float = 15.0,
    rng: random.Random | None = None,
):
    """Run `fn()` up to `attempts` times with exponential backoff on any exception
    whose name ends in 'RateLimitError', 'APIConnectionError', or 'Timeout'."""
    last_err: Exception | None = None
    r = rng or random.Random()
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            last_err = e
            is_transient = any(
                tag in name for tag in ("RateLimit", "APIConnection", "Timeout", "ServiceUnavailable")
            )
            if not is_transient or i == attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2 ** i)) + r.uniform(0, 0.5)
            logger.warning("Transient LLM error %s — retry %d/%d in %.1fs",
                           name, i + 1, attempts, delay)
            time.sleep(delay)
    if last_err:
        raise last_err


# ---- JSON extraction helper ----------------------------------------------

def _extract_first_json(text: str) -> Any | None:
    """Best-effort: find the first balanced {...} block and json.loads() it."""
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"' and not esc:
            in_str = not in_str
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start: i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = -1
    return None
