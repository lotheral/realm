"""Platform interfaces — abstract interaction venue."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

# Phase 3 post topics. Phase 4+ will expand via content engine.
TOPIC = Literal["politics", "tech", "finance", "culture", "personal", "news"]


@dataclass(frozen=True, slots=True)
class Post:
    """A single unit of content on a platform.

    Phase 3: no body text — just metadata (topic, sentiment, virality score).
    LLM-generated bodies arrive in Phase 4.
    """

    post_id: str
    author_id: str
    tick: int
    topic: str                    # One of TOPIC
    sentiment: float              # [-1, 1]: negative to positive
    virality: float               # [0, inf): boost applied when seeded into feeds
    political_lean: float = 0.5   # [0, 1]: 0 left, 1 right
    engagement: int = 0           # accumulated likes/shares/replies


@dataclass
class Engagement:
    """A single engagement action on a post."""

    agent_id: str
    post_id: str
    tick: int
    kind: str                     # "like" | "share" | "reply"


class IPlatform(ABC):
    """Abstract venue where agents exchange posts."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def post(self, p: Post) -> None:
        """Publish a post to the platform."""

    @abstractmethod
    def engage(self, e: Engagement) -> None:
        """Record an engagement on an existing post."""

    @abstractmethod
    def feed_for(
        self, agent_id: str, neighbor_ids: list[str], *, limit: int = 20,
    ) -> list[Post]:
        """Return the posts visible to `agent_id` right now.

        Base rule: posts from network neighbors, plus high-virality posts from
        anyone (viral content leaks across the graph).
        """

    @abstractmethod
    def current_tick_posts(self) -> list[Post]:
        """All posts published in the current tick window."""

    @abstractmethod
    def advance(self, new_tick: int) -> None:
        """Called by SimulationEngine at the start of each new tick."""
