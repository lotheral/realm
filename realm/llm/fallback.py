"""FallbackBackend — wraps a primary backend with ordered runtime fallbacks.

Behaviour per `complete()` call:

    1. Try primary. If it returns, done.
    2. On any exception from primary, log and try next fallback in order.
    3. If every backend fails, raise the error from the last backend attempted.

Used by the router to make `personality_backend: openai / fallback_backend: moonshot`
resilient against runtime errors (bad model id, unsupported parameter the fix-loop
couldn't recover, 5xx, transient timeouts beyond retry budget) — not just
missing-credential failures at build time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realm.core.logging import get_logger

from .interfaces import ILLMBackend, LLMBackendError, LLMResponse

logger = get_logger(__name__)


@dataclass
class FallbackBackend(ILLMBackend):
    primary: ILLMBackend
    fallbacks: list[ILLMBackend] = field(default_factory=list)

    @property
    def backend_name(self) -> str:
        names = [self.primary.backend_name] + [b.backend_name for b in self.fallbacks]
        return "fallback[" + "→".join(names) + "]"

    @property
    def model(self) -> str:
        return self.primary.model

    def complete(
        self, system: str, user: str, *,
        max_tokens: int = 512, temperature: float = 0.7, json_mode: bool = False,
    ) -> LLMResponse:
        chain = [self.primary, *self.fallbacks]
        last_err: Exception | None = None
        for i, backend in enumerate(chain):
            try:
                resp = backend.complete(
                    system, user,
                    max_tokens=max_tokens, temperature=temperature, json_mode=json_mode,
                )
                if i > 0:
                    logger.info(
                        "Fallback succeeded: primary %s failed, served by %s",
                        self.primary.backend_name, backend.backend_name,
                    )
                return resp
            except Exception as e:  # noqa: BLE001
                last_err = e
                is_last = (i == len(chain) - 1)
                if is_last:
                    break
                logger.warning(
                    "Backend %s failed (%s: %s) — trying %s",
                    backend.backend_name, type(e).__name__, e,
                    chain[i + 1].backend_name,
                )
        # Every backend failed
        assert last_err is not None
        raise LLMBackendError(
            f"all {len(chain)} backends failed; last error from "
            f"{chain[-1].backend_name}: {last_err}"
        ) from last_err
