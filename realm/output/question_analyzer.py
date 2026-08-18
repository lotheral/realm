"""Sprint 17 WP2 — LLM-driven question analysis.

After ``CategoryRouter.route()`` picks a category, this analyzer asks the
LLM to extract structured information about the question itself: what is
being predicted, what YES/NO mean, which traits are most relevant, and
the LLM's own probability prior. The prior is later blended with the
simulation result via the category's ``llm_blend_weight``.

Graceful degradation: ``analyze()`` returns ``None`` on any LLM failure
or schema mismatch. Callers that don't need a full analysis can use
:meth:`QuestionAnalysis.minimal` to construct a placeholder with only
``original_question`` and category metadata populated.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_split_prompt
from realm.output.category_router import CategoryMatch
from realm.personality.trait_vector import TraitVector

logger = logging.getLogger(__name__)

_VALID_HORIZONS = ("weeks", "months", "years", "unknown")
_PRIOR_CLAMP = (0.05, 0.95)


@dataclass(frozen=True)
class QuestionAnalysis:
    """Structured LLM-derived view of a prediction question.

    All ``Optional`` fields default to ``None`` / empty so a "minimal"
    analysis (no LLM available) can be constructed via
    :meth:`QuestionAnalysis.minimal`.
    """

    original_question: str
    category_id: str
    category_label: str

    # LLM-derived fields (None / empty when unavailable)
    subject: str | None = None
    outcome_variable: str | None = None
    yes_means: str | None = None
    no_means: str | None = None
    key_factors: tuple[str, ...] = ()
    relevant_traits: tuple[str, ...] = ()
    time_horizon: str | None = None
    llm_prior: float | None = None
    prior_reasoning: str | None = None
    # Sprint 20: web research result travels WITH the analysis instead of
    # through an analyzer instance attribute (the old `_last_web_result`
    # side channel leaked stale results across requests and raced under
    # FastAPI's threadpool). Typed as `object` for the same import-cycle
    # reason as QuestionAnalyzer._web; the runtime contract is
    # ``.context`` (str) + ``.sources`` (iterable with ``.url``).
    web_result: object | None = None

    @classmethod
    def minimal(cls, question: str, category: CategoryMatch) -> QuestionAnalysis:
        """Construct a placeholder analysis used when no LLM is available.
        Carries only the original question + category metadata; all LLM-
        derived fields stay None / empty."""
        return cls(
            original_question=question,
            category_id=category.category_id,
            category_label=category.label,
        )

    @classmethod
    def from_llm_dict(
        cls,
        question: str,
        category: CategoryMatch,
        data: Mapping[str, object],
    ) -> QuestionAnalysis | None:
        """Build a QuestionAnalysis from an LLM JSON response.

        Returns ``None`` when the schema is missing the load-bearing
        fields (``llm_prior`` plus at least one of ``subject`` /
        ``yes_means``). Silently sanitizes / clamps the rest:
            - ``llm_prior`` clamped to ``_PRIOR_CLAMP`` ([0.05, 0.95])
            - ``relevant_traits`` filtered to known TraitVector names
            - ``time_horizon`` validated against ``_VALID_HORIZONS``;
              defaults to ``"unknown"`` on mismatch
        """
        if "llm_prior" not in data:
            return None
        if not (data.get("subject") or data.get("yes_means")):
            return None

        try:
            prior_raw = float(data.get("llm_prior", 0.5))
        except (TypeError, ValueError):
            return None
        prior = max(_PRIOR_CLAMP[0], min(_PRIOR_CLAMP[1], prior_raw))

        valid_traits = set(TraitVector.trait_names())
        relevant_raw = data.get("relevant_traits") or []
        if not isinstance(relevant_raw, (list, tuple)):
            relevant = ()
        else:
            relevant = tuple(
                str(t) for t in relevant_raw
                if isinstance(t, str) and t in valid_traits
            )

        key_factors_raw = data.get("key_factors") or []
        if not isinstance(key_factors_raw, (list, tuple)):
            key_factors: tuple[str, ...] = ()
        else:
            key_factors = tuple(
                str(f).strip() for f in key_factors_raw
                if isinstance(f, str) and f.strip()
            )

        horizon_raw = data.get("time_horizon")
        horizon = str(horizon_raw).strip().lower() if isinstance(horizon_raw, str) else "unknown"
        if horizon not in _VALID_HORIZONS:
            horizon = "unknown"

        def _opt_str(key: str) -> str | None:
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
            return None

        return cls(
            original_question=question,
            category_id=category.category_id,
            category_label=category.label,
            subject=_opt_str("subject"),
            outcome_variable=_opt_str("outcome_variable"),
            yes_means=_opt_str("yes_means"),
            no_means=_opt_str("no_means"),
            key_factors=key_factors,
            relevant_traits=relevant,
            time_horizon=horizon,
            llm_prior=prior,
            prior_reasoning=_opt_str("prior_reasoning"),
        )


class QuestionAnalyzer:
    """Wraps an ``ILLMBackend`` and produces ``QuestionAnalysis`` objects.

    Sprint 18 WP2: optionally consults a ``WebResearcher`` to fold
    current web context into the analysis prompt. When the researcher
    is unavailable / fails, the analyzer runs exactly like Sprint 17
    (training-data-only LLM prior).
    """

    def __init__(
        self,
        llm_backend: ILLMBackend | None,
        web_researcher: object | None = None,
    ) -> None:
        self._llm = llm_backend
        # Typed as `object` to avoid an import cycle with web_researcher
        # (which itself imports from realm.llm). The runtime contract
        # is: ``web_researcher.research(question, category_id)`` returns
        # an object with ``.context`` (str) and ``.sources`` (iterable
        # of WebResearchSource) — or None.
        self._web = web_researcher

    def analyze(
        self,
        question: str,
        category: CategoryMatch,
        *,
        enable_web_research: bool = True,
    ) -> QuestionAnalysis | None:
        """Call LLM and return a structured analysis, or ``None`` on any
        failure path. Caller treats ``None`` as "no analysis available;
        skip blending and narrative."

        Sprint 18 WP2: ``enable_web_research`` toggles the web research
        step. Set False to force training-data-only LLM prior — used
        by the Polymarket backtest A/B path to keep web research out
        of the comparison."""
        if self._llm is None:
            return None

        # Sprint 18 WP2: optional web research before the analyzer LLM
        # call. None on any failure → analyzer runs without web context.
        web_context = ""
        web_result = None
        if enable_web_research and self._web is not None:
            try:
                web_result = self._web.research(question, category.category_id)
                if web_result is not None:
                    web_context = web_result.context
            except Exception as e:
                logger.warning("web research raised (%s); skipping", e)

        prompt = load_split_prompt("question/analyze")
        trait_list = "\n".join(f"  - {t}" for t in TraitVector.trait_names())
        user = prompt.render_user(
            question=question,
            category_id=category.category_id,
            category_label=category.label,
            trait_list=trait_list,
            web_context=web_context or "(no current web research available)",
        )

        try:
            data = self._llm.complete_json(
                prompt.system, user, temperature=0.2, max_tokens=1024,
            )
        except (LLMBackendError, ValueError, KeyError) as e:
            logger.warning("LLM question analysis failed (%s); skipping", e)
            return None

        if not isinstance(data, Mapping):
            logger.warning("LLM question analysis returned non-mapping; skipping")
            return None

        analysis = QuestionAnalysis.from_llm_dict(question, category, data)
        if analysis is None:
            logger.warning(
                "LLM question analysis schema mismatch (keys=%s); skipping",
                list(data.keys()),
            )
            return None

        if web_result is not None:
            analysis = dataclasses.replace(analysis, web_result=web_result)
        return analysis
