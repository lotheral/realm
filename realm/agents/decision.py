"""Rule-based agent decision policy.

Given an agent's current traits (natal + cultural + transit-modulated) and the
platform feed they'd see, decide what to do this tick:

    Action = "post" | "engage" | "lurk"

Phase 3 MVP — no LLM, no planning. Pure trait-driven probabilistic rules:

    p(post)    ∝ 0.15 * (extraversion + persuasion_skill)/2
                 + 0.05 * social_dominance - 0.03 * loss_aversion
    p(engage)  ∝ 0.20 * (fomo_susceptibility + information_sharing)/2
                 + 0.08 * agreeableness
    p(lurk)    = 1 - p(post) - p(engage)

Content choice given "post":
    topic based on profession + dominant trait
    sentiment based on (1 - neuroticism) + transit-derived mood proxy
    virality boost if agent is a hub (influencer) or has high persuasion_skill
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from realm.personality.trait_vector import TraitVector

from .interfaces import Agent

Action = Literal["post", "engage", "lurk"]


@dataclass(frozen=True, slots=True)
class Decision:
    action: Action
    topic: str | None = None
    sentiment: float = 0.0
    political_lean: float = 0.5
    virality: float = 1.0
    target_post_id: str | None = None
    engagement_kind: str | None = None


# Topic affinity per profession (rough). Traits nudge further at runtime.
_PROFESSION_TOPIC_BIAS: dict[str, dict[str, float]] = {
    "professionals":  {"tech": 0.30, "finance": 0.20, "news": 0.20,
                       "politics": 0.15, "culture": 0.10, "personal": 0.05},
    "technicians":    {"tech": 0.35, "news": 0.20, "personal": 0.15,
                       "finance": 0.10, "politics": 0.10, "culture": 0.10},
    "managers":       {"finance": 0.30, "news": 0.20, "politics": 0.20,
                       "tech": 0.15, "culture": 0.10, "personal": 0.05},
    "service_sales":  {"personal": 0.25, "culture": 0.20, "news": 0.20,
                       "politics": 0.15, "finance": 0.10, "tech": 0.10},
    "clerical":       {"news": 0.25, "personal": 0.20, "culture": 0.20,
                       "politics": 0.15, "finance": 0.10, "tech": 0.10},
    "student":        {"culture": 0.25, "tech": 0.20, "personal": 0.20,
                       "politics": 0.15, "news": 0.15, "finance": 0.05},
    "retired":        {"news": 0.30, "personal": 0.20, "politics": 0.20,
                       "culture": 0.15, "finance": 0.10, "tech": 0.05},
    "homemaker":      {"personal": 0.30, "culture": 0.25, "news": 0.20,
                       "politics": 0.10, "finance": 0.10, "tech": 0.05},
}


_DEFAULT_TOPIC_DIST = {
    "news": 0.20, "personal": 0.20, "culture": 0.20,
    "politics": 0.15, "tech": 0.15, "finance": 0.10,
}


def _topic_for(agent: Agent, rng: random.Random, feed: list | None = None) -> str:
    """Sample the topic this agent will post about.

    Order of influence:
      1. Profession-specific base distribution.
      2. Trait nudges (analytical_depth → tech/finance, spirituality → culture, …).
      3. News topic contagion — agents with high herd_susceptibility are more
         likely to write about topics they just saw dominate the news feed. This
         is the butterfly-effect coupling: a burst of injected news on topic X
         propagates into agent posts proportional to herd_susceptibility.
    """
    dist = _PROFESSION_TOPIC_BIAS.get(agent.profile.profession_code, _DEFAULT_TOPIC_DIST)
    t = agent.traits
    weights = dict(dist)
    weights["tech"] = weights.get("tech", 0) + (t.analytical_depth - 0.5) * 0.3
    weights["finance"] = weights.get("finance", 0) + (t.analytical_depth - 0.5) * 0.2
    weights["culture"] = weights.get("culture", 0) + (t.spirituality - 0.5) * 0.3
    weights["politics"] = weights.get("politics", 0) + (t.contrarian_tendency - 0.5) * 0.4

    # News topic contagion — count news posts in the feed and boost their topic
    # weights proportional to (herd_susceptibility − contrarian_tendency).
    if feed:
        news_topic_counts: dict[str, int] = {}
        for p in feed:
            if str(getattr(p, "author_id", "")).startswith("news:"):
                news_topic_counts[p.topic] = news_topic_counts.get(p.topic, 0) + 1
        if news_topic_counts:
            herd_factor = (t.herd_susceptibility - 0.3) - (t.contrarian_tendency - 0.5) * 0.5
            herd_factor = max(-0.3, min(0.7, herd_factor))
            total_news = sum(news_topic_counts.values())
            for topic, count in news_topic_counts.items():
                share = count / total_news
                # Max boost at herd_factor=0.7 and 100% news share: +0.70
                weights[topic] = weights.get(topic, 0.01) + 1.0 * herd_factor * share

    # Floor at 0 so clamped negative weights don't crash the sampler
    weights = {k: max(0.01, v) for k, v in weights.items()}
    total = sum(weights.values())
    r = rng.uniform(0, total)
    cum = 0.0
    for k, w in weights.items():
        cum += w
        if r <= cum:
            return k
    return "news"


def _post_probability(traits: TraitVector) -> float:
    """Base probability this agent posts this tick. Clamped to [0, 0.35]."""
    p = (
        0.15 * (traits.extraversion + traits.persuasion_skill) / 2
        + 0.05 * traits.social_dominance
        - 0.03 * traits.loss_aversion
    )
    return max(0.0, min(0.35, p))


def _engage_probability(traits: TraitVector, feed_size: int) -> float:
    """Base engagement probability. Zero if feed is empty; capped at 0.5."""
    if feed_size == 0:
        return 0.0
    p = (
        0.20 * (traits.fomo_susceptibility + traits.information_sharing) / 2
        + 0.08 * traits.agreeableness
    )
    return max(0.0, min(0.5, p))


def _sentiment_for(agent: Agent, rng: random.Random) -> float:
    """Post sentiment: base mood from traits + jitter.

    High neuroticism pulls sentiment negative; high financial_optimism pulls positive.
    """
    t = agent.traits
    base = (t.financial_optimism - t.neuroticism) * 0.5
    jitter = rng.uniform(-0.25, 0.25)
    return max(-1.0, min(1.0, base + jitter))


def _virality_for(agent: Agent, rng: random.Random) -> float:
    base = 1.0
    if agent.profile.marginal_category == "influencer":
        base += 0.8
    base += (agent.traits.persuasion_skill - 0.5) * 0.8
    return max(0.5, base + rng.uniform(-0.1, 0.1))


def _engagement_kind(traits: TraitVector, rng: random.Random) -> str:
    """Choose between 'like', 'share', 'reply' based on traits."""
    share_w = 0.3 + (traits.information_sharing - 0.5) * 0.5
    reply_w = 0.2 + (traits.communication_assertiveness - 0.5) * 0.5
    like_w = 1.0 - share_w - reply_w
    # Normalize
    total = like_w + share_w + reply_w
    r = rng.uniform(0, total)
    if r < like_w:
        return "like"
    if r < like_w + share_w:
        return "share"
    return "reply"


def decide(
    agent: Agent,
    feed: list,    # list[Post]
    rng: random.Random,
) -> Decision:
    """Sample an action for this agent given current feed visibility."""
    traits = agent.traits
    p_post = _post_probability(traits)
    p_engage = _engage_probability(traits, len(feed))

    r = rng.random()
    if r < p_post:
        return Decision(
            action="post",
            topic=_topic_for(agent, rng, feed=feed),
            sentiment=_sentiment_for(agent, rng),
            political_lean=float(traits.political_spectrum),
            virality=_virality_for(agent, rng),
        )
    if r < p_post + p_engage and feed:
        # Pick a post weighted by engagement + virality
        weights = [p.engagement + p.virality for p in feed]
        total = sum(weights)
        if total <= 0:
            chosen = feed[0]
        else:
            rr = rng.uniform(0, total)
            cum = 0.0
            chosen = feed[-1]
            for p, w in zip(feed, weights, strict=True):
                cum += w
                if rr <= cum:
                    chosen = p
                    break
        return Decision(
            action="engage",
            target_post_id=chosen.post_id,
            engagement_kind=_engagement_kind(traits, rng),
        )
    return Decision(action="lurk")
