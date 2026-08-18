"""Multi-branch prediction (decision #13) + Q&A parser.

Algorithm:
    1. Take the current simulation as "base".
    2. For each branch (default n=5), rebuild the sim with a perturbed seed:
            branch_seed = master_seed + branch_seed_offset * branch_idx
       Run it forward `horizon_ticks` from tick 0.
    3. Observe a configurable metric on each branch (topic sentiment, trait
       mean, engagement rate, ...).
    4. Aggregate: probability = share of branches where metric crosses
       threshold; confidence = 1 - normalized variance of branches.

Q&A module turns natural-language questions into BranchSpec configurations.
Phase 6 MVP is rule-based (keywords + simple regex) - a future phase will
swap in LLM-based parsing.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.core.config import load_realm_config
from realm.core.logging import get_logger
from realm.demographics.world_generator import WorldGenerator
from realm.output.category_router import CategoryMatch
from realm.simulation.climate import ClimateEngine
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator

logger = get_logger(__name__)


# ---- Branch specification ------------------------------------------------

@dataclass(frozen=True)
class BranchSpec:
    """Metric to evaluate at the end of each branch.

    observe(sim) -> float. Larger is "more toward yes".
    threshold is the boundary that turns observations into yes/no votes.

    `initial_events`: optional tuple of SeedEvent instances that get
    pre-loaded into the branch's NewsChannel at tick 0. Lets a caller run
    a what-if scenario (decision #13) by comparing baseline vs. scenario
    distributions on the same metric.

    `agent_builder`: optional callable `(seed: int, n_agents: int) -> list[Agent]`
    that overrides the default WorldGenerator + AgentFactory pipeline. Used by
    validity studies that need a custom population (e.g. BigFive synthetic
    OCEAN scores). Must return a list of n_agents Agent instances.
    """
    name: str
    observe: Callable[[SimulationEngine], float]
    threshold: float
    horizon_ticks: int = 30
    n_branches: int = 5
    n_agents: int = 300
    initial_events: tuple = ()
    agent_builder: Callable[[int, int], list] | None = None


# ---- Outcome --------------------------------------------------------------

@dataclass(frozen=True)
class PredictionOutcome:
    question: str
    metric: str
    branch_values: tuple[float, ...]
    threshold: float
    probability: float              # fraction of branches over threshold
    mean_value: float
    stddev_value: float
    confidence: float               # 1 - normalized stddev, clamped [0, 1]
    narrative: str = ""
    category: CategoryMatch | None = None


# ---- PredictionEngine -----------------------------------------------------

@dataclass
class PredictionEngine:
    master_seed: int
    branch_seed_offset: int = 1000

    def run(
        self,
        spec: BranchSpec,
        question: str = "",
        *,
        category: CategoryMatch | None = None,
    ) -> PredictionOutcome:
        values: list[float] = []
        for i in range(spec.n_branches):
            branch_seed = self.master_seed + self.branch_seed_offset * (i + 1)
            sim = build_branch_sim(
                branch_seed,
                spec.n_agents,
                initial_events=spec.initial_events,
                agent_builder=spec.agent_builder,
            )
            sim.run(spec.horizon_ticks)
            values.append(float(spec.observe(sim)))

        n_yes = sum(1 for v in values if v >= spec.threshold)
        prob = n_yes / len(values) if values else 0.0
        mean = statistics.mean(values) if values else 0.0
        stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
        # Confidence: low variance -> high confidence
        confidence = max(0.0, min(1.0, 1.0 - stdev * 4.0))

        return PredictionOutcome(
            question=question,
            metric=spec.name,
            branch_values=tuple(values),
            threshold=spec.threshold,
            probability=prob,
            mean_value=mean,
            stddev_value=stdev,
            confidence=confidence,
            narrative=_build_narrative(spec, prob, mean, stdev, confidence),
            category=category,
        )


def _build_narrative(
    spec: BranchSpec, prob: float, mean: float, stdev: float, conf: float,
) -> str:
    yes_no = "yes" if prob >= 0.5 else "no"
    return (
        f"{spec.n_branches} branches, horizon {spec.horizon_ticks} ticks. "
        f"Metric '{spec.name}' mean={mean:.3f} +/-{stdev:.3f}, "
        f"threshold={spec.threshold:.2f}. "
        f"Answer: {yes_no} (P={prob:.2f}, confidence={conf:.2f})."
    )


def build_branch_sim(
    seed: int,
    n_agents: int,
    *,
    initial_events: tuple = (),
    agent_builder: Callable[[int, int], list] | None = None,
    drift_event_weights: dict[str, float] | None = None,
    seed_offsets: dict[str, float] | None = None,
    drift_volatility: float = 1.0,
    drift_asymmetry_positive: float = 1.0,
    drift_asymmetry_negative: float = 1.0,
    primary_traits: tuple[str, ...] = (),
) -> SimulationEngine:
    """Construct a fresh SimulationEngine for one branch.

    When `initial_events` is non-empty, wires a NewsChannel + IngestionManager
    that publishes those events at tick 0. Agents see them in their feed and
    react via mood contagion + topic contagion in the decision policy.

    When `agent_builder` is provided, it replaces the default WorldGenerator +
    AgentFactory pipeline. Used by validity studies that need a custom
    population (e.g. BigFive-derived agents). The builder receives the branch
    seed and the requested agent count.

    Sprint 14 WP1: ``drift_event_weights`` (dict event_type → relative weight)
    causes the DriftEventBridge to weight-sample among matching rules; None
    preserves first-match-wins. Sprint 14 WP2: ``seed_offsets`` (dict trait →
    additive offset) is forwarded to the default AgentFactory so the starting
    population reflects the question's domain. ``seed_offsets`` is ignored
    when a custom ``agent_builder`` is supplied — that builder is responsible
    for any offsets it wants to apply.
    """
    if agent_builder is not None:
        agents = agent_builder(seed, n_agents)
    else:
        agents = AgentFactory(seed_offsets=seed_offsets).build_batch(
            WorldGenerator(master_seed=seed).generate(n_agents),
        )
    clock = Clock.from_config()
    clock.master_seed = seed
    net = NetworkTopology(
        agents, NetworkConfig(local_k=10, rewire_p=0.1, hub_ratio=0.05),
    )
    net.build(clock.rng("network"))
    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    climate = ClimateEngine(modulator, dampening=0.7)
    social = SocialMediaPlatform(memory_ticks=5, virality_threshold=1.5)

    platforms: list = [social]
    pre_tick_hooks: list = []
    if initial_events:
        from realm.ingestion.entity_extractor import EnrichingProcessor
        from realm.ingestion.knowledge_graph import KnowledgeGraph
        from realm.ingestion.manager import IngestionManager
        from realm.ingestion.sources.manual_upload import ManualUploadSource
        from realm.simulation.platforms.news_channel import NewsChannelPlatform

        news = NewsChannelPlatform(memory_ticks=5)
        src = ManualUploadSource(source_id=f"scenario:{seed}")
        src.enqueue_many(list(initial_events))
        mgr = IngestionManager(
            sources=[src], processors=[EnrichingProcessor()],
            knowledge_graph=KnowledgeGraph(), news_channel=news,
        )
        platforms.append(news)
        pre_tick_hooks.append(lambda t, _mgr=mgr: _mgr.pull(t))

    # Sprint 13 Bug-2 fix: wire ExperienceDriftEngine + DriftEventBridge by
    # default so per-tick decisions actually move agent traits. Sprint 11
    # observed the predictor pipeline running with engine=None, which meant
    # zero true drift and the API's "trait_shifts" field was meaningless
    # baseline distribution skew (mean - 0.5) instead of actual movement.
    # The drift engine's cumulative cap (max_drift_ratio * original_value,
    # default 0.10) bounds every trait per agent.
    from realm.simulation.drift import DriftEventBridge

    # Sprint 15: per-category baseline differentiation. drift_volatility
    # scales BOTH the cumulative cap (max_drift_ratio × volatility) AND the
    # per-event speed (intensity_scale = volatility). Compound effect lets
    # high-volatility domains accumulate enough drift in 30 ticks for the
    # asymmetry skew to actually move the population mean. Asymmetry
    # multipliers control sign-based per-trait scaling. Defaults 1.0 each
    # preserve Sprint 14 behavior bit-for-bit.
    # Sprint 16: load the bridge first so we can pass its full event_map
    # (15 events from config/drift_events.json) into the engine. The engine's
    # built-in `_EVENT_TRAIT_MAP` default only contains the 6 Sprint 9 events;
    # without explicit wiring, all Sprint 10 events (leadership_act,
    # group_conformity, group_dissent, financial_loss, financial_gain,
    # cultural_experience) and Sprint 16 events (regime_consolidation,
    # diplomatic_stalemate, sanctions_pressure) were silently no-op'd by
    # `engine.event_map.get(event_type)` returning None. Pre-Sprint 16
    # calibrations were running on only the 6 Sprint 9 events — a latent
    # bug since Sprint 10 that hid the value of category-conditioned weights
    # for the Sprint 10/16 event pool.
    drift_bridge = DriftEventBridge.default()
    if drift_event_weights:
        drift_bridge = drift_bridge.with_weights(drift_event_weights)
    # Sprint 20: construct through the bridge so the engine can never be
    # built without the bridge's full event catalog (the Sprint 10 bug).
    drift_engine = drift_bridge.build_engine(
        drift_volatility=float(drift_volatility),
        positive_multiplier=float(drift_asymmetry_positive),
        negative_multiplier=float(drift_asymmetry_negative),
        primary_traits=frozenset(primary_traits),
    )

    return SimulationEngine(
        agents=agents, network=net, modulator=modulator,
        platforms=platforms, clock=clock, climate=climate,
        pre_tick_hooks=pre_tick_hooks,
        drift_engine=drift_engine,
        drift_bridge=drift_bridge,
    )


# Backward-compatible private alias for any internal call sites.
_build_branch_sim = build_branch_sim


# ---- Built-in metric observers -------------------------------------------

def observe_topic_share(topic: str, window: int | None = None) -> Callable[[SimulationEngine], float]:
    """Fraction of posts on `topic` across the simulation run.

    `window=None` (default): measure across ALL ticks - the right window for
    what-if questions like "did topic X ever dominate?" because injected news
    may have expired from the feed before the final ticks.
    `window=N`: measure only the last N ticks.
    """
    def observer(sim: SimulationEngine) -> float:
        if not sim.history:
            return 0.0
        slice_ = sim.history if window is None else sim.history[-window:]
        total = sum(s.posts for s in slice_)
        hits = sum(s.posts_by_topic.get(topic, 0) for s in slice_)
        return hits / total if total else 0.0
    return observer


def observe_mean_trait(trait_name: str) -> Callable[[SimulationEngine], float]:
    """Aggregate mean of `trait_name` across all agents at end of branch."""
    def observer(sim: SimulationEngine) -> float:
        values = [getattr(a.traits, trait_name, 0.5) for a in sim.agents]
        return statistics.mean(values) if values else 0.5
    return observer


def observe_engagement_rate() -> Callable[[SimulationEngine], float]:
    """engagements / posts across the whole run."""
    def observer(sim: SimulationEngine) -> float:
        agg = sim.aggregate_stats()
        posts = agg.get("posts", 0)
        engs = agg.get("engagements", 0)
        return engs / posts if posts else 0.0
    return observer


# Category-aware trait weights. The weighting must sit ACROSS multiple trait
# dimensions because scaling every agent's contribution to a single trait by a
# constant is mathematically inert (sum / N is unchanged). Multipliers below
# combine multiple trait axes per the active prediction category.
_CATEGORY_TRAIT_WEIGHT = {
    "primary": 2.0,
    "secondary": 1.0,
    "suppressed": 0.25,
}


def observe_category_consensus(category: CategoryMatch) -> Callable[[SimulationEngine], float]:
    """Per-branch metric = weighted population mean across the category's traits.

    For each agent, compute a personal score
        s_i = sum(w_t * agent.traits[t]   for t in primary U secondary U suppressed)
              / sum(w_t                   for t in primary U secondary U suppressed)
    where w_t = 2.0 (primary) / 1.0 (secondary) / 0.25 (suppressed) and traits not
    listed are skipped entirely. The branch metric is the population mean of s_i.

    Different categories produce DIFFERENT consensus numbers from the same
    population because the trait set + weights differ — that is the entire point.
    Falls back to overall mean of all 24 traits when the category has no
    weighted traits at all (e.g. a malformed category record).
    """
    weighted: dict[str, float] = {}
    for trait in category.primary_traits:
        weighted[trait] = _CATEGORY_TRAIT_WEIGHT["primary"]
    for trait in category.secondary_traits:
        weighted.setdefault(trait, _CATEGORY_TRAIT_WEIGHT["secondary"])
    for trait in category.suppressed_traits:
        weighted.setdefault(trait, _CATEGORY_TRAIT_WEIGHT["suppressed"])
    weight_sum = sum(weighted.values())

    def observer(sim: SimulationEngine) -> float:
        if not sim.agents or weight_sum <= 0.0:
            return 0.5
        scores: list[float] = []
        for agent in sim.agents:
            traits = agent.traits
            agent_score = 0.0
            for trait, w in weighted.items():
                agent_score += w * float(getattr(traits, trait, 0.5))
            scores.append(agent_score / weight_sum)
        return statistics.mean(scores)
    return observer


# ---- Question parser -----------------------------------------------------

_TOPICS = {"politics", "tech", "finance", "culture", "personal", "news"}

_TRAITS_LOWER = {
    "risk", "risk appetite", "risk_appetite",
    "optimism", "financial optimism", "financial_optimism",
    "neuroticism", "spirituality", "empathy", "patience",
    "impulsivity", "authority", "authority_compliance",
}


@dataclass
class ParsedQuestion:
    spec: BranchSpec
    original: str
    category: CategoryMatch | None = None


class QuestionParser:
    """Tiny rule-based parser for Q&A inputs.

    Supports patterns like:
        "Will sentiment on finance be positive in 30 ticks?"
        "Will tech dominate the topic mix?"
        "Will engagement rate stay above 1.5?"
        "Will mean empathy rise above 0.60?"
    Anything it can't parse falls back to a default 'sentiment rises' question.
    """

    def parse(self, text: str) -> ParsedQuestion:
        q = text.lower().strip()

        horizon = self._extract_horizon(q)
        agents = self._extract_agent_count(q, default=300)

        # Topic-share intent
        for topic in _TOPICS:
            if f"{topic}" in q and ("dominate" in q or "topic" in q or "share" in q):
                return ParsedQuestion(
                    spec=BranchSpec(
                        name=f"{topic}_share",
                        observe=observe_topic_share(topic),
                        threshold=0.30,
                        horizon_ticks=horizon, n_agents=agents,
                    ),
                    original=text,
                )

        # Trait mean intent
        for trait in _TRAITS_LOWER:
            if trait in q:
                canonical = trait.replace(" ", "_")
                # Map alias to canonical trait
                aliases = {
                    "risk": "risk_appetite",
                    "optimism": "financial_optimism",
                    "authority": "authority_compliance",
                }
                canonical = aliases.get(canonical, canonical)
                threshold = self._extract_threshold(q, default=0.55)
                return ParsedQuestion(
                    spec=BranchSpec(
                        name=f"mean_{canonical}",
                        observe=observe_mean_trait(canonical),
                        threshold=threshold,
                        horizon_ticks=horizon, n_agents=agents,
                    ),
                    original=text,
                )

        # Engagement-rate intent
        if "engagement" in q:
            threshold = self._extract_threshold(q, default=1.5)
            return ParsedQuestion(
                spec=BranchSpec(
                    name="engagement_rate",
                    observe=observe_engagement_rate(),
                    threshold=threshold,
                    horizon_ticks=horizon, n_agents=agents,
                ),
                original=text,
            )

        # Default fallback: positive news sentiment
        return ParsedQuestion(
            spec=BranchSpec(
                name="mean_financial_optimism",
                observe=observe_mean_trait("financial_optimism"),
                threshold=0.55,
                horizon_ticks=horizon, n_agents=agents,
            ),
            original=text,
        )

    @staticmethod
    def _extract_horizon(q: str) -> int:
        m = re.search(r"(\d+)\s*(ticks?|days?)", q)
        if m:
            return max(1, min(365, int(m.group(1))))
        return 15

    @staticmethod
    def _extract_agent_count(q: str, default: int) -> int:
        m = re.search(r"(\d+)\s*(agents?|people|population)", q)
        if m:
            return max(30, min(2000, int(m.group(1))))
        return default

    @staticmethod
    def _extract_threshold(q: str, default: float) -> float:
        m = re.search(r"(?:above|over|past|beyond|greater than)\s*(\d+(?:\.\d+)?)", q)
        if m:
            return float(m.group(1))
        return default


def predict(
    question: str,
    *,
    master_seed: int | None = None,
    route_category: bool = False,
) -> PredictionOutcome:
    """One-shot helper: parse a question, run the multi-branch engine, return outcome.

    When ``route_category`` is True, the question is also routed through
    :class:`realm.output.category_router.CategoryRouter`. The matched category
    is attached to the returned ``PredictionOutcome``. When the routed
    category is non-balanced (i.e. has a non-empty primary trait list), the
    branch metric is computed via :func:`observe_category_consensus` so the
    weighted multi-trait population mean is the yes/no signal — overriding the
    QuestionParser's default observer.
    """
    if master_seed is None:
        cfg = load_realm_config()
        master_seed = int(cfg["realm"]["simulation"]["master_seed"])
    parsed = QuestionParser().parse(question)
    category: CategoryMatch | None = None
    spec = parsed.spec
    if route_category:
        from realm.output.category_router import default_router

        category = default_router().route(question)
        if category.primary_traits:
            spec = BranchSpec(
                name=f"category_{category.category_id}",
                observe=observe_category_consensus(category),
                threshold=0.55,
                horizon_ticks=spec.horizon_ticks,
                n_branches=spec.n_branches,
                n_agents=spec.n_agents,
                initial_events=spec.initial_events,
                agent_builder=spec.agent_builder,
            )
    engine = PredictionEngine(master_seed=master_seed)
    return engine.run(spec, question=question, category=category)
