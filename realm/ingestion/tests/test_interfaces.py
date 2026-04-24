"""Tests for SeedEvent + abstract interfaces."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from realm.ingestion.interfaces import (
    IDataSource,
    IEventSink,
    ISeedProcessor,
    SeedEvent,
)


class TestSeedEvent:
    def test_required_fields(self):
        e = SeedEvent(
            event_id="e1",
            source="test",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            headline="Hello world",
        )
        assert e.event_id == "e1"
        assert e.topic == "news"
        assert e.sentiment == 0.0
        assert e.entities == ()
        assert e.geography is None

    def test_frozen(self):
        e = SeedEvent(
            event_id="e1", source="t",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            headline="h",
        )
        with pytest.raises((AttributeError, Exception)):
            e.headline = "changed"  # type: ignore[misc]

    def test_short_label(self):
        e = SeedEvent(
            event_id="e1", source="t",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            headline="A quick brown fox jumps over the lazy dog",
            topic="tech",
        )
        assert "[tech]" in e.short_label()


class TestAbstracts:
    def test_idatasource_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IDataSource()  # type: ignore[abstract]

    def test_iseedprocessor_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ISeedProcessor()  # type: ignore[abstract]

    def test_ieventsink_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IEventSink()  # type: ignore[abstract]
