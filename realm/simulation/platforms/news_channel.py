"""News channel — broadcast-style platform.

Unlike social_media (peer-to-peer), the NewsChannel is where SeedEvents enter
the simulation. Every agent sees news posts (gated by geography if specified on
the event). Agents can engage (like/share) but cannot author. Posts here carry
elevated virality so they propagate to social_media via the mood-contagion
mechanism in agent.decision.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from realm.core.logging import get_logger
from realm.ingestion.interfaces import SeedEvent

from .base import Engagement, IPlatform, Post

logger = get_logger(__name__)


@dataclass
class NewsChannelPlatform(IPlatform):
    platform_name: str = "news_channel"
    memory_ticks: int = 5
    default_virality: float = 2.0

    _posts_by_tick: dict[int, list[Post]] = field(default_factory=dict)
    _posts_by_id: dict[str, Post] = field(default_factory=dict)
    _post_geo: dict[str, str | None] = field(default_factory=dict)  # post_id → ISO2 or None
    _engagements: list[Engagement] = field(default_factory=list)
    _current_tick: int = 0
    _tick_window: deque[int] = field(default_factory=lambda: deque(maxlen=5))
    _event_counter: int = 0

    def __post_init__(self) -> None:
        self._tick_window = deque(maxlen=self.memory_ticks)

    # ---- IPlatform ----------------------------------------------------

    @property
    def name(self) -> str:
        return self.platform_name

    def post(self, p: Post) -> None:
        self._posts_by_tick.setdefault(p.tick, []).append(p)
        self._posts_by_id[p.post_id] = p

    def engage(self, e: Engagement) -> None:
        target = self._posts_by_id.get(e.post_id)
        if target is None:
            return
        from dataclasses import replace
        updated = replace(target, engagement=target.engagement + 1)
        self._posts_by_id[e.post_id] = updated
        lst = self._posts_by_tick.get(target.tick, [])
        for i, q in enumerate(lst):
            if q.post_id == e.post_id:
                lst[i] = updated
                break
        self._engagements.append(e)

    def feed_for(
        self, agent_id: str, neighbor_ids: list[str], *, limit: int = 10,
    ) -> list[Post]:
        """News posts visible to this agent. Geography gating optional."""
        # Current memory window posts, newest first
        visible: list[Post] = []
        for t in self._tick_window:
            for p in self._posts_by_tick.get(t, []):
                # If the post has a geography tag, we skip it here; callers
                # with access to agent country can filter via `visible_for()`.
                visible.append(p)
        visible.sort(key=lambda p: (-p.tick, -p.engagement))
        return visible[:limit]

    def current_tick_posts(self) -> list[Post]:
        return list(self._posts_by_tick.get(self._current_tick, []))

    def advance(self, new_tick: int) -> None:
        self._current_tick = new_tick
        self._tick_window.append(new_tick)
        cutoff = new_tick - self.memory_ticks
        for t in list(self._posts_by_tick):
            if t < cutoff:
                for p in self._posts_by_tick.pop(t):
                    self._posts_by_id.pop(p.post_id, None)
                    self._post_geo.pop(p.post_id, None)

    # ---- Bridge from SeedEvent ---------------------------------------

    def publish_events(
        self, events: list[SeedEvent], tick: int,
    ) -> list[Post]:
        """Turn SeedEvents into Posts at the current tick. Returns the new posts."""
        new_posts: list[Post] = []
        for e in events:
            post = Post(
                post_id=f"NC_{tick}_{self._event_counter}",
                author_id=f"news:{e.source}",
                tick=tick,
                topic=e.topic,
                sentiment=e.sentiment,
                virality=max(e.virality, self.default_virality),
                political_lean=0.5,
                engagement=0,
            )
            self._event_counter += 1
            self.post(post)
            self._post_geo[post.post_id] = e.geography
            new_posts.append(post)
        if new_posts:
            logger.info("NewsChannel published %d events at tick %d", len(new_posts), tick)
        return new_posts

    def visible_for(self, agent_country: str, *, limit: int = 10) -> list[Post]:
        """Country-gated feed: only include posts whose geography is None or matches."""
        out: list[Post] = []
        for t in self._tick_window:
            for p in self._posts_by_tick.get(t, []):
                geo = self._post_geo.get(p.post_id)
                if geo is None or geo == agent_country:
                    out.append(p)
        out.sort(key=lambda p: (-p.tick, -p.engagement))
        return out[:limit]

    def total_posts(self) -> int:
        return len(self._posts_by_id)

    def top_posts(self, n: int = 10) -> list[Post]:
        return sorted(self._posts_by_id.values(),
                      key=lambda p: -p.engagement)[:n]
