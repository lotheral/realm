"""SimulationEngine — main tick loop.

Per-tick pipeline:

    1. Advance all platforms to the new tick.
    2. Compute transit positions once (TransitModulator caches).
    3. For each agent:
         a. Apply transit modifiers to get effective traits for this tick.
         b. Build their platform feed (network-gated visibility + viral leaks).
         c. Sample a Decision (post / engage / lurk) via rule-based policy.
         d. Execute the decision against the platform.
    4. Record TickStats.
    5. Advance clock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from realm.agents.decision import decide
from realm.agents.interfaces import Agent
from realm.core.logging import get_logger
from realm.personality.trait_vector import TraitVector
from realm.simulation.clock import Clock
from realm.simulation.drift import DriftEventBridge, ExperienceDriftEngine, event_from_decision
from realm.simulation.network import NetworkTopology
from realm.simulation.platforms.base import Engagement, IPlatform, Post
from realm.simulation.transit_modulator import TransitModulator

if TYPE_CHECKING:
    from realm.simulation.climate import ClimateEngine

logger = get_logger(__name__)


@dataclass
class TickStats:
    tick: int
    posts: int = 0
    engagements: int = 0
    lurkers: int = 0
    actions_by_type: dict[str, int] = field(default_factory=dict)
    posts_by_topic: dict[str, int] = field(default_factory=dict)


@dataclass
class SimulationEngine:
    agents: list[Agent]
    network: NetworkTopology
    modulator: TransitModulator
    platforms: list[IPlatform]
    clock: Clock
    climate: ClimateEngine | None = None
    pre_tick_hooks: list[Callable[[int], None]] = field(default_factory=list)
    # Sprint 9 WP3: optional drift engine. When set, tick() records a drift
    # event per agent based on its Decision.action + Decision.sentiment.
    drift_engine: ExperienceDriftEngine | None = None
    # Sprint 10 WP3: optional config-driven event bridge. When set, overrides
    # the hard-coded event_from_decision heuristic. The drift_engine's
    # event_map is swapped to the bridge's catalogue so the new event types
    # (leadership_act, group_conformity, …) have trait weights.
    drift_bridge: DriftEventBridge | None = None
    history: list[TickStats] = field(default_factory=list)
    _post_counter: int = 0
    _agents_by_id: dict[str, Agent] = field(default_factory=dict, init=False)
    _post_to_platform: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._agents_by_id = {a.agent_id: a for a in self.agents}
        if not self.platforms:
            raise ValueError("SimulationEngine requires at least one platform")

    def tick(self) -> TickStats:
        """Run one simulation tick. Returns stats, appends to history."""
        t = self.clock.tick
        sim_time = self.clock.sim_time
        rng = self.clock.rng("simulation")

        # Pre-tick hooks (e.g., IngestionManager.pull) — let them push events
        # into platforms BEFORE the window advance so they land in this tick.
        for hook in self.pre_tick_hooks:
            try:
                hook(t)
            except Exception as e:
                logger.warning("pre_tick_hook %r failed: %s", hook, e)

        for plat in self.platforms:
            plat.advance(t)

        stats = TickStats(tick=t)
        social = self.platforms[0]

        # Compute collective climate ONCE per tick (shared by every agent)
        collective_mod: dict[str, float] = (
            self.climate.compute(sim_time) if self.climate is not None else {}
        )

        # Iterate agents in stable order for determinism
        for agent in self.agents:
            # Layer composition (decision #5 / Phase 5 final formula):
            #   natal+cultural (static, in agent.traits)
            #   → collective climate (global, per-tick)
            #   → individual transits (per-agent, per-tick)
            traits_after_climate = (
                agent.traits.apply_modifier(collective_mod) if collective_mod else agent.traits
            )
            # Transit modulation is astrology-bound; skip when the agent was
            # built by a non-astrological InputAdapter (natal_chart is None).
            if agent.natal_chart is None:
                modified_traits = traits_after_climate
            else:
                modified_traits = self.modulator.apply_to(
                    traits_after_climate, agent.natal_chart, sim_time,
                )

            # Build feed: social (neighbors) + news (country-gated)
            neighbors = self.network.neighbors_of(agent.agent_id)
            social_feed = social.feed_for(agent.agent_id, neighbors, limit=15)
            news_feed = self._news_feed_for(agent.profile.country, limit=5)
            feed = list(news_feed) + list(social_feed)

            # Mood contagion: news sentiment nudges the agent's posting mood
            modified_traits = self._apply_news_mood(modified_traits, news_feed)
            agent_for_tick = replace(agent, traits=modified_traits)

            decision = decide(agent_for_tick, feed, rng)
            stats.actions_by_type[decision.action] = (
                stats.actions_by_type.get(decision.action, 0) + 1
            )

            # Sprint 9 WP3: record drift event from the decision against the
            # agent's ORIGINAL traits (not transit-modulated), so drift
            # represents lasting experience, not transient tick state.
            # Sprint 10 WP3: if a DriftEventBridge is installed, use its
            # rule-based resolver; otherwise fall back to the hard-coded
            # event_from_decision heuristic with intensity 0.5.
            if self.drift_engine is not None:
                if self.drift_bridge is not None:
                    resolved = self.drift_bridge.event_for(decision, agent.traits, rng=rng)
                    if resolved is not None:
                        event_type, intensity = resolved
                        self.drift_engine.record_event(
                            agent.agent_id,
                            event_type,
                            intensity=intensity,
                            original_traits=agent.traits,
                        )
                else:
                    event_type = event_from_decision(
                        decision.action,
                        getattr(decision, "sentiment", None),
                    )
                    if event_type is not None:
                        self.drift_engine.record_event(
                            agent.agent_id,
                            event_type,
                            intensity=0.5,
                            original_traits=agent.traits,
                        )

            if decision.action == "post":
                post_id = f"P_{t}_{self._post_counter}"
                self._post_counter += 1
                social.post(Post(
                    post_id=post_id,
                    author_id=agent.agent_id,
                    tick=t,
                    topic=decision.topic or "news",
                    sentiment=decision.sentiment,
                    virality=decision.virality,
                    political_lean=decision.political_lean,
                ))
                self._post_to_platform[post_id] = 0
                stats.posts += 1
                stats.posts_by_topic[decision.topic or "news"] = (
                    stats.posts_by_topic.get(decision.topic or "news", 0) + 1
                )
            elif decision.action == "engage" and decision.target_post_id:
                self._route_engagement(Engagement(
                    agent_id=agent.agent_id,
                    post_id=decision.target_post_id,
                    tick=t,
                    kind=decision.engagement_kind or "like",
                ))
                stats.engagements += 1
            else:
                stats.lurkers += 1

        self.history.append(stats)
        self.clock.advance()
        return stats

    # ---- helpers --------------------------------------------------------

    def _news_feed_for(self, country: str, *, limit: int = 5) -> list[Post]:
        """Collect news-channel posts visible to an agent in `country`."""
        from realm.simulation.platforms.news_channel import NewsChannelPlatform
        out: list[Post] = []
        for plat in self.platforms[1:]:
            if isinstance(plat, NewsChannelPlatform):
                out.extend(plat.visible_for(country, limit=limit))
        return out[:limit]

    def _apply_news_mood(
        self, traits: TraitVector, news_feed: list[Post],
    ) -> TraitVector:
        """Small mood contagion: news sentiment in the feed nudges agent sentiment
        indirectly via fomo_susceptibility and herd_susceptibility."""
        if not news_feed:
            return traits
        avg_sentiment = sum(p.sentiment for p in news_feed) / len(news_feed)
        # Negative news amplifies neuroticism, dampens financial_optimism;
        # positive news does the reverse. Scale by herd_susceptibility.
        herd = traits.herd_susceptibility
        delta = avg_sentiment * 0.05 * herd
        return traits.apply_modifier({
            "financial_optimism": delta,
            "neuroticism": -delta,
        })

    def _route_engagement(self, eng: Engagement) -> None:
        """Deliver an engagement to the owning platform.

        Social posts are tracked in `_post_to_platform` at post() time. News
        posts originate from IngestionManager so we don't have their id;
        engage() is a no-op on unknown post_ids so fanning out is safe.
        """
        idx = self._post_to_platform.get(eng.post_id)
        if idx is not None and 0 <= idx < len(self.platforms):
            self.platforms[idx].engage(eng)
            return
        for plat in self.platforms:
            plat.engage(eng)

    def run(self, n_ticks: int) -> list[TickStats]:
        """Run n_ticks of simulation."""
        for _ in range(n_ticks):
            self.tick()
        logger.info(
            "Simulation ran %d ticks: %d posts, %d engagements total",
            n_ticks,
            sum(s.posts for s in self.history),
            sum(s.engagements for s in self.history),
        )
        return self.history

    # ---- Introspection ----------------------------------------------------

    def aggregate_stats(self) -> dict[str, float | int]:
        if not self.history:
            return {"ticks": 0, "posts": 0, "engagements": 0}
        total_posts = sum(s.posts for s in self.history)
        total_engagements = sum(s.engagements for s in self.history)
        total_lurkers = sum(s.lurkers for s in self.history)
        return {
            "ticks": len(self.history),
            "posts": total_posts,
            "engagements": total_engagements,
            "lurkers": total_lurkers,
            "posts_per_tick": total_posts / len(self.history),
            "engagements_per_tick": total_engagements / len(self.history),
        }
