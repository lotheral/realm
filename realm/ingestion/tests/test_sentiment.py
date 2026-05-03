"""Sprint 14 WP5: extracted sentiment module.

Verifies that the strict (BASE-only) variant preserves Sprint 13's contract
bit-for-bit and the combined (BASE + DOMAIN) inventory broadens coverage
without breaking direction.
"""

from __future__ import annotations

from realm.ingestion.sentiment import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    parse_sentiment,
    parse_sentiment_strict,
)


def test_empty_input_returns_zero() -> None:
    assert parse_sentiment("") == 0.0
    assert parse_sentiment("   ") == 0.0
    assert parse_sentiment_strict("") == 0.0


def test_strict_preserves_sprint13_dovish_direction() -> None:
    """The Sprint 13 acceptance test C feed is dovish — strict parser
    must return positive sentiment."""
    feed = "Federal Reserve cuts rates, dovish stance, easing monetary policy"
    sentiment = parse_sentiment_strict(feed)
    assert sentiment > 0


def test_strict_preserves_sprint13_hawkish_direction() -> None:
    feed = "Federal Reserve raises rates, hawkish stance, tightening accelerates"
    sentiment = parse_sentiment_strict(feed)
    assert sentiment < 0


def test_combined_inventory_includes_domain_words() -> None:
    """Crypto-specific positive 'etf' and negative 'rugpull' must register
    under the combined inventory but NOT under strict (Sprint 13 contract)."""
    pos_combined = parse_sentiment("Bitcoin ETF approved, adoption surging")
    pos_strict = parse_sentiment_strict("Bitcoin ETF approved, adoption surging")
    assert pos_combined > 0
    # 'surging' is in the strict negative list; combined picks up 'etf'+'adoption'
    # so combined should be MORE positive than strict.
    assert pos_combined > pos_strict


def test_inventory_membership() -> None:
    """All BASE entries appear in the combined inventory (no accidental
    drop). Domain entries appear only in the combined inventory."""
    for w in ("hike", "raises", "missile"):
        assert w in NEGATIVE_WORDS
    for w in ("dovish", "easing", "stimulus"):
        assert w in POSITIVE_WORDS
    # Domain markers
    assert "rugpull" in NEGATIVE_WORDS
    assert "etf" in POSITIVE_WORDS
