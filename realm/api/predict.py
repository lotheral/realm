"""FastAPI predict endpoint for the v2 dashboard.

Runs category-routed multi-branch simulation, then derives a calibrated
``probability`` from the per-branch population trait deviations rather than
from raw threshold crossings (which saturated at 1.0 in Sprint 12). The
underlying ``PredictionOutcome`` only carries ``probability`` /
``mean_value`` / ``stddev_value`` / ``confidence`` (float 0..1); the
dashboard fields (drivers / dissent / agents_supporting/opposing/neutral
/ trait_shifts / answer text / confidence string) are synthesised from
the captured agent population.

Sprint 13 fixes three P0 bugs identified in live testing:

* **Bug 1 (degenerate consensus).** ``probability`` was raw-trait-threshold,
  always saturating to 1.0. Replaced with a sigmoid over weighted population
  trait deviations vs the unperturbed tick-0 baseline. Clamped to [0.05, 0.95].
* **Bug 2 (excessive trait shifts).** ``trait_shifts`` reported population
  mean minus 0.5 (baseline distribution skew, mislabelled as drift).
  Replaced with effective drift = ``post_tick_N_mean - tick_0_mean``,
  bounded by the ExperienceDriftEngine's ±max_drift_ratio cap (0.10).
* **Bug 3 (zero scenario delta).** Scenario branches now run with a
  perturbed ``agent_builder`` that shifts 70% of agents on the category's
  primary traits by a sentiment-parsed perturbation in [-0.15, +0.15].
  The remaining 30% are baked-in skeptics.

Run locally with::

    .venv/Scripts/python.exe -m uvicorn realm.api.predict:app \\
        --host 127.0.0.1 --port 8420 --reload
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import replace as _dc_replace
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

# Sprint 17: auto-load .env at module import so realm_start.bat (which just
# calls uvicorn directly, without dotenv) still picks up REALM_LLM_*
# variables. Silently no-ops when python-dotenv isn't installed or the
# .env file is missing — the env-var-only path keeps working.
try:
    from dotenv import load_dotenv as _load_dotenv

    _DOTENV_PATH = Path(__file__).resolve().parents[2] / ".env"
    if _DOTENV_PATH.exists():
        _load_dotenv(_DOTENV_PATH, override=False)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from realm import __version__ as _realm_version
from realm.core.config import load_realm_config
from realm.core.logging import get_logger
from realm.ingestion.interfaces import SeedEvent

# Sprint 14 WP5: word lists were lifted out of this module into
# `realm/ingestion/sentiment.py` so the dashboard's RSS feed parser shares
# them. Sprint 20: switched from the strict base-only variant to the FULL
# inventory — the Sprint 20 diagnosis showed the strict list misreading
# clearly-bearish feeds as neutral, and direction correctness of the
# scenario channel now outranks bit-compatibility with the Sprint 13
# acceptance numbers (see outputs/sprint20_question_blindness.md).
from realm.ingestion.sentiment import parse_sentiment as _parse_sentiment
from realm.output.category_router import CategoryMatch, default_router
from realm.output.predictor import (
    BranchSpec,
    build_branch_sim,
    observe_category_consensus,
)

logger = get_logger(__name__)

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Sprint 20: availability banner moved from import time to app startup
    # so importing this module has no logging / env-probing side effects.
    _log_llm_availability()
    yield


app = FastAPI(
    title="REALM Prediction API",
    description="Category-routed multi-branch prediction for the v2 dashboard.",
    version=_realm_version,
    lifespan=_lifespan,
)

# CORS — dashboard runs from a file:// origin or localhost; allow all for
# local dev. Lock down in production.
# TODO: production deployment must restrict allow_origins to the served
# dashboard origin instead of "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Sprint 20: every component below resolves its optional LLM backend
# through realm.llm.router.backend_for — ONE strict env-gate parse, one
# graceful-degradation contract — and is constructed lazily on first use
# (importing this module no longer probes the environment or builds
# backends as a side effect). @lru_cache(maxsize=1) keeps the
# once-per-process singleton behavior the endpoint always had.


@lru_cache(maxsize=1)
def _get_router():
    return default_router()


# Sprint 17 WP6 (reworked Sprint 20): one-line LLM availability log at app
# STARTUP (not import). Uses the same strict gate as the components, so
# the banner can no longer disagree with the router's actual state.
def _log_llm_availability() -> None:
    from realm.llm.router import env_gate_enabled, is_llm_configured
    gate_on = env_gate_enabled("REALM_LLM_CATEGORY_BACKEND")
    if gate_on and is_llm_configured():
        logger.info(
            "[REALM] LLM backend ACTIVE — LLM-first routing + question / "
            "scenario / narrative analysis enabled",
        )
    else:
        reason = (
            "no API key" if gate_on else "REALM_LLM_CATEGORY_BACKEND not enabled"
        )
        logger.info(
            "[REALM] LLM backend INACTIVE (%s) — running in simulation-only "
            "mode; set REALM_LLM_CATEGORY_BACKEND=1 + an OPENAI_API_KEY / "
            "MOONSHOT_API_KEY in .env for full LLM intelligence",
            reason,
        )


@lru_cache(maxsize=1)
def _get_question_analyzer():
    """Sprint 17 WP2 + Sprint 18 WP2: LLM-backed question analyzer with
    optional web research (``REALM_WEB_SEARCH_PROVIDER`` + matching key;
    silently no-ops when unconfigured)."""
    from realm.llm.router import TASK_CATEGORY, backend_for
    from realm.llm.web_researcher import default_web_researcher
    from realm.output.question_analyzer import QuestionAnalyzer
    backend = backend_for(TASK_CATEGORY)
    # Build researcher even when LLM backend is None — analyzer.is_available()
    # correctly reports False in that case so .research() short-circuits.
    web = default_web_researcher(backend)
    return QuestionAnalyzer(backend, web_researcher=web)


@lru_cache(maxsize=1)
def _get_scenario_analyzer():
    """Sprint 17 WP3: LLM-backed scenario analyzer (same gate as the
    question analyzer)."""
    from realm.llm.router import TASK_CATEGORY, backend_for
    from realm.output.scenario_analyzer import ScenarioAnalyzer
    return ScenarioAnalyzer(backend_for(TASK_CATEGORY))


@lru_cache(maxsize=1)
def _get_narrator():
    """Sprint 17 WP4: LLM-backed prediction narrator (same gate as the
    question + scenario analyzers)."""
    from realm.llm.router import TASK_CATEGORY, backend_for
    from realm.output.prediction_narrator import PredictionNarrator
    return PredictionNarrator(backend_for(TASK_CATEGORY))


def _blend_with_llm_prior(
    sim_prob: float, llm_prior: float | None, blend_weight: float,
) -> tuple[float, float | None]:
    """Sprint 17 WP2: blend the simulation probability with the LLM prior.

    Returns a 2-tuple ``(final_prob, blended_prob)``:
      - ``llm_prior is None`` (LLM unavailable / analyzer failed) →
        ``final = sim_prob`` and ``blended = None``. Callers can detect
        the no-blend case by checking ``blended_prob is None``.
      - ``llm_prior is not None`` → ``final = blended = (1-w)*sim + w*prior``,
        clamped to ``_PROBABILITY_CLAMP`` ([0.05, 0.95]).

    The blend weight ``w`` comes from ``CategoryMatch.llm_blend_weight``
    (per-category in ``config/prediction_categories.json``). Higher ``w``
    leans on the LLM's factual context (science 0.7); lower ``w`` keeps
    the swarm-sentiment signal dominant (crypto 0.3).
    """
    if llm_prior is None:
        return sim_prob, None
    sim_weight = 1.0 - blend_weight
    blended = (sim_weight * sim_prob) + (blend_weight * llm_prior)
    blended = max(_PROBABILITY_CLAMP[0], min(_PROBABILITY_CLAMP[1], blended))
    return blended, blended


@lru_cache(maxsize=1)
def _get_feed_parser():
    """Sprint 14 WP5 FeedParser. Falls back to the heuristic inventory
    when no parser-task LLM is configured (own gate env var)."""
    from realm.ingestion.feed_parser import FeedParser
    from realm.llm.router import TASK_PARSER, backend_for
    backend = backend_for(TASK_PARSER, env_var="REALM_LLM_PARSER_BACKEND")
    return FeedParser(category_router=_get_router(), llm_backend=backend)

# Sprint 13 calibration knobs.
_SIGMOID_SENSITIVITY = 8.0     # ±0.10 deviation -> ~31%-69%
_PROBABILITY_CLAMP = (0.05, 0.95)
_BUCKET_MIN_THRESHOLD = 0.005  # avoids all-neutral degenerate split when σ≈0
_PERTURBATION_RATIO = 0.7      # share of agents affected by scenario_feed
_PERTURBATION_MAX = 0.15       # cap on per-trait scenario perturbation
_BRANCH_SEED_OFFSET = 1000     # mirrors PredictionEngine.branch_seed_offset


# ---- Request / response schemas ------------------------------------------


class PredictRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    n_agents: int = Field(default=100, ge=10, le=2000)
    n_ticks: int = Field(default=30, ge=5, le=100)
    n_branches: int = Field(default=5, ge=1, le=20)
    scenario_feed: str | None = Field(default=None, max_length=2000)
    master_seed: int | None = None
    # Sprint 18 WP1 — A/B toggles for backtesting. Default True/True
    # preserves the Sprint 17 production behavior. The Polymarket
    # backtest script flips these to compare LLM-only vs sim-only vs
    # blended Brier scores.
    use_llm: bool = True
    use_sim: bool = True
    # Sprint 18 WP2 — opt-in web research before the question analyzer
    # LLM call. When True (default) and a search provider is configured
    # (REALM_WEB_SEARCH_PROVIDER + key in .env) the LLM prior is
    # informed by current web context. Set False to force training-data-
    # only LLM prior (Sprint 17 behavior, useful for backtest A/B).
    enable_web_research: bool = True


class PredictResponse(BaseModel):
    question: str
    category_id: str
    category_label: str
    primary_traits: list[str]
    subcategory: str | None
    probability: float
    confidence: str
    answer: str
    drivers: list[str]
    dissent: str
    trait_shifts: dict[str, float]
    agents_supporting: float
    agents_opposing: float
    agents_neutral: float
    branch_values: list[float]
    n_agents: int
    n_ticks: int
    n_branches: int
    # Scenario fields (only set when scenario_feed was provided)
    baseline_probability: float | None = None
    delta: float | None = None
    # Sprint 17 WP2 — LLM question analysis (None when LLM unavailable
    # or analyzer returned no usable result).
    subject: str | None = None
    yes_means: str | None = None
    no_means: str | None = None
    llm_prior: float | None = None
    prior_reasoning: str | None = None
    # Sprint 17 WP2 — probability blending diagnostics. simulation_probability
    # is the pre-blend (sigmoid + offset) result; blended_probability is the
    # post-blend value. Both are equal to .probability when blending ran;
    # both are None when LLM was unavailable (.probability == sim only).
    simulation_probability: float | None = None
    blended_probability: float | None = None
    # Sprint 17 WP4 — LLM-generated narrative. None when LLM unavailable.
    headline: str | None = None
    narrative_drivers: list[str] | None = None
    dissent_narrative: str | None = None
    confidence_note: str | None = None
    caveat: str | None = None
    # Sprint 18 WP2 — web-research diagnostics. None when web research
    # was disabled / unavailable / failed.
    web_research_used: bool = False
    web_sources: list[str] | None = None
    # Sprint 19.1 — scenario perturbation reporting. Sprint 13's
    # trait_shifts deliberately reports drift ONLY (post-sim minus
    # post-perturbation tick0) so the user-injected perturbation does
    # not double-count. That makes scenario trait_shifts look like ±0
    # even when probability moved a lot. These two new fields surface
    # WHAT THE SCENARIO INJECTED (per-trait) and WHAT THE SCENARIO
    # WAS ABOUT (LLM event summary) so the dashboard can explain the
    # delta to the user.
    scenario_perturbation: dict[str, float] | None = None
    scenario_event_summary: str | None = None
    # Sprint 19.2 — delta decomposition. Sprint 19's dual blend weights
    # (baseline LLM-dominant 0.85-0.95 vs scenario sim-dominant 0.40)
    # introduce a mechanical shift component into the scenario delta:
    # even if the simulation didn't move, switching from baseline to
    # scenario weights pulls probability toward the sim signal. This
    # decomposition surfaces both contributions so users can tell the
    # mechanical shift apart from the actual scenario response.
    # delta_total == delta_blend_shift + delta_sim_movement (within rounding)
    delta_blend_shift: float | None = None
    delta_sim_movement: float | None = None
    delta_total: float | None = None


# ---- Sentiment parsing for scenario perturbation ------------------------

_MIN_PERTURBATION = 0.08  # magnitude floor once a DIRECTION is resolved (neutral parses apply zero — Sprint 20)


def _perturbation_for_feed(feed: str) -> float:
    """Convert a scenario_feed string into a per-trait perturbation in
    [-_PERTURBATION_MAX, +_PERTURBATION_MAX]. Magnitude is floored at
    ``_MIN_PERTURBATION`` when a direction is resolved.

    Sprint 20: a neutral parse now returns 0.0. The old behavior — a
    +0.08 positive nudge whenever the feed parsed neutral — fabricated
    a direction the feed never expressed, which the Sprint 20 diagnosis
    caught treating clearly-bearish feeds as bullish. With the scenario
    delta as REALM's primary product, no movement is more honest than
    invented movement; operators wanting semantic direction on ambiguous
    feeds should enable the LLM scenario analyzer."""
    sentiment = _parse_sentiment(feed)
    if sentiment > 0:
        magnitude = max(_MIN_PERTURBATION, min(_PERTURBATION_MAX, sentiment * 2.0))
        return magnitude
    if sentiment < 0:
        magnitude = max(_MIN_PERTURBATION, min(_PERTURBATION_MAX, -sentiment * 2.0))
        return -magnitude
    logger.warning(
        "scenario_feed parsed as sentiment-neutral — applying NO population "
        "perturbation (direction would be fabricated). Enable the LLM "
        "scenario analyzer or use clearer sentiment wording for a "
        "directional scenario.",
    )
    return 0.0


def _make_perturbed_agent_builder(
    scenario_feed: str,
    category: CategoryMatch,
    *,
    scenario_analysis: object | None = None,
):
    """Return an ``agent_builder`` that perturbs agents to reflect the
    user-provided scenario_feed.

    Sprint 17 WP3: when ``scenario_analysis`` is a ``ScenarioAnalysis``
    instance (LLM-derived), use its per-trait ``trait_impacts`` dict and
    its ``affected_population_pct`` — the perturbation is semantic
    (different traits move by different amounts based on the LLM's read
    of the scenario). When ``scenario_analysis`` is None (no LLM /
    analyzer failed), fall back to the pre-Sprint-17 path: a single
    sentiment-parsed scalar applied uniformly to the category's primary
    traits in 70% of agents (Sprint 13 contract preserved).

    Sprint 14 WP2: the inner AgentFactory receives the category's
    ``trait_seed_offsets`` so the starting population already reflects
    the question's domain BEFORE the scenario perturbation layers on.
    """
    seed_offsets = dict(category.trait_seed_offsets)

    # Two perturbation modes — pick once outside the builder closure to
    # avoid recomputing per-call.
    if scenario_analysis is not None and getattr(
        scenario_analysis, "trait_impacts_dict", None
    ):
        # LLM mode: per-trait deltas + LLM-derived affected fraction
        trait_impacts: dict[str, float] = scenario_analysis.trait_impacts_dict
        affected_ratio: float = float(scenario_analysis.affected_population_pct)
        perturbation_scalar = None
    else:
        # Heuristic mode (Sprint 13 path): scalar applied uniformly to
        # the category's primary traits in a 70% subset.
        trait_impacts = {}
        affected_ratio = _PERTURBATION_RATIO
        perturbation_scalar = _perturbation_for_feed(scenario_feed)

    primary = list(category.primary_traits)

    def builder(seed: int, n_agents: int) -> list:
        from realm.agents.factory import AgentFactory
        from realm.demographics.world_generator import WorldGenerator

        agents = AgentFactory(seed_offsets=seed_offsets).build_batch(
            WorldGenerator(master_seed=seed).generate(n_agents)
        )

        # No-op cases: no traits to push (heuristic mode + zero scalar)
        # or no impacts (LLM mode but empty after sanitization — should
        # not happen since analyzer returns None in that case).
        if perturbation_scalar == 0.0 or (
            perturbation_scalar is None and not trait_impacts
        ):
            return agents
        if perturbation_scalar is not None and not primary:
            return agents

        rng = random.Random(seed + 9001)
        n_affected = max(1, int(len(agents) * affected_ratio))
        affected_idx = set(rng.sample(range(len(agents)), n_affected))

        new_agents: list = []
        for i, agent in enumerate(agents):
            if i not in affected_idx:
                new_agents.append(agent)
                continue
            trait_updates: dict[str, float] = {}
            if perturbation_scalar is not None:
                # Heuristic: same scalar across all primary traits
                for trait in primary:
                    current = float(getattr(agent.traits, trait, 0.5))
                    trait_updates[trait] = max(
                        0.0, min(1.0, current + perturbation_scalar),
                    )
            else:
                # LLM mode: per-trait delta from the analyzer
                for trait, delta in trait_impacts.items():
                    current = float(getattr(agent.traits, trait, 0.5))
                    trait_updates[trait] = max(0.0, min(1.0, current + delta))
            new_traits = _dc_replace(agent.traits, **trait_updates)
            new_agents.append(_dc_replace(agent, traits=new_traits))
        return new_agents

    return builder


# ---- Effective-trait helpers --------------------------------------------


def _effective_traits(sim: Any, agent: Any):
    """Return the agent's drift-applied trait vector when an
    ExperienceDriftEngine is attached to the simulation, else the raw
    immutable traits. Drift is bounded by ±max_drift_ratio in the engine."""
    eng = getattr(sim, "drift_engine", None)
    if eng is not None:
        return eng.current_traits(agent)
    return agent.traits


def _trait_means(sim: Any, traits: list[str]) -> dict[str, float]:
    if not sim.agents or not traits:
        return {}
    out: dict[str, float] = {}
    for trait in traits:
        vals = [float(getattr(_effective_traits(sim, a), trait, 0.5)) for a in sim.agents]
        if vals:
            out[trait] = statistics.mean(vals)
    return out


def _trait_stdevs(sim: Any, traits: list[str]) -> dict[str, float]:
    if not sim.agents or not traits:
        return {}
    out: dict[str, float] = {}
    for trait in traits:
        vals = [float(getattr(_effective_traits(sim, a), trait, 0.5)) for a in sim.agents]
        if len(vals) > 1:
            out[trait] = statistics.pstdev(vals)
    return out


def _category_weights(category: CategoryMatch) -> dict[str, float]:
    weighted: dict[str, float] = {}
    for trait in category.primary_traits:
        weighted[trait] = 2.0
    for trait in category.secondary_traits:
        weighted.setdefault(trait, 1.0)
    for trait in category.suppressed_traits:
        weighted.setdefault(trait, 0.25)
    if not weighted:
        # Pure balanced category — equal weight on every TraitVector axis so
        # the calibrator still has something to compare against.
        from realm.personality.trait_vector import TraitVector

        weighted = dict.fromkeys(TraitVector.trait_names(), 1.0)
    return weighted


def _weighted_population_deviation(
    sim: Any, baseline_means: Mapping[str, float], weights: Mapping[str, float],
) -> float:
    wsum = sum(weights.values()) or 1.0
    post_means = _trait_means(sim, list(weights))
    return sum(
        w * (post_means.get(t, 0.5) - baseline_means.get(t, 0.5))
        for t, w in weights.items()
    ) / wsum


def _per_agent_deviations(
    sim: Any, baseline_means: Mapping[str, float], weights: Mapping[str, float],
) -> list[float]:
    wsum = sum(weights.values()) or 1.0
    devs: list[float] = []
    for agent in sim.agents:
        eff = _effective_traits(sim, agent)
        score = sum(
            w * (float(getattr(eff, t, 0.5)) - baseline_means.get(t, 0.5))
            for t, w in weights.items()
        ) / wsum
        devs.append(score)
    return devs


def _bucket_three_way(devs: list[float]) -> tuple[float, float, float]:
    if not devs:
        return (0.34, 0.33, 0.33)
    sigma = statistics.pstdev(devs) if len(devs) > 1 else 0.0
    threshold = max(_BUCKET_MIN_THRESHOLD, 0.5 * sigma)
    sup = sum(1 for d in devs if d > threshold)
    opp = sum(1 for d in devs if d < -threshold)
    neu = len(devs) - sup - opp
    n = float(len(devs))
    return (sup / n, opp / n, neu / n)


# ---- Synthesis helpers ---------------------------------------------------


_CONFIDENCE_BUCKETS = [
    (0.20, "high"),
    (0.13, "medium-high"),
    (0.07, "medium"),
    (0.03, "low-medium"),
    (0.0, "low"),
]


def _confidence_label_from_distance(distance_from_mid: float) -> str:
    """Confidence is now driven by how far the calibrated probability sits
    from 50% (raw branch stdev confused 'all branches saturated to 1.0'
    with 'high confidence'). 50% prob -> low; 95%/5% -> high."""
    for threshold, label in _CONFIDENCE_BUCKETS:
        if distance_from_mid >= threshold:
            return label
    return "low"


def _answer_text(probability: float) -> str:
    if probability >= 0.75:
        return "LIKELY YES"
    if probability >= 0.55:
        return "LEANING YES"
    if probability > 0.45:
        return "TOSS-UP"
    if probability > 0.25:
        return "LEANING NO"
    return "LIKELY NO"


def _build_drivers(
    category: CategoryMatch,
    trait_means: Mapping[str, float],
    trait_stdevs: Mapping[str, float],
    trait_shifts: Mapping[str, float],
) -> list[str]:
    drivers: list[str] = []
    primary = list(category.primary_traits)[:3] or list(category.secondary_traits)[:3]
    for trait in primary:
        mean = trait_means.get(trait, 0.5)
        sigma = trait_stdevs.get(trait, 0.0)
        shift = trait_shifts.get(trait, 0.0)
        tone = "elevated" if mean > 0.55 else ("muted" if mean < 0.45 else "near-neutral")
        spread = "tight cluster" if sigma < 0.08 else (
            "broad spread" if sigma > 0.16 else "moderate spread"
        )
        direction = (
            "drifted up" if shift > 0.005 else (
                "drifted down" if shift < -0.005 else "held steady"
            )
        )
        drivers.append(
            f"{trait} mean {mean:.2f} ({tone}, {spread} σ={sigma:.2f}); {direction} {shift:+.3f}"
        )
    if not drivers:
        drivers.append(
            f"{category.label}: balanced — no category-emphasised traits to report"
        )
    return drivers


def _build_dissent(
    category: CategoryMatch,
    trait_stdevs: Mapping[str, float],
    sup: float, opp: float, neu: float,
) -> str:
    if not category.primary_traits:
        return "Balanced fallback: no category-specific dissent cluster identified"
    spreads = [(t, trait_stdevs.get(t, 0.0)) for t in category.primary_traits]
    spreads.sort(key=lambda x: x[1], reverse=True)
    trait, sigma = spreads[0]
    return (
        f"{int(round(opp * 100))}% of agents oppose, {int(round(neu * 100))}% neutral; "
        f"primary disagreement on {trait} (σ={sigma:.2f})."
    )


# ---- Branch runner -------------------------------------------------------


def _seed_event_from_text(text: str, when: datetime) -> SeedEvent:
    sentiment = max(-1.0, min(1.0, _parse_sentiment(text) * 4.0))
    return SeedEvent(
        event_id="dashboard:scenario",
        source="dashboard:user_input",
        timestamp=when,
        headline=text[:140],
        body=text,
        topic="news",
        sentiment=sentiment,
        virality=4.0,
        entities=(),
        geography=None,
    )


def _resolve_seed(req: PredictRequest) -> int:
    if req.master_seed is not None:
        return req.master_seed
    cfg = load_realm_config()
    return int(cfg["realm"]["simulation"]["master_seed"])


def _capture_baseline_means(
    master_seed: int, n_agents: int, traits: list[str],
    *,
    seed_offsets: dict[str, float] | None = None,
    drift_event_weights: dict[str, float] | None = None,
    drift_volatility: float = 1.0,
    drift_asymmetry_positive: float = 1.0,
    drift_asymmetry_negative: float = 1.0,
    primary_traits: tuple[str, ...] = (),
) -> dict[str, float]:
    """Run a 0-tick reference sim with the unperturbed default agent_builder
    and return the trait population means at tick 0. This is the universal
    calibration baseline; both baseline and scenario branches measure their
    deviations against it so a perturbed scenario actually moves probability.

    Sprint 14 WP1+WP2: the reference sim is built with the active category's
    ``seed_offsets`` and ``drift_event_weights`` so the baseline reflects the
    same starting population shape used by all branches; otherwise the 0-tick
    reference would diverge from per-branch tick-0 means and ``trait_shifts``
    would mis-report the offset itself as drift (Sprint 13 collateral bug)."""
    ref_sim = build_branch_sim(
        master_seed, n_agents,
        seed_offsets=seed_offsets,
        drift_event_weights=drift_event_weights,
        drift_volatility=drift_volatility,
        drift_asymmetry_positive=drift_asymmetry_positive,
        drift_asymmetry_negative=drift_asymmetry_negative,
        primary_traits=primary_traits,
    )
    return _trait_means(ref_sim, traits)


def _run_branches(
    *, master_seed: int, n_agents: int, n_ticks: int, n_branches: int,
    initial_events: tuple = (), agent_builder=None,
    tick0_traits: list[str] | None = None,
    seed_offsets: dict[str, float] | None = None,
    drift_event_weights: dict[str, float] | None = None,
    drift_volatility: float = 1.0,
    drift_asymmetry_positive: float = 1.0,
    drift_asymmetry_negative: float = 1.0,
    primary_traits: tuple[str, ...] = (),
) -> tuple[list[Any], Any, dict[str, float]]:
    """Run all branches with optional perturbation. Returns
    ``(sims, last_sim, last_tick0_means)`` where ``last_tick0_means`` is the
    trait population means of the LAST branch *before* it ran. That is the
    correct baseline for reporting drift-only ``trait_shifts`` — including
    any agent_builder perturbation that shifted the initial state but
    excluding the perturbation itself from the displayed delta."""
    sims: list = []
    last_tick0_means: dict[str, float] = {}
    traits_to_capture = tick0_traits or []
    for i in range(n_branches):
        branch_seed = master_seed + _BRANCH_SEED_OFFSET * (i + 1)
        sim = build_branch_sim(
            branch_seed, n_agents,
            initial_events=initial_events,
            agent_builder=agent_builder,
            seed_offsets=seed_offsets,
            drift_event_weights=drift_event_weights,
            drift_volatility=drift_volatility,
            drift_asymmetry_positive=drift_asymmetry_positive,
            drift_asymmetry_negative=drift_asymmetry_negative,
            primary_traits=primary_traits,
        )
        if i == n_branches - 1 and traits_to_capture:
            last_tick0_means = _trait_means(sim, traits_to_capture)
        sim.run(n_ticks)
        sims.append(sim)
    return sims, sims[-1], last_tick0_means


def _calibrated_outcome(
    *, sims: list[Any], baseline_means: Mapping[str, float],
    category: CategoryMatch,
):
    """Compute calibrated probability + per-agent bucket from a list of
    completed branch sims and the universal baseline means.

    Sprint 15 WP4: sigmoid sensitivity is scaled per-category by
    ``category.sigmoid_sensitivity_multiplier``. Higher-volatility domains
    (crypto 1.4) amplify their already-wider deviations into wider
    probability swings; lower-volatility domains (politics 0.7) keep
    their tighter deviations close to 50%."""
    weights = _category_weights(category)
    branch_devs = [
        _weighted_population_deviation(sim, baseline_means, weights) for sim in sims
    ]
    mean_dev = statistics.mean(branch_devs) if branch_devs else 0.0
    effective_sensitivity = (
        _SIGMOID_SENSITIVITY * float(category.sigmoid_sensitivity_multiplier)
    )
    raw_prob = 1.0 / (1.0 + math.exp(-effective_sensitivity * mean_dev))
    probability = max(_PROBABILITY_CLAMP[0], min(_PROBABILITY_CLAMP[1], raw_prob))

    # Sprint 16 WP2: per-category last-mile probability offset. Applied AFTER
    # sigmoid + clamp so the underlying drift signal stays the dominant input;
    # offset is bounded to [-0.05, +0.05] in CategoryRouter validation. Used
    # only when drift mechanics alone cannot reach a category's calibration
    # target. Re-clamp keeps probability in [0.05, 0.95].
    offset = float(category.baseline_probability_offset)
    if offset != 0.0:
        probability = max(
            _PROBABILITY_CLAMP[0],
            min(_PROBABILITY_CLAMP[1], probability + offset),
        )

    # Per-agent bucket built from the LAST branch's population (which has
    # both the perturbation and the simulation-induced drift).
    agent_devs = _per_agent_deviations(sims[-1], baseline_means, weights)
    sup, opp, neu = _bucket_three_way(agent_devs)
    return probability, branch_devs, (sup, opp, neu)


# ---- Endpoint ------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "categories": list(_get_router().category_ids),
        "default_horizon_ticks": 30,
    }


# ---- Sprint 14 WP5 — feed parser endpoints ----------------------------


class FeedParseRequest(BaseModel):
    text: str | None = Field(default=None, max_length=10000)
    rss_url: str | None = Field(default=None, max_length=500)
    texts: list[str] | None = None


class FeedParseResponse(BaseModel):
    source: str
    title: str
    content: str
    timestamp: str
    sentiment_score: float
    keywords: list[str]
    detected_category: str | None
    items: list[str] = []


class FeedParseListResponse(BaseModel):
    items: list[FeedParseResponse]


@app.get("/api/feeds")
def list_feeds() -> dict[str, object]:
    """Return the pre-configured RSS feed sources for the scenario panel."""
    import json
    from pathlib import Path
    cfg_path = (
        Path(__file__).resolve().parents[2] / "config" / "feed_sources.json"
    )
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        # Sandbox safety: never crash the dashboard if the config is missing.
        return {"feeds": []}
    return {"feeds": cfg.get("feeds", [])}


def _parsed_to_response(parsed) -> FeedParseResponse:
    return FeedParseResponse(
        source=parsed.source,
        title=parsed.title,
        content=parsed.content,
        timestamp=parsed.timestamp.isoformat(),
        sentiment_score=parsed.sentiment_score,
        keywords=list(parsed.keywords),
        detected_category=parsed.detected_category,
        items=list(parsed.items),
    )


@app.post("/api/feed/parse", response_model=FeedParseListResponse)
def parse_feed(req: FeedParseRequest) -> FeedParseListResponse:
    """Parse a manual text, an RSS URL, or a list of texts into ParsedFeed
    payloads. Sentiment + keyword extraction shared with /api/predict's
    scenario perturbation pipeline."""
    if req.rss_url:
        items = _get_feed_parser().parse_rss(req.rss_url, max_items=5)
        return FeedParseListResponse(items=[_parsed_to_response(p) for p in items])
    if req.texts:
        agg = _get_feed_parser().parse_multiple(list(req.texts))
        return FeedParseListResponse(items=[_parsed_to_response(agg)])
    if req.text:
        single = _get_feed_parser().parse_text(req.text)
        return FeedParseListResponse(items=[_parsed_to_response(single)])
    raise HTTPException(
        status_code=422,
        detail="provide one of: text, rss_url, or texts (non-empty)",
    )


@app.post("/api/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest) -> PredictResponse:
    try:
        category = _get_router().route(req.question)
        master_seed = _resolve_seed(req)

        # Sprint 17 WP2: LLM question analysis (one call per request).
        # Returns None on any LLM failure path; downstream code treats
        # `None` as "no analysis available, no blending, no narrative."
        # Sprint 18 WP1: skip entirely when ``use_llm=False`` (backtest
        # A/B path that isolates the simulation signal).
        # Sprint 18 WP2: pass through enable_web_research toggle so
        # backtests can isolate web-research impact independently.
        analysis = (
            _get_question_analyzer().analyze(
                req.question, category,
                enable_web_research=req.enable_web_research,
            )
            if req.use_llm else None
        )
        # Sprint 20: web research metadata travels inside the returned
        # analysis (the old instance-attribute side channel leaked stale
        # results across requests and raced under FastAPI's threadpool).
        web_result = analysis.web_result if analysis is not None else None
        llm_prior = analysis.llm_prior if analysis is not None else None
        # Sprint 19 WP1: separate baseline vs scenario blend weights.
        # Sprint 18 backtest showed sim adds NEGATIVE value to baseline
        # predictions (+0.048 Brier), so baseline now LLM-dominant
        # (0.85-0.95) and scenario now sim-dominant (0.40 LLM / 0.60 sim).
        baseline_blend_weight = float(category.llm_blend_weight)
        scenario_blend_weight = float(category.scenario_llm_blend_weight)

        # Sprint 18 WP1: LLM-only fast path. When use_sim=False the entire
        # simulation pipeline is bypassed and the response carries the
        # LLM prior as the probability. When BOTH use_llm and use_sim are
        # False we return 0.5 (no signal), which is also handy as a
        # null-baseline in Brier comparisons.
        if not req.use_sim:
            llm_only_prob = llm_prior if llm_prior is not None else 0.5
            return PredictResponse(
                question=req.question,
                category_id=category.category_id,
                category_label=category.label,
                primary_traits=list(category.primary_traits),
                subcategory=category.subcategory,
                probability=round(llm_only_prob, 4),
                confidence=_confidence_label_from_distance(
                    abs(llm_only_prob - 0.5)
                ),
                answer=_answer_text(llm_only_prob),
                drivers=[],
                dissent="",
                trait_shifts={},
                agents_supporting=0.0,
                agents_opposing=0.0,
                agents_neutral=1.0,
                branch_values=[],
                n_agents=req.n_agents,
                n_ticks=req.n_ticks,
                n_branches=req.n_branches,
                # LLM analysis fields populated as usual when available
                subject=analysis.subject if analysis else None,
                yes_means=analysis.yes_means if analysis else None,
                no_means=analysis.no_means if analysis else None,
                llm_prior=(
                    round(analysis.llm_prior, 4)
                    if analysis and analysis.llm_prior is not None else None
                ),
                prior_reasoning=analysis.prior_reasoning if analysis else None,
                # No simulation ran → both diagnostic fields None
                simulation_probability=None,
                blended_probability=None,
                # Sprint 18 WP2 — web research diagnostics
                web_research_used=web_result is not None,
                web_sources=(
                    [s.url for s in web_result.sources]
                    if web_result is not None else None
                ),
            )

        # Baseline means must include every trait the category cares about so
        # both calibration and trait_shifts can compute against them.
        all_relevant = (
            list(category.primary_traits)
            + list(category.secondary_traits)
            + list(category.suppressed_traits)
        ) or ["openness"]
        # Sprint 14 WP1+WP2: pull category-conditioned drift weights and
        # zero-sum trait seed offsets. Both the 0-tick reference baseline
        # and every branch run share the same offsets/weights so trait_shifts
        # reports drift only (not the offset itself).
        # Sprint 15 WP2+WP3: pull volatility + asymmetry; same propagation.
        seed_offsets = dict(category.trait_seed_offsets)
        # Sprint 18 WP3 + Sprint 19 WP3: when the LLM router returned
        # multi-category, blend ALL category-dependent parameters across
        # the set (Sprint 18 only blended drift_event_weights; Sprint 19
        # extends to sigmoid sensitivity, drift volatility, asymmetry,
        # and baseline_probability_offset). The blended view is
        # constructed via dataclass.replace so downstream code (incl.
        # _calibrated_outcome) reads the blended scalars transparently.
        if category.secondary_categories:
            from realm.output.category_router import blend_category_parameters
            secondary_data = {c["id"]: c for c in _get_router().categories}
            blended = blend_category_parameters(category, secondary_data)
            category = _dc_replace(
                category,
                drift_event_weights=blended["drift_event_weights"],
                drift_volatility=blended["drift_volatility"],
                drift_asymmetry_positive=blended["drift_asymmetry_positive"],
                drift_asymmetry_negative=blended["drift_asymmetry_negative"],
                sigmoid_sensitivity_multiplier=blended["sigmoid_sensitivity_multiplier"],
                baseline_probability_offset=blended["baseline_probability_offset"],
            )
        drift_event_weights = dict(category.drift_event_weights)
        drift_volatility = float(category.drift_volatility)
        drift_pos = float(category.drift_asymmetry_positive)
        drift_neg = float(category.drift_asymmetry_negative)
        primary_traits = tuple(category.primary_traits)
        baseline_means = _capture_baseline_means(
            master_seed, req.n_agents, all_relevant,
            seed_offsets=seed_offsets,
            drift_event_weights=drift_event_weights,
            drift_volatility=drift_volatility,
            drift_asymmetry_positive=drift_pos,
            drift_asymmetry_negative=drift_neg,
            primary_traits=primary_traits,
        )

        # Baseline run (no perturbation, no scenario feed).
        baseline_sims, baseline_last, baseline_tick0 = _run_branches(
            master_seed=master_seed,
            n_agents=req.n_agents, n_ticks=req.n_ticks,
            n_branches=req.n_branches,
            tick0_traits=all_relevant,
            seed_offsets=seed_offsets,
            drift_event_weights=drift_event_weights,
            drift_volatility=drift_volatility,
            drift_asymmetry_positive=drift_pos,
            drift_asymmetry_negative=drift_neg,
            primary_traits=primary_traits,
        )
        baseline_probability, baseline_branch_devs, baseline_buckets = _calibrated_outcome(
            sims=baseline_sims, baseline_means=baseline_means, category=category,
        )
        baseline_sim_probability = baseline_probability  # pre-blend snapshot
        baseline_probability, baseline_blended = _blend_with_llm_prior(
            baseline_probability, llm_prior, baseline_blend_weight,
        )

        # Scenario run (only if a feed was supplied).
        scenario_probability: float | None = None
        scenario_buckets: tuple[float, float, float] | None = None
        scenario_branch_devs: list[float] | None = None
        scenario_last: Any | None = None
        scenario_tick0: dict[str, float] = {}
        scenario_analysis = None
        # Sprint 19.1: capture per-trait scenario perturbation for the
        # response so the dashboard can show "what the scenario pushed"
        # alongside Sprint 13's drift-only trait_shifts.
        scenario_perturbation_dict: dict[str, float] | None = None
        scenario_event_summary_text: str | None = None
        if req.scenario_feed:
            # Sprint 17 WP3: LLM scenario analysis (None on failure → heuristic)
            scenario_analysis = _get_scenario_analyzer().analyze(
                req.scenario_feed, req.question, category,
            )
            if scenario_analysis is not None:
                # LLM mode — per-trait deltas + event_summary
                scenario_perturbation_dict = dict(scenario_analysis.trait_impacts_dict)
                scenario_event_summary_text = scenario_analysis.event_summary or None
            else:
                # Heuristic fallback — scalar applied uniformly to primary traits
                scalar = _perturbation_for_feed(req.scenario_feed)
                if category.primary_traits and scalar != 0.0:
                    scenario_perturbation_dict = {
                        t: round(scalar, 4) for t in category.primary_traits
                    }
            agent_builder = _make_perturbed_agent_builder(
                req.scenario_feed, category, scenario_analysis=scenario_analysis,
            )
            seed_event = _seed_event_from_text(req.scenario_feed, datetime.now(UTC))
            scenario_sims, scenario_last, scenario_tick0 = _run_branches(
                master_seed=master_seed,
                n_agents=req.n_agents, n_ticks=req.n_ticks,
                n_branches=req.n_branches,
                initial_events=(seed_event,),
                agent_builder=agent_builder,
                tick0_traits=all_relevant,
                seed_offsets=seed_offsets,
                drift_event_weights=drift_event_weights,
                drift_volatility=drift_volatility,
                drift_asymmetry_positive=drift_pos,
                drift_asymmetry_negative=drift_neg,
                primary_traits=primary_traits,
            )
            scenario_probability, scenario_branch_devs, scenario_buckets = _calibrated_outcome(
                sims=scenario_sims, baseline_means=baseline_means, category=category,
            )
            scenario_sim_probability = scenario_probability  # pre-blend snapshot
            scenario_probability, scenario_blended = _blend_with_llm_prior(
                scenario_probability, llm_prior, scenario_blend_weight,
            )

        active_probability = scenario_probability if scenario_probability is not None else baseline_probability
        active_branch_devs = scenario_branch_devs if scenario_branch_devs is not None else baseline_branch_devs
        active_buckets = scenario_buckets if scenario_buckets is not None else baseline_buckets
        active_last = scenario_last if scenario_last is not None else baseline_last
        # Drift baseline = tick-0 means of the ACTIVE branch. For scenario runs
        # this includes the perturbation, so trait_shifts reports drift only
        # (bounded by the 0.10 cap) and not the user-injected perturbation.
        active_tick0 = scenario_tick0 if scenario_probability is not None else baseline_tick0
        baseline_probability_field = baseline_probability if scenario_probability is not None else None
        delta = (
            scenario_probability - baseline_probability
            if scenario_probability is not None else None
        )

        # Sprint 19.2 — decompose the scenario delta into mechanical
        # blend-weight rebalancing vs actual simulation movement. Only
        # meaningful when both a scenario branch ran AND an LLM prior
        # is available (without a prior the baseline/scenario weights
        # both reduce to "sim only" — no rebalancing happens).
        delta_blend_shift_value: float | None = None
        delta_sim_movement_value: float | None = None
        delta_total_value: float | None = None
        if scenario_probability is not None and llm_prior is not None:
            # Hypothetical scenario probability if sim had stayed at the
            # baseline level — isolates the contribution of switching
            # from baseline_blend_weight to scenario_blend_weight.
            mechanical_scenario, _ = _blend_with_llm_prior(
                baseline_sim_probability, llm_prior, scenario_blend_weight,
            )
            delta_blend_shift_value = mechanical_scenario - baseline_probability
            delta_sim_movement_value = scenario_probability - mechanical_scenario
            delta_total_value = scenario_probability - baseline_probability

        # Stats from the active sim — uses effective drift-applied traits.
        primary_secondary = (
            list(category.primary_traits) + list(category.secondary_traits)
        )
        active_means = _trait_means(active_last, primary_secondary)
        active_stdevs = _trait_stdevs(active_last, primary_secondary)
        # Pure drift = effective_post_mean - active_tick0_mean. Always bounded
        # by the 0.10 ExperienceDriftEngine cap, regardless of perturbation.
        trait_shifts = {
            t: round(active_means.get(t, 0.5) - active_tick0.get(t, baseline_means.get(t, 0.5)), 4)
            for t in category.primary_traits
        }
        sup, opp, neu = active_buckets
        confidence = _confidence_label_from_distance(abs(active_probability - 0.5))

        # Sprint 17 WP2: pick which simulation_probability + blended_probability
        # to report. Active = scenario when present, else baseline.
        active_sim_prob = (
            scenario_sim_probability if scenario_probability is not None
            else baseline_sim_probability
        )
        active_blended = (
            scenario_blended if scenario_probability is not None
            else baseline_blended
        )

        # Sprint 17 WP4: LLM-driven narrative (None when LLM unavailable
        # or narrator returned no usable result). Uses pre-blend
        # simulation_probability AND post-blend probability so the
        # headline can compare the two.
        narrative = _get_narrator().narrate(
            question=req.question,
            category=category,
            analysis=analysis,
            probability=active_probability,
            simulation_probability=active_sim_prob,
            blended_probability=active_blended,
            supporting=sup,
            opposing=opp,
            neutral=neu,
            trait_shifts=trait_shifts,
            scenario_feed=req.scenario_feed,
            scenario_analysis=scenario_analysis,
            delta=delta,
        )

        return PredictResponse(
            question=req.question,
            category_id=category.category_id,
            category_label=category.label,
            primary_traits=list(category.primary_traits),
            subcategory=category.subcategory,
            probability=round(active_probability, 4),
            confidence=confidence,
            answer=_answer_text(active_probability),
            drivers=_build_drivers(category, active_means, active_stdevs, trait_shifts),
            dissent=_build_dissent(category, active_stdevs, sup, opp, neu),
            trait_shifts=trait_shifts,
            agents_supporting=round(sup, 4),
            agents_opposing=round(opp, 4),
            agents_neutral=round(neu, 4),
            branch_values=[round(v, 4) for v in active_branch_devs],
            n_agents=req.n_agents,
            n_ticks=req.n_ticks,
            n_branches=req.n_branches,
            baseline_probability=(
                round(baseline_probability_field, 4)
                if baseline_probability_field is not None else None
            ),
            delta=(round(delta, 4) if delta is not None else None),
            # Sprint 17 WP2 — LLM analysis fields (None when LLM unavailable)
            subject=analysis.subject if analysis else None,
            yes_means=analysis.yes_means if analysis else None,
            no_means=analysis.no_means if analysis else None,
            llm_prior=(
                round(analysis.llm_prior, 4)
                if analysis and analysis.llm_prior is not None else None
            ),
            prior_reasoning=analysis.prior_reasoning if analysis else None,
            simulation_probability=round(active_sim_prob, 4),
            blended_probability=(
                round(active_blended, 4) if active_blended is not None else None
            ),
            # Sprint 17 WP4 — LLM narrative (None when LLM unavailable)
            headline=narrative.headline if narrative else None,
            narrative_drivers=(
                list(narrative.key_drivers) if narrative else None
            ),
            dissent_narrative=narrative.dissent_view if narrative else None,
            confidence_note=narrative.confidence_note if narrative else None,
            caveat=narrative.caveat if narrative else None,
            # Sprint 18 WP2 — web research diagnostics
            web_research_used=web_result is not None,
            web_sources=(
                [s.url for s in web_result.sources]
                if web_result is not None else None
            ),
            scenario_perturbation=scenario_perturbation_dict,
            scenario_event_summary=scenario_event_summary_text,
            delta_blend_shift=(
                round(delta_blend_shift_value, 4)
                if delta_blend_shift_value is not None else None
            ),
            delta_sim_movement=(
                round(delta_sim_movement_value, 4)
                if delta_sim_movement_value is not None else None
            ),
            delta_total=(
                round(delta_total_value, 4)
                if delta_total_value is not None else None
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("predict_endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Re-export observe_category_consensus + BranchSpec so import-time consumers
# (e.g. ad-hoc smoke scripts) keep working without touching predictor internals.
__all__ = ("app", "PredictRequest", "PredictResponse", "observe_category_consensus", "BranchSpec")
