"""LLM router — selects a backend per task type.

Config schema (realm.yaml → realm.llm):

    llm:
      default_backend: "moonshot"
      personality_backend: "moonshot"
      spotlight_backend: "moonshot"
      parser_backend: "openai"
      report_backend: "openai"
      simulation_backend: "ollama"

Env vars override: `REALM_LLM_<TASK>_BACKEND` (e.g. `REALM_LLM_PERSONALITY_BACKEND=openai`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from realm.core.config import load_realm_config
from realm.core.logging import get_logger

from .interfaces import ILLMBackend, LLMBackendError

logger = get_logger(__name__)


# Canonical task types.
TASK_PERSONALITY = "personality"
TASK_SPOTLIGHT = "spotlight"
TASK_PARSER = "parser"
TASK_REPORT = "report"
TASK_SIMULATION = "simulation"

_TASK_ORDER = (TASK_PERSONALITY, TASK_SPOTLIGHT, TASK_PARSER, TASK_REPORT, TASK_SIMULATION)


@lru_cache(maxsize=1)
def _llm_config() -> dict:
    try:
        return load_realm_config().get("realm", {}).get("llm", {})
    except Exception:
        return {}


def _resolve_backend_name(task: str) -> str:
    """Resolve the backend id for a task: env > config > default."""
    env_name = f"REALM_LLM_{task.upper()}_BACKEND"
    if env_name in os.environ:
        return os.environ[env_name].strip()
    cfg = _llm_config()
    specific = cfg.get(f"{task}_backend")
    if specific:
        return str(specific)
    return str(cfg.get("default_backend", "moonshot"))


def build_backend(name: str) -> ILLMBackend:
    """Factory by backend id."""
    n = name.lower()
    if n == "openai":
        from .openai_backend import OpenAIBackend
        return OpenAIBackend()
    if n == "moonshot":
        from .openai_backend import MoonshotBackend
        return MoonshotBackend()
    if n == "ollama":
        from .ollama_backend import OllamaBackend
        return OllamaBackend()
    raise LLMBackendError(f"unknown LLM backend: {name!r}")


@dataclass
class LLMRouter:
    """Cached per-task backend dispenser. Falls back to the configured
    fallback backend when a task-specific backend can't be instantiated
    (e.g. missing API key). `fallback_backend=None` reads from realm.yaml."""

    fallback_backend: str | None = None
    _instances: dict[str, ILLMBackend] = field(default_factory=dict)

    def __post_init__(self):
        if self.fallback_backend is None:
            cfg = _llm_config()
            self.fallback_backend = str(cfg.get("fallback_backend", "moonshot"))

    def for_task(self, task: str) -> ILLMBackend:
        """Return the backend for a task.

        If primary and fallback are different providers and both have credentials,
        wraps them in a FallbackBackend so runtime errors on primary
        (bad model id, unsupported parameters, 5xx, etc.) are transparently
        retried against the fallback before bubbling up.
        """
        if task not in self._instances:
            name = _resolve_backend_name(task)
            fallback_name = self.fallback_backend

            try:
                primary = build_backend(name)
            except LLMBackendError as e:
                logger.warning(
                    "LLM backend %r unavailable for task %r (%s) — trying %r",
                    name, task, e, fallback_name,
                )
                if name == fallback_name:
                    raise
                # Build-time fallback: just the fallback backend alone.
                self._instances[task] = build_backend(fallback_name)
                return self._instances[task]

            # Primary built successfully. Wrap with runtime fallback if a
            # distinct secondary backend is also available.
            if fallback_name and fallback_name != name:
                try:
                    secondary = build_backend(fallback_name)
                    from .fallback import FallbackBackend
                    self._instances[task] = FallbackBackend(
                        primary=primary, fallbacks=[secondary],
                    )
                    logger.debug(
                        "Task %r routed: primary=%s fallback=%s",
                        task, name, fallback_name,
                    )
                    return self._instances[task]
                except LLMBackendError:
                    # Fallback not configured — use primary alone.
                    pass

            self._instances[task] = primary
        return self._instances[task]

    def clear(self):
        self._instances.clear()


def is_llm_configured() -> bool:
    """Return True if at least one LLM backend is reachable (has an API key)."""
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("MOONSHOT_API_KEY")
        or os.getenv("OLLAMA_HOST")     # local Ollama is assumed reachable when set
    )
