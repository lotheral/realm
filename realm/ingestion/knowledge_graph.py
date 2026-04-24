"""Knowledge graph built from SeedEvent entity streams.

Nodes: entities (proper nouns from extraction). Edge weight = co-occurrence
count. Each edge and node tracks:
    - first_seen, last_seen tick / timestamp
    - mention_count
    - aggregate sentiment (running mean)

Decay: call decay(factor) between ticks to gradually fade old relationships so
the KG reflects recent salience, not permanent history.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import networkx as nx

from realm.ingestion.interfaces import SeedEvent


@dataclass
class KnowledgeGraph:
    """In-memory entity co-occurrence graph."""

    graph: nx.Graph = field(default_factory=nx.Graph)
    _ingested_event_ids: set[str] = field(default_factory=set, repr=False)

    # ---- ingestion -----------------------------------------------------

    def ingest(self, events: Iterable[SeedEvent]) -> int:
        """Add events to the graph. Returns the number of NEW events absorbed."""
        added = 0
        for e in events:
            if e.event_id in self._ingested_event_ids:
                continue
            self._ingested_event_ids.add(e.event_id)
            added += 1
            self._ingest_one(e)
        return added

    def _ingest_one(self, e: SeedEvent) -> None:
        entities = [x for x in e.entities if x]
        now = e.timestamp
        # Add nodes
        for entity in entities:
            if entity in self.graph:
                node = self.graph.nodes[entity]
                node["mention_count"] += 1
                node["last_seen"] = now
                prev = node["sentiment_sum"]
                node["sentiment_sum"] = prev + e.sentiment
            else:
                self.graph.add_node(
                    entity,
                    first_seen=now, last_seen=now,
                    mention_count=1,
                    sentiment_sum=e.sentiment,
                )
        # Add co-occurrence edges (all unordered pairs in this event)
        for i, a in enumerate(entities):
            for b in entities[i + 1:]:
                if a == b:
                    continue
                if self.graph.has_edge(a, b):
                    self.graph.edges[a, b]["weight"] += 1.0
                    self.graph.edges[a, b]["last_seen"] = now
                else:
                    self.graph.add_edge(a, b, weight=1.0, first_seen=now, last_seen=now)

    # ---- queries -------------------------------------------------------

    def hot_entities(self, n: int = 10) -> list[tuple[str, int]]:
        """Top-N entities by mention_count."""
        data = [
            (name, int(d.get("mention_count", 0)))
            for name, d in self.graph.nodes(data=True)
        ]
        data.sort(key=lambda t: -t[1])
        return data[:n]

    def sentiment_of(self, entity: str) -> float:
        """Average sentiment of events mentioning `entity`. 0.0 if unknown."""
        if entity not in self.graph:
            return 0.0
        node = self.graph.nodes[entity]
        count = max(1, node.get("mention_count", 1))
        return float(node.get("sentiment_sum", 0.0)) / count

    def related_entities(self, entity: str, k: int = 5) -> list[tuple[str, float]]:
        """Top-k entities most co-occurring with `entity`."""
        if entity not in self.graph:
            return []
        neighbors = [
            (nb, float(self.graph.edges[entity, nb].get("weight", 0.0)))
            for nb in self.graph.neighbors(entity)
        ]
        neighbors.sort(key=lambda t: -t[1])
        return neighbors[:k]

    def size(self) -> tuple[int, int]:
        return self.graph.number_of_nodes(), self.graph.number_of_edges()

    # ---- decay --------------------------------------------------------

    def decay(self, factor: float = 0.95) -> None:
        """Multiply all edge weights by `factor` and drop sub-threshold edges.

        Also reduces node mention_count; nodes that drop below 1 are removed.
        Call once per tick (or at a slower cadence) to keep the graph focused
        on recent activity.
        """
        if factor <= 0 or factor > 1:
            raise ValueError("decay factor must be in (0, 1]")

        to_remove_edges = []
        for u, v, data in self.graph.edges(data=True):
            data["weight"] = float(data.get("weight", 0.0)) * factor
            if data["weight"] < 0.1:
                to_remove_edges.append((u, v))
        self.graph.remove_edges_from(to_remove_edges)

        to_remove_nodes = []
        for name, data in self.graph.nodes(data=True):
            data["mention_count"] = float(data.get("mention_count", 0)) * factor
            if data["mention_count"] < 0.5:
                to_remove_nodes.append(name)
        self.graph.remove_nodes_from(to_remove_nodes)
