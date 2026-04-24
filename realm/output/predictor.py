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


# ---- PredictionEngine -----------------------------------------------------

@dataclass
class PredictionEngine:
    master_seed: int
    branch_seed_offset: int = 1000

    def run(self, spec: BranchSpec, question: str = "") -> PredictionOutcome:
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
) -> SimulationEngine:
    """Construct a fresh SimulationEngine for one branch.

    When `initial_events` is non-empty, wires a NewsChannel + IngestionManager
    that publishes those events at tick 0. Agents see them in their feed and
    react via mood contagion + topic contagion in the decision policy.

    When `agent_builder` is provided, it replaces the default WorldGenerator +
    AgentFactory pipeline. Used by validity studies that need a custom
    population (e.g. BigFive-derived agents). The builder receives the branch
    seed and the requested agent count.
    """
    if agent_builder is not None:
        agents = agent_builder(seed, n_agents)
    else:
        agents = AgentFactory().build_batch(
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

    return SimulationEngine(
        agents=agents, network=net, modulator=modulator,
        platforms=platforms, clock=clock, climate=climate,
        pre_tick_hooks=pre_tick_hooks,
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
    question: str, *, master_seed: int | None = None,
) -> PredictionOutcome:
    """One-shot helper: parse a question, run the multi-branch engine, return outcome."""
    if master_seed is None:
        cfg = load_realm_config()
        master_seed = int(cfg["realm"]["simulation"]["master_seed"])
    parsed = QuestionParser().parse(question)
    engine = PredictionEngine(master_seed=master_seed)
    return engine.run(parsed.spec, question=question)
