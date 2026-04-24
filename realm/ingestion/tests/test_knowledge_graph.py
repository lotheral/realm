"""Tests for KnowledgeGraph."""

from __future__ import annotations

from datetime import UTC, datetime

from realm.ingestion.interfaces import SeedEvent
from realm.ingestion.knowledge_graph import KnowledgeGraph


def _event(eid: str, entities: tuple[str, ...], sentiment: float = 0.0) -> SeedEvent:
    return SeedEvent(
        event_id=eid, source="t",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        headline=f"Event {eid}",
        sentiment=sentiment,
        entities=entities,
    )


class TestIngest:
    def test_adds_new_events(self):
        kg = KnowledgeGraph()
        added = kg.ingest([_event("e1", ("Apple", "China"))])
        assert added == 1
        assert kg.size() == (2, 1)  # 2 nodes, 1 edge

    def test_dedupes_by_event_id(self):
        kg = KnowledgeGraph()
        e = _event("e1", ("A", "B"))
        kg.ingest([e])
        kg.ingest([e])   # same event_id → skipped
        nodes, edges = kg.size()
        assert nodes == 2
        assert edges == 1

    def test_co_occurrence_weights(self):
        kg = KnowledgeGraph()
        kg.ingest([
            _event("e1", ("Apple", "China")),
            _event("e2", ("Apple", "China")),
            _event("e3", ("Apple", "USA")),
        ])
        # Apple-China edge should weigh more than Apple-USA
        ac = kg.graph.edges["Apple", "China"]["weight"]
        au = kg.graph.edges["Apple", "USA"]["weight"]
        assert ac == 2
        assert au == 1


class TestQueries:
    def test_hot_entities(self):
        kg = KnowledgeGraph()
        kg.ingest([
            _event("e1", ("A", "B")),
            _event("e2", ("A", "C")),
            _event("e3", ("A", "D")),
            _event("e4", ("B", "C")),
        ])
        hot = kg.hot_entities(n=2)
        assert hot[0][0] == "A"
        assert hot[0][1] == 3

    def test_sentiment_of(self):
        kg = KnowledgeGraph()
        kg.ingest([
            _event("e1", ("X", "Y"), sentiment=0.5),
            _event("e2", ("X", "Y"), sentiment=0.5),
        ])
        assert kg.sentiment_of("X") == 0.5

    def test_unknown_sentiment_zero(self):
        kg = KnowledgeGraph()
        assert kg.sentiment_of("Nonexistent") == 0.0

    def test_related_entities(self):
        kg = KnowledgeGraph()
        kg.ingest([
            _event("e1", ("A", "B")),
            _event("e2", ("A", "B")),
            _event("e3", ("A", "C")),
        ])
        related = kg.related_entities("A")
        # B should rank first (co-occurrence 2) ahead of C (co-occurrence 1)
        assert related[0][0] == "B"
        assert related[0][1] == 2


class TestDecay:
    def test_decay_reduces_weights(self):
        kg = KnowledgeGraph()
        kg.ingest([_event("e1", ("A", "B"))])
        w0 = kg.graph.edges["A", "B"]["weight"]
        kg.decay(0.5)
        w1 = kg.graph.edges["A", "B"]["weight"]
        assert w1 == w0 * 0.5

    def test_decay_removes_stale_edges(self):
        kg = KnowledgeGraph()
        kg.ingest([_event("e1", ("A", "B"))])
        # Decay aggressively — weight drops below 0.1 threshold
        for _ in range(10):
            kg.decay(0.3)
        assert not kg.graph.has_edge("A", "B")

    def test_decay_validation(self):
        kg = KnowledgeGraph()
        import pytest
        with pytest.raises(ValueError):
            kg.decay(0.0)
        with pytest.raises(ValueError):
            kg.decay(1.5)
