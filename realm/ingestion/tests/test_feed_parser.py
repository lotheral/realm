"""Sprint 14 WP5: FeedParser orchestration tests.

Covers:
1. parse_text — heuristic path (no LLM): sentiment, keywords, category.
2. parse_multiple — averages sentiment across items.
3. parse_rss — wraps RssFeedSource; we monkey-patch fetch() to return a
   synthetic SeedEvent without hitting the network.
4. category detection through CategoryRouter.
5. validation: empty inputs raise ValueError.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from realm.ingestion.feed_parser import FeedParser, ParsedFeed
from realm.ingestion.interfaces import SeedEvent
from realm.output.category_router import CategoryRouter


def _router() -> CategoryRouter:
    return CategoryRouter()


def test_parse_text_heuristic_negative() -> None:
    p = FeedParser(category_router=_router())
    out = p.parse_text("Stock market crash, banking sector collapse, panic spreads")
    assert isinstance(out, ParsedFeed)
    assert out.source == "manual"
    assert out.sentiment_score < 0
    # Either 'markets' or 'economics' is acceptable (both keywords present);
    # we just require SOME category was detected.
    assert out.detected_category is not None
    assert any(k in {"crash", "collapse", "stock", "panic", "spreads", "banking"} for k in out.keywords)


def test_parse_text_heuristic_positive() -> None:
    p = FeedParser(category_router=_router())
    out = p.parse_text(
        "Federal Reserve cuts rates, easing monetary policy, stimulus boost"
    )
    assert out.sentiment_score > 0
    assert out.detected_category in ("economics", "markets")


def test_parse_text_rejects_empty() -> None:
    p = FeedParser()
    with pytest.raises(ValueError):
        p.parse_text("")
    with pytest.raises(ValueError):
        p.parse_text("    ")


def test_parse_multiple_averages_sentiment() -> None:
    """parse_multiple should return the arithmetic mean of per-item sentiments."""
    from realm.ingestion.sentiment import parse_sentiment

    p = FeedParser(category_router=_router())
    a = "Federal Reserve cuts rates, easing monetary policy"
    b = "Hawkish tightening, raises rates, prolonged"
    agg = p.parse_multiple([a, b])
    assert agg.source == "multi"
    expected = round((parse_sentiment(a) + parse_sentiment(b)) / 2, 4)
    assert abs(agg.sentiment_score - expected) < 0.01
    assert agg.items == (a, b)


def test_parse_multiple_rejects_empty() -> None:
    p = FeedParser()
    with pytest.raises(ValueError):
        p.parse_multiple([])
    with pytest.raises(ValueError):
        p.parse_multiple(["", "  "])


def test_parse_rss_via_monkey_patch(monkeypatch) -> None:
    """parse_rss must round-trip RssFeedSource events into ParsedFeed
    without touching the network. Monkey-patch the source's fetch()."""
    fake_event = SeedEvent(
        event_id="fake-1",
        source="rss://example.com",
        timestamp=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        headline="Bitcoin ETF approval drives bullish rally to all-time-high",
        body="Major institutional inflows reported across crypto markets.",
        topic="news",
        sentiment=0.0,
        virality=2.0,
    )

    from realm.ingestion.sources import rss_feed as rss_mod

    class FakeRss:
        def __init__(self, *a, **kw):
            pass

        def fetch(self):
            return [fake_event]

    monkeypatch.setattr(rss_mod, "RssFeedSource", FakeRss)
    p = FeedParser(category_router=_router())
    out = p.parse_rss("https://example.com/feed.xml")
    assert len(out) == 1
    item = out[0]
    assert item.source == "rss"
    assert "Bitcoin" in item.title
    assert item.sentiment_score > 0
    assert item.detected_category == "crypto"


def test_parser_without_router_returns_none_category() -> None:
    p = FeedParser(category_router=None)
    out = p.parse_text("Bitcoin ETF approved, adoption surges")
    assert out.detected_category is None


def test_keywords_are_unique_and_bounded() -> None:
    p = FeedParser()
    out = p.parse_text(
        "Crash crash crash growth growth boom recovery growth recovery boom"
    )
    assert len(out.keywords) == len(set(out.keywords))
    assert len(out.keywords) <= 10
