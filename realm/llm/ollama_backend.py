"""Ollama backend — local LLM server, zero credentials.

Requires a running `ollama serve` on OLLAMA_HOST (default http://localhost:11434).
Uses HTTP directly (no SDK dependency) so Ollama is optional.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from realm.core.logging import get_logger

from .interfaces import (
    ILLMBackend,
    InMemoryCache,
    LLMBackendError,
    LLMResponse,
    prompt_key,
)

logger = get_logger(__name__)


@dataclass
class OllamaBackend(ILLMBackend):
    _model: str = "qwen2.5:14b"
    host: str = "http://localhost:11434"
    cache: InMemoryCache | None = field(default_factory=InMemoryCache)

    def __post_init__(self):
        self._model = os.getenv("REALM_OLLAMA_MODEL", self._model)
        self.host = os.getenv("OLLAMA_HOST", self.host).rstrip("/")

    @property
    def backend_name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self, system: str, user: str, *,
        max_tokens: int = 512, temperature: float = 0.7, json_mode: bool = False,
    ) -> LLMResponse:
        key = prompt_key(system, user, self._model, json_mode, temperature)
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return LLMResponse(
                    content=hit.content, model=hit.model,
                    tokens_in=hit.tokens_in, tokens_out=hit.tokens_out,
                    cached=True,
                )

        payload: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            req = urllib.request.Request(
                f"{self.host}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise LLMBackendError(f"ollama unreachable at {self.host}: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMBackendError(f"ollama returned malformed response: {e}") from e

        content = data.get("message", {}).get("content", "").strip()
        result = LLMResponse(
            content=content, model=self._model,
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
            cached=False,
        )
        if self.cache is not None:
            self.cache.set(key, result)
        return result
