"""PersonalityEmbedder orchestrator.

Selects an embedder implementation based on the `realm.personality.mode` config
key. Supported modes:

    - "rule_based"  — deterministic table-driven (no LLM, offline-safe)
    - "llm"         — full LLM embedder (Mode B); graceful fallback to rule-based
    - "hybrid"      — rule-based baseline + LLM adjustments (Mode C); graceful
                      fallback to pure rule-based when no LLM key is available
"""

from __future__ import annotations

from realm.core.config import load_realm_config
from realm.core.exceptions import PersonalityEmbeddingError

from .interfaces import IPersonalityEmbedder
from .rule_based import RuleBasedEmbedder


def get_personality_embedder(mode: str | None = None) -> IPersonalityEmbedder:
    """Return a ready-to-use embedder instance.

    Args:
        mode: "rule_based" | "llm" | "hybrid". If None, read from realm.yaml.
    """
    if mode is None:
        cfg = load_realm_config()
        mode = cfg["realm"]["personality"]["mode"]

    if mode == "rule_based":
        return RuleBasedEmbedder()
    if mode == "llm":
        from .llm_based import LLMEmbedder
        return LLMEmbedder()
    if mode == "hybrid":
        from .hybrid import HybridEmbedder
        return HybridEmbedder()
    raise PersonalityEmbeddingError(f"unknown personality mode: {mode!r}")
