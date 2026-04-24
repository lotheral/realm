"""IngestionManager — orchestrates data sources → processors → sinks.

Typical pipeline per tick:
    sources.fetch() → (concat)
    → ISeedProcessor chain (enrich, dedupe)
    → KnowledgeGraph.ingest()
    → NewsChannelPlatform.publish_events()

The manager exposes a simple .pull(tick) that the SimulationEngine calls at
the start of each tick.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realm.core.logging import get_logger
from realm.ingestion.interfaces import IDataSource, ISeedProcessor, SeedEvent
from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.simulation.platforms.news_channel import NewsChannelPlatform

logger = get_logger(__name__)


@dataclass
class IngestionManager:
    sources: list[IDataSource] = field(default_factory=list)
    processors: list[ISeedProcessor] = field(default_factory=list)
    knowledge_graph: KnowledgeGraph | None = None
    news_channel: NewsChannelPlatform | None = None

    def add_source(self, src: IDataSource) -> None:
        self.sources.append(src)

    def add_processor(self, proc: ISeedProcessor) -> None:
        self.processors.append(proc)

    def pull(self, tick: int) -> list[SeedEvent]:
        """Fetch + enrich + dispatch. Returns the final processed event list."""
        raw: list[SeedEvent] = []
        for src in self.sources:
            try:
                raw.extend(src.fetch())
            except Exception as e:
                logger.warning("Source %s.fetch() failed: %s", src.name, e)

        if not raw:
            return []

        processed = raw
        for proc in self.processors:
            try:
                processed = proc.process(processed)
            except Exception as e:
                logger.warning("Processor %s failed: %s", type(proc).__name__, e)

        if self.knowledge_graph is not None:
            added = self.knowledge_graph.ingest(processed)
            if added:
                logger.debug("KG ingested %d events", added)

        if self.news_channel is not None:
            self.news_channel.publish_events(processed, tick=tick)

        return processed

    def close(self) -> None:
        import contextlib
        for src in self.sources:
            with contextlib.suppress(Exception):
                src.close()
