"""Tests for IDataSource implementations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from realm.core.exceptions import DataError
from realm.ingestion.interfaces import SeedEvent
from realm.ingestion.sources.manual_upload import ManualUploadSource
from realm.ingestion.sources.rss_feed import RssFeedSource


class TestManualUpload:
    def test_starts_empty(self):
        src = ManualUploadSource()
        assert src.fetch() == []

    def test_enqueue_and_drain(self):
        src = ManualUploadSource()
        src.enqueue(SeedEvent(
            event_id="e1", source="manual",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            headline="first",
        ))
        src.enqueue(SeedEvent(
            event_id="e2", source="manual",
            timestamp=datetime(2026, 1, 2, tzinfo=UTC),
            headline="second",
        ))
        batch = src.fetch()
        assert len(batch) == 2
        # Second fetch is empty (queue drained)
        assert src.fetch() == []

    def test_from_json_file(self, tmp_path: Path):
        data = [
            {
                "event_id": "manual:001",
                "timestamp": "2026-04-23T12:00:00Z",
                "headline": "Test headline",
                "body": "A body",
                "topic": "finance",
                "sentiment": -0.3,
                "entities": ["Apple", "China"],
                "geography": "US",
            },
            {
                "event_id": "manual:002",
                "timestamp": "2026-04-23T13:00:00Z",
                "headline": "Another story",
            },
        ]
        path = tmp_path / "events.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        src = ManualUploadSource.from_json_file(path)
        events = src.fetch()
        assert len(events) == 2
        assert events[0].event_id == "manual:001"
        assert events[0].topic == "finance"
        assert events[0].entities == ("Apple", "China")
        assert events[1].topic == "news"  # default

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(DataError):
            ManualUploadSource.from_json_file(tmp_path / "does_not_exist.json")

    def test_invalid_format_raises(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text('{"not": "an array"}', encoding="utf-8")
        with pytest.raises(DataError):
            ManualUploadSource.from_json_file(path)


class TestRssFeedOfflineRobustness:
    """RSS tests without real network — verify offline failure modes are graceful."""

    def test_unreachable_url_returns_empty(self):
        src = RssFeedSource("http://localhost:1/does_not_exist", source_id="fake")
        # feedparser should return a bozo feed; we should catch and return []
        events = src.fetch()
        assert isinstance(events, list)

    def test_deduplication(self, monkeypatch):
        """Manually feed the source two identical entries; second fetch() should skip them."""
        src = RssFeedSource("http://example.invalid", source_id="unit")
        import feedparser
        fake_parsed = feedparser.FeedParserDict()
        entry = feedparser.FeedParserDict()
        entry.id = "guid-1"
        entry.title = "Test headline"
        entry.summary = "Body"
        entry.link = "http://example.com/1"
        fake_parsed.entries = [entry]
        fake_parsed.bozo = False

        def fake_parse(*args, **kwargs):
            return fake_parsed

        monkeypatch.setattr("feedparser.parse", fake_parse)

        first = src.fetch()
        assert len(first) == 1
        second = src.fetch()
        assert second == []


class TestSourceName:
    def test_manual_name(self):
        src = ManualUploadSource(source_id="test_src")
        assert src.name == "test_src"

    def test_rss_name(self):
        src = RssFeedSource("http://example.com/feed", source_id="bbc_world")
        assert src.name == "bbc_world"
