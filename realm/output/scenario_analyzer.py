"""Sprint 17 WP3 — LLM-driven scenario analysis.

When ``predict_endpoint`` receives a ``scenario_feed`` and an LLM
backend is wired, this analyzer asks the LLM for structured guidance
on how to perturb the agent population: which traits to push, by how
much, and what fraction of agents are swayed by the news.

The result feeds directly into ``_make_perturbed_agent_builder`` in
``realm/api/predict.py``. When the analyzer is unavailable / fails /
returns nonsense, the caller falls back to the pre-Sprint-17
sentiment-word-counting heuristic in ``_perturbation_for_feed``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_split_prompt
from realm.output.category_router import CategoryMatch
from realm.personality.trait_vector import TraitVector

logger = logging.getLogger(__name__)

_VALID_DIRECTIONS = ("increases", "decreases", "mixed")
_VALID_MAGNITUDES = ("slight", "moderate", "strong")
_TRAIT_IMPACT_CLAMP = (-0.15, 0.15)
_AFFECTED_PCT_CLAMP = (0.1, 0.95)


@dataclass(frozen=True)
class ScenarioAnalysis:
    """Structured LLM read of a scenario_feed.

    All fields are validated / clamped at construction time via
    :meth:`ScenarioAnalysis.from_llm_dict` — the dataclass itself is a
    frozen container.
    """

    original_feed: str
    event_summary: str
    direction: str            # one of _VALID_DIRECTIONS
    magnitude: str            # one of _VALID_MAGNITUDES
    trait_impacts: tuple[tuple[str, float], ...]   # bounded ± 0.15
    reasoning: str
    affected_population_pct: float                  # bounded [0.1, 0.95]

    @property
    def trait_impacts_dict(self) -> dict[str, float]:
        """Convenience view as a plain dict for downstream apply loops."""
        return dict(self.trait_impacts)

    @classmethod
    def from_llm_dict(
        cls, feed: str, data: Mapping[str, object],
    ) -> ScenarioAnalysis | None:
        """Build from an LLM JSON response with sanitization + clamping.

        Returns ``None`` when the schema is missing load-bearing fields
        (``direction`` invalid, ``trait_impacts`` empty after filtering).
        """
        direction_raw = str(data.get("direction", "")).strip().lower()
        if direction_raw not in _VALID_DIRECTIONS:
            return None

        magnitude_raw = str(data.get("magnitude", "")).strip().lower()
        if magnitude_raw not in _VALID_MAGNITUDES:
            magnitude_raw = "moderate"  # safe default

        valid_traits = set(TraitVector.trait_names())
        impacts_raw = data.get("trait_impacts") or {}
        if not isinstance(impacts_raw, Mapping):
            return None
        sanitized: list[tuple[str, float]] = []
        for k, v in impacts_raw.items():
            if not isinstance(k, str) or k not in valid_traits:
                continue
            try:
                vf = float(v)
            except (TypeError, ValueError):
                continue
            clamped = max(_TRAIT_IMPACT_CLAMP[0],
                          min(_TRAIT_IMPACT_CLAMP[1], vf))
            sanitized.append((k, clamped))
        if not sanitized:
            return None  # nothing to perturb → caller falls back

        try:
            pct_raw = float(data.get("affected_population_pct", 0.7))
        except (TypeError, ValueError):
            pct_raw = 0.7
        affected_pct = max(_AFFECTED_PCT_CLAMP[0],
                           min(_AFFECTED_PCT_CLAMP[1], pct_raw))

        return cls(
            original_feed=feed,
            event_summary=str(data.get("event_summary", "")).strip(),
            direction=direction_raw,
            magnitude=magnitude_raw,
            trait_impacts=tuple(sanitized),
            reasoning=str(data.get("reasoning", "")).strip(),
            affected_population_pct=affected_pct,
        )


class ScenarioAnalyzer:
    """Wraps an ``ILLMBackend`` and produces ``ScenarioAnalysis``."""

    def __init__(self, llm_backend: ILLMBackend | None) -> None:
        self._llm = llm_backend

    def analyze(
        self, feed: str, question: str, category: CategoryMatch,
    ) -> ScenarioAnalysis | None:
        """Returns ``None`` on any failure path (no LLM, network error,
        invalid direction, all trait names hallucinated). Caller treats
        ``None`` as "use the heuristic perturbation path."
        """
        if self._llm is None or not feed.strip():
            return None

        prompt = load_split_prompt("scenario/parse")
        trait_list = "\n".join(f"  - {t}" for t in TraitVector.trait_names())
        user = prompt.render_user(
            question=question,
            category_id=category.category_id,
            feed=feed,
            trait_list=trait_list,
        )

        try:
            data = self._llm.complete_json(
                prompt.system, user, temperature=0.2, max_tokens=1024,
            )
        except (LLMBackendError, ValueError, KeyError) as e:
            logger.warning("LLM scenario analysis failed (%s); skipping", e)
            return None

        if not isinstance(data, Mapping):
            logger.warning("LLM scenario analysis returned non-mapping; skipping")
            return None

        result = ScenarioAnalysis.from_llm_dict(feed, data)
        if result is None:
            logger.warning(
                "LLM scenario analysis schema mismatch (keys=%s); skipping",
                list(data.keys()),
            )
        return result
