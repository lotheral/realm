"""SeedEvent model + ingestion interfaces.

SeedEvent is the canonical unit of real-world signal entering the simulation:
  - Normalized across data sources (RSS, manual, news APIs, …)
  - Carries pre-extracted topic / sentiment / entities (decision: processing
    happens inside the data source or a processor pipeline, before agents see it)
  - Immutable once created
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

# ---- SeedEvent ------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SeedEvent:
    """Canonical ingestion event."""

    event_id: str                       # globally unique, e.g. "rss:bbc:2026-04-23:001"
    source: str                         # source identifier: "rss://feeds.bbc..."
    timestamp: datetime                 # when the event occurred / was published
    headline: str
    body: str = ""                      # full body / description, optional
    topic: str = "news"                 # one of platforms.base.TOPIC
    sentiment: float = 0.0              # [-1, 1]
    virality: float = 1.5               # default seed for NewsChannel posting
    entities: tuple[str, ...] = ()      # extracted proper-noun entities
    geography: str | None = None        # ISO2 country code if detectable
    url: str | None = None
    raw: dict[str, object] = field(default_factory=dict, compare=False, hash=False)

    def short_label(self) -> str:
        return f"[{self.topic}] {self.headline[:60]}"


# ---- Interfaces -----------------------------------------------------------

class IDataSource(ABC):
    """A puller of raw events from some external or local medium.

    The fetch() method is stateful per-source: subsequent calls return only
    NEW events since the last call (deduplication via event_id).
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch(self) -> list[SeedEvent]:
        """Pull the latest batch. Returns [] if nothing new."""

    def close(self) -> None:  # noqa: B027
        """Optional cleanup (close open sockets, etc.). Default no-op."""


class ISeedProcessor(ABC):
    """Post-fetch pipeline step: enrich, filter, or reroute events.

    Processors run in order, each transforms the event list. Common uses:
      - Entity extraction
      - Topic classification
      - Sentiment scoring
      - Geography tagging
      - Deduplication across sources
    """

    @abstractmethod
    def process(self, events: list[SeedEvent]) -> list[SeedEvent]:
        ...


class IEventSink(ABC):
    """Destination for processed events — typically a NewsChannel platform or
    the knowledge graph."""

    @abstractmethod
    def emit(self, events: list[SeedEvent]) -> None: ...
