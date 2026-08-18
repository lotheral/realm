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
# Sprint 17: dedicated task for category-router LLM-first classification.
# Allows the dashboard / API operator to point category routing at a
# different (e.g. cheaper, faster) backend than personality embedding.
TASK_CATEGORY = "category"

_TASK_ORDER = (
    TASK_PERSONALITY, TASK_SPOTLIGHT, TASK_PARSER, TASK_REPORT,
    TASK_SIMULATION, TASK_CATEGORY,
)


@lru_cache(maxsize=1)
def _llm_config() -> dict:
    try:
        return load_realm_config().get("realm", {}).get("llm", {})
    except Exception:
        return {}


_TRUTHY_GATE_VALUES = ("1", "true", "yes", "on")


def _resolve_backend_name(task: str) -> str:
    """Resolve the backend id for a task: env > config > default.

    Sprint 17: when the env value is a truthy boolean gate
    ({"1", "true", "yes", "on"}) — common pattern for "enable LLM"
    flags — fall through to the config-driven default rather than
    trying to build a backend literally named "1". This lets users
    write the simple `REALM_LLM_<TASK>_BACKEND=1` to enable LLM and
    pick up their `realm.yaml` default, while explicit backend names
    (e.g. `=openai`, `=ollama`) still pin to that specific backend.
    """
    env_name = f"REALM_LLM_{task.upper()}_BACKEND"
    if env_name in os.environ:
        env_val = os.environ[env_name].strip()
        if env_val and env_val.lower() not in _TRUTHY_GATE_VALUES:
            return env_val
        # Truthy gate ("1" / "true" / etc): fall through to config default
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


# Sprint 20 — the ONE place that decides whether an LLM enable-gate env var
# is on. Before this, predict.py used bare truthiness while category_router
# parsed strictly, so REALM_LLM_CATEGORY_BACKEND=0 produced a half-LLM
# state (router off, analyzers on) that no test covered.
#
# Semantics (settled after the Sprint 20 verification pass): these vars
# double as BACKEND SELECTORS — the module docstring documents
# REALM_LLM_<TASK>_BACKEND=openai / =moonshot as valid, and
# _resolve_backend_name() honors them — so an allowlist of truthy words
# would silently disable documented configurations. The gate is therefore
# OFF only for explicitly-falsy values (or unset); any other non-empty
# value (1/true/yes/on, or a backend name) counts as enabled.
_FALSY_GATE_VALUES = ("", "0", "false", "no", "off", "none", "disabled")


def env_gate_enabled(env_var: str) -> bool:
    """Return True unless the env var is unset or holds an explicitly
    falsy value (0/false/no/off/none/disabled, case-insensitive,
    whitespace-tolerant). Backend names like ``openai`` count as
    enabled — they both open the gate and pin the task's backend."""
    return os.environ.get(env_var, "").strip().lower() not in _FALSY_GATE_VALUES


def backend_for(
    task: str,
    env_var: str = "REALM_LLM_CATEGORY_BACKEND",
):
    """Resolve the LLM backend for ``task``, or ``None`` when the gate is
    off, no API key is configured, or backend construction fails.

    This is the single entry point every REALM component uses to obtain
    an optional LLM backend — graceful degradation (return ``None``,
    never raise) is part of the contract.
    """
    if not (env_gate_enabled(env_var) and is_llm_configured()):
        return None
    try:
        return LLMRouter().for_task(task)
    except Exception as exc:  # noqa: BLE001 - degrade, never break the caller
        logger.warning(
            "LLM backend construction for task %r failed (%s); "
            "degrading to no-LLM mode", task, exc,
        )
        return None
