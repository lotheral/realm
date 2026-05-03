"""Sprint 17 WP4 — LLM-driven prediction narrative.

After the simulation produces (probability, buckets, trait_shifts),
this narrator asks the LLM for a question-specific story: a headline,
3-4 key drivers, the dissent view, a confidence note, and a caveat.
The result is surfaced on ``PredictResponse`` (dashboard renders it
when present, falls back to template text when None).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_split_prompt
from realm.output.category_router import CategoryMatch
from realm.output.question_analyzer import QuestionAnalysis
from realm.output.scenario_analyzer import ScenarioAnalysis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PredictionNarrative:
    """LLM-generated narrative wrapping the raw simulation numbers."""

    headline: str
    key_drivers: tuple[str, ...]
    dissent_view: str
    confidence_note: str
    caveat: str

    @classmethod
    def from_llm_dict(cls, data: Mapping[str, object]) -> PredictionNarrative | None:
        headline = str(data.get("headline", "")).strip()
        if not headline:
            return None
        drivers_raw = data.get("key_drivers") or []
        if not isinstance(drivers_raw, (list, tuple)):
            return None
        drivers = tuple(
            str(d).strip() for d in drivers_raw
            if isinstance(d, str) and d.strip()
        )
        if not drivers:
            return None
        return cls(
            headline=headline,
            key_drivers=drivers,
            dissent_view=str(data.get("dissent_view", "")).strip(),
            confidence_note=str(data.get("confidence_note", "")).strip(),
            caveat=str(data.get("caveat", "")).strip(),
        )


class PredictionNarrator:
    """Wraps an ``ILLMBackend`` and produces ``PredictionNarrative``."""

    def __init__(self, llm_backend: ILLMBackend | None) -> None:
        self._llm = llm_backend

    def narrate(
        self,
        *,
        question: str,
        category: CategoryMatch,
        analysis: QuestionAnalysis | None,
        probability: float,
        simulation_probability: float | None,
        blended_probability: float | None,
        supporting: float,
        opposing: float,
        neutral: float,
        trait_shifts: Mapping[str, float],
        scenario_feed: str | None = None,
        scenario_analysis: ScenarioAnalysis | None = None,
        delta: float | None = None,
    ) -> PredictionNarrative | None:
        """Returns ``None`` on any LLM failure path."""
        if self._llm is None:
            return None

        prompt = load_split_prompt("narrative/generate")

        # Stringify everything for safe substitution. Missing analysis
        # fields render as "n/a" so the LLM understands "not available".
        def _opt(v) -> str:
            if v is None:
                return "n/a"
            if isinstance(v, float):
                return f"{v:.4f}"
            return str(v)

        def _opt_list(seq) -> str:
            if not seq:
                return "n/a"
            return ", ".join(str(x) for x in seq)

        user = prompt.render_user(
            question=question,
            category_id=category.category_id,
            subject=_opt(analysis.subject if analysis else None),
            yes_means=_opt(analysis.yes_means if analysis else None),
            no_means=_opt(analysis.no_means if analysis else None),
            key_factors=_opt_list(analysis.key_factors if analysis else ()),
            llm_prior=_opt(analysis.llm_prior if analysis else None),
            probability=f"{probability:.4f}",
            probability_pct=f"{probability * 100:.1f}",
            simulation_probability=_opt(simulation_probability),
            blended_probability=_opt(blended_probability),
            supporting=f"{supporting * 100:.1f}",
            opposing=f"{opposing * 100:.1f}",
            neutral=f"{neutral * 100:.1f}",
            trait_shifts=", ".join(
                f"{k}={v:+.3f}" for k, v in trait_shifts.items()
            ) or "n/a",
            scenario_feed=_opt(scenario_feed),
            scenario_direction=_opt(
                scenario_analysis.direction if scenario_analysis else None
            ),
            scenario_magnitude=_opt(
                scenario_analysis.magnitude if scenario_analysis else None
            ),
            delta=_opt(delta),
        )

        try:
            data = self._llm.complete_json(
                prompt.system, user, temperature=0.3, max_tokens=1024,
            )
        except (LLMBackendError, ValueError, KeyError) as e:
            logger.warning("LLM narrative generation failed (%s); skipping", e)
            return None

        if not isinstance(data, Mapping):
            logger.warning("LLM narrative returned non-mapping; skipping")
            return None

        result = PredictionNarrative.from_llm_dict(data)
        if result is None:
            logger.warning(
                "LLM narrative schema mismatch (keys=%s); skipping",
                list(data.keys()),
            )
        return result
