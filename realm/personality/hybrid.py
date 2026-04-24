"""Hybrid personality embedder (Mode C per doc §5.2).

Strategy:
    1. Run the rule-based embedder → baseline TraitVector.
    2. Ask the LLM for small ADJUSTMENTS given the baseline + natal chart.
    3. Blend: final = clamp(baseline + blend_ratio × adjustments, 0, 1).

If the LLM is unavailable, returns the rule-based baseline unchanged —
production-safe even with no API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from realm.core.logging import get_logger
from realm.core.types import NatalChart
from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_prompt
from realm.llm.router import TASK_PERSONALITY, LLMRouter

from .interfaces import IPersonalityEmbedder
from .llm_based import natal_chart_hash, serialize_natal_chart
from .rule_based import RuleBasedEmbedder
from .trait_vector import TraitVector

logger = get_logger(__name__)


@dataclass
class HybridEmbedder(IPersonalityEmbedder):
    backend: ILLMBackend | None = None
    router: LLMRouter | None = None
    blend_ratio: float = 0.5                # weight of LLM adjustments
    _cache: dict[str, TraitVector] = field(default_factory=dict)
    _rule_based: RuleBasedEmbedder = field(default_factory=RuleBasedEmbedder)

    def __post_init__(self):
        if self.backend is None:
            router = self.router or LLMRouter()
            try:
                self.backend = router.for_task(TASK_PERSONALITY)
            except LLMBackendError as e:
                logger.warning("HybridEmbedder: %s — using pure rule-based", e)
                self.backend = None

    @property
    def mode(self) -> str:
        return "hybrid"

    def embed(self, chart: NatalChart) -> TraitVector:
        key = natal_chart_hash(chart)
        if key in self._cache:
            return self._cache[key]

        baseline = self._rule_based.embed(chart)

        if self.backend is None:
            self._cache[key] = baseline
            return baseline

        prompt = load_prompt("personality/hybrid_refinement")
        user = prompt.render(
            baseline_json=json.dumps(baseline.to_dict(), separators=(",", ":")),
            chart_json=serialize_natal_chart(chart),
        )
        try:
            adjustments = self.backend.complete_json(
                system="You output JSON only. No prose.",
                user=user,
                max_tokens=512, temperature=0.3,
            )
        except LLMBackendError as e:
            logger.warning("Hybrid LLM call failed (%s) — keeping baseline", e)
            self._cache[key] = baseline
            return baseline

        if not isinstance(adjustments, dict):
            logger.warning("Hybrid LLM returned non-dict %r — keeping baseline",
                           type(adjustments).__name__)
            self._cache[key] = baseline
            return baseline

        scaled = {
            k: max(-0.15, min(0.15, float(v))) * self.blend_ratio
            for k, v in adjustments.items()
            if isinstance(v, (int, float)) and k in TraitVector.trait_names()
        }
        merged = baseline.apply_modifier(scaled)
        self._cache[key] = merged
        return merged
