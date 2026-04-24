"""Spotlight content generator (decision #1).

After agent posts are authored with topic/sentiment/virality metadata but an
empty `body` field (Phase 3 MVP), the spotlight picks the top ~1-2% of posts
by (virality × (1 + engagement)) and asks the LLM to generate a plausible
body written in the agent's voice.

Usage:

    from realm.llm.spotlight import SpotlightAnnotator
    annotator = SpotlightAnnotator(ratio=0.02)
    annotator.annotate_tick(sim, tick=t, news_context=recent_news)

If no LLM is configured, annotate_tick is a no-op and returns [].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from realm.core.logging import get_logger
from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_prompt
from realm.llm.router import TASK_SPOTLIGHT, LLMRouter

if TYPE_CHECKING:
    from realm.agents.interfaces import Agent
    from realm.simulation.engine import SimulationEngine
    from realm.simulation.platforms.base import Post

logger = get_logger(__name__)


def _sentiment_descriptor(s: float) -> str:
    if s >= 0.6:
        return "strongly positive / enthusiastic"
    if s >= 0.2:
        return "optimistic"
    if s <= -0.6:
        return "harshly critical / alarmed"
    if s <= -0.2:
        return "skeptical / frustrated"
    return "measured and neutral"


def _top_traits(agent: Agent, n: int = 3) -> str:
    d = agent.traits.to_dict()
    ranked = sorted(d.items(), key=lambda kv: abs(kv[1] - 0.5), reverse=True)[:n]
    return ", ".join(f"{name}={val:.2f}" for name, val in ranked)


@dataclass
class SpotlightAnnotator:
    backend: ILLMBackend | None = None
    router: LLMRouter | None = None
    ratio: float = 0.02                      # fraction of posts to spotlight
    max_posts_per_tick: int = 5              # hard ceiling to control cost
    min_virality: float = 1.5                # skip low-virality posts entirely
    max_tokens: int = 160
    _annotated: set[str] = field(default_factory=set)

    def __post_init__(self):
        if self.backend is None:
            router = self.router or LLMRouter()
            try:
                self.backend = router.for_task(TASK_SPOTLIGHT)
            except LLMBackendError as e:
                logger.warning("SpotlightAnnotator: %s — disabled", e)
                self.backend = None

    def is_enabled(self) -> bool:
        return self.backend is not None

    def annotate_tick(
        self,
        sim: SimulationEngine,
        *,
        news_context: str = "",
    ) -> list[Post]:
        """Annotate this tick's top posts in place. Returns the updated posts."""
        if not self.is_enabled():
            return []

        social = sim.platforms[0]
        if not hasattr(social, "current_tick_posts"):
            return []

        posts: list[Post] = list(social.current_tick_posts())
        if not posts:
            return []

        posts.sort(
            key=lambda p: -(p.virality * (1.0 + p.engagement)),
        )
        n = min(
            self.max_posts_per_tick,
            max(1, int(len(posts) * self.ratio)) if self.ratio > 0 else 0,
        )
        candidates = [p for p in posts[:n] if p.virality >= self.min_virality]
        if not candidates:
            return []

        agents_by_id = {a.agent_id: a for a in sim.agents}
        prompt = load_prompt("spotlight/narrative")

        updated: list[Post] = []
        for post in candidates:
            if post.post_id in self._annotated:
                continue
            author = agents_by_id.get(post.author_id)
            if author is None:
                continue  # news-channel authored post or unknown

            user = prompt.render(
                name=f"{author.profile.name_first} {author.profile.name_last}",
                age=str(author.profile.age_years),
                country=author.profile.country,
                profession=author.profile.profession_code,
                top_traits=_top_traits(author),
                topic=post.topic,
                sentiment_descriptor=_sentiment_descriptor(post.sentiment),
                news_context=news_context or "(none)",
            )
            try:
                resp = self.backend.complete(
                    system="You are a concise voice-authoring assistant.",
                    user=user,
                    max_tokens=self.max_tokens, temperature=0.8,
                )
            except LLMBackendError as e:
                logger.warning("Spotlight LLM call failed for %s: %s", post.post_id, e)
                continue

            body = resp.content.strip()
            if not body:
                continue
            set_post_body(social, post.post_id, body)
            self._annotated.add(post.post_id)
            updated.append(post)

        if updated:
            logger.info("Spotlight annotated %d posts at tick %d",
                        len(updated), sim.clock.tick)
        return updated


# ---- platform sidecar -----------------------------------------------------
# Posts are frozen dataclasses whose `body` field is empty in Phase 3. Rather
# than mutate frozen instances we stash LLM-generated bodies in a sidecar dict
# on the platform. Dashboards + reports read via get_post_body().

_SIDECAR_ATTR = "_spotlight_bodies"


def get_post_body(platform, post_id: str) -> str | None:
    sidecar = getattr(platform, _SIDECAR_ATTR, None)
    return sidecar.get(post_id) if sidecar else None


def set_post_body(platform, post_id: str, body: str) -> None:
    sidecar = getattr(platform, _SIDECAR_ATTR, None)
    if sidecar is None:
        sidecar = {}
        setattr(platform, _SIDECAR_ATTR, sidecar)
    sidecar[post_id] = body
