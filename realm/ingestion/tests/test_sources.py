"""Tests for IDataSource implementations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from realm.core.exceptions import DataError
from realm.ingestion.interfaces import SeedEvent
from realm.ingestion.sources.manual_upload import ManualUploadSource
from realm.ingestion.sources.rss_feed import RssFeedSource, _fetch_feed


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

    def test_private_url_is_rejected_before_http_request(self, monkeypatch):
        requested = False

        def fail_if_requested(*args, **kwargs):
            nonlocal requested
            requested = True
            raise AssertionError("private URL reached the HTTP client")

        monkeypatch.setattr("httpx.Client.stream", fail_if_requested)
        src = RssFeedSource("http://127.0.0.1/admin", source_id="fake")

        assert src.fetch() == []
        assert requested is False

    def test_redirect_target_is_revalidated(self, monkeypatch):
        import httpx

        real_client = httpx.Client

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

        monkeypatch.setattr(
            "realm.ingestion.sources.rss_feed.httpx.Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
        )

        def resolve(host, *args):
            address = "127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"
            return [(2, 1, 6, "", (address, 80))]

        monkeypatch.setattr(
            "realm.ingestion.sources.rss_feed.socket.getaddrinfo",
            resolve,
        )

        with pytest.raises(ValueError, match="non-public"):
            _fetch_feed("http://feeds.example/news", timeout=1.0)

    def test_configured_timeout_is_passed_to_http_client(self, monkeypatch):
        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def __enter__(self):
                raise RuntimeError("stop after client construction")

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("realm.ingestion.sources.rss_feed.httpx.Client", FakeClient)

        with pytest.raises(RuntimeError, match="client construction"):
            _fetch_feed("https://feeds.example/news", timeout=2.75)

        assert captured["timeout"] == 2.75
        assert captured["follow_redirects"] is False
        assert captured["trust_env"] is False

    def test_deduplication(self, monkeypatch):
        """Manually feed the source two identical entries; second fetch() should skip them."""
        src = RssFeedSource("http://example.com", source_id="unit")
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
        monkeypatch.setattr(
            "realm.ingestion.sources.rss_feed._fetch_feed",
            lambda *args, **kwargs: b"<rss />",
        )

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
