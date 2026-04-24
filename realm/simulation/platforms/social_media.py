"""Twitter/Reddit-style social media platform.

Phase 3 MVP: in-memory feed with per-tick windowing. Posts from the last
`memory_ticks` ticks are visible in feeds; older posts are archived.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from .base import Engagement, IPlatform, Post


@dataclass
class SocialMediaPlatform(IPlatform):
    platform_name: str = "feed"
    memory_ticks: int = 5
    virality_threshold: float = 1.5   # posts above this leak across the network
    viral_feed_cap: int = 10          # max viral posts per agent's feed

    _posts_by_tick: dict[int, list[Post]] = field(default_factory=lambda: defaultdict(list))
    _posts_by_author: dict[str, list[Post]] = field(default_factory=lambda: defaultdict(list))
    _posts_by_id: dict[str, Post] = field(default_factory=dict)
    _engagements: list[Engagement] = field(default_factory=list)
    _current_tick: int = 0
    _tick_window: deque[int] = field(default_factory=lambda: deque(maxlen=5))

    def __post_init__(self) -> None:
        self._tick_window = deque(maxlen=self.memory_ticks)

    # ---- IPlatform ---------------------------------------------------------

    @property
    def name(self) -> str:
        return self.platform_name

    def post(self, p: Post) -> None:
        self._posts_by_tick[p.tick].append(p)
        self._posts_by_author[p.author_id].append(p)
        self._posts_by_id[p.post_id] = p

    def engage(self, e: Engagement) -> None:
        target = self._posts_by_id.get(e.post_id)
        if target is None:
            return
        # Replace post with updated engagement count (frozen dataclass copy)
        from dataclasses import replace
        updated = replace(target, engagement=target.engagement + 1)
        self._posts_by_id[e.post_id] = updated
        # Update cache lists
        for lst in (self._posts_by_tick.get(target.tick, []),
                    self._posts_by_author.get(target.author_id, [])):
            for i, q in enumerate(lst):
                if q.post_id == e.post_id:
                    lst[i] = updated
        self._engagements.append(e)

    def feed_for(
        self, agent_id: str, neighbor_ids: list[str], *, limit: int = 20,
    ) -> list[Post]:
        neighbor_set = set(neighbor_ids)
        neighbor_set.discard(agent_id)

        # Posts from the current memory window
        visible: list[Post] = []
        for t in self._tick_window:
            for p in self._posts_by_tick.get(t, []):
                if p.author_id == agent_id:
                    continue
                if p.author_id in neighbor_set:
                    visible.append(p)

        # Add viral posts from anywhere (up to viral_feed_cap)
        viral: list[Post] = []
        for t in self._tick_window:
            for p in self._posts_by_tick.get(t, []):
                if p.author_id == agent_id or p.author_id in neighbor_set:
                    continue
                if p.virality >= self.virality_threshold:
                    viral.append(p)
        viral.sort(key=lambda p: -p.virality)
        visible.extend(viral[: self.viral_feed_cap])

        # Sort by (engagement desc, then tick desc)
        visible.sort(key=lambda p: (-p.engagement, -p.tick))
        return visible[:limit]

    def current_tick_posts(self) -> list[Post]:
        return list(self._posts_by_tick.get(self._current_tick, []))

    def advance(self, new_tick: int) -> None:
        self._current_tick = new_tick
        self._tick_window.append(new_tick)
        # Prune posts older than memory window
        cutoff = new_tick - self.memory_ticks
        stale = [t for t in self._posts_by_tick if t < cutoff]
        for t in stale:
            for p in self._posts_by_tick.pop(t):
                self._posts_by_id.pop(p.post_id, None)
                # Author list prune
                author_lst = self._posts_by_author.get(p.author_id, [])
                self._posts_by_author[p.author_id] = [
                    q for q in author_lst if q.post_id != p.post_id
                ]

    # ---- Reporting helpers ------------------------------------------------

    def total_posts(self) -> int:
        return len(self._posts_by_id)

    def total_engagements(self) -> int:
        return len(self._engagements)

    def top_posts(self, n: int = 10) -> list[Post]:
        return sorted(self._posts_by_id.values(),
                      key=lambda p: -p.engagement)[:n]
