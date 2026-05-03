"""Sprint 14 WP5 — unified feed parser.

Thin orchestration layer that turns three input shapes into a single
``ParsedFeed`` payload consumed by the dashboard's scenario flow:
  1. Manual text (the existing textarea path)
  2. A single RSS feed URL — wraps `RssFeedSource`
  3. A list of texts — averages sentiment + concatenates keywords

Sentiment comes from `realm.ingestion.sentiment.parse_sentiment` (combined
base + domain inventory). Category is detected via `CategoryRouter.route`
when a router is supplied — the dashboard already constructs one.

The optional `LLMRouter().for_task("parser")` backend is consulted when set
in the environment; in that path the heuristic result is replaced by a
structured JSON parse via ``prompts/feed_parser/analyze_feed.yaml``. The
caller never needs to know which path produced the answer — fields are the
same shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from realm.core.logging import get_logger
from realm.ingestion.sentiment import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    parse_sentiment,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class ParsedFeed:
    """Canonical feed-parser output. Wire-compatible with the
    /api/feed/parse endpoint response."""

    source: str  # 'manual', 'rss', 'multi', 'llm'
    title: str
    content: str
    timestamp: datetime
    sentiment_score: float  # [-1, +1]
    keywords: tuple[str, ...]
    detected_category: str | None
    items: tuple[str, ...] = field(default_factory=tuple)


def _extract_keywords(text: str, *, limit: int = 10) -> tuple[str, ...]:
    """Pick keywords by hitting either side of the sentiment lexicon plus the
    longest non-stopword tokens. Cheap, deterministic, no NLP deps."""
    if not text:
        return ()
    lower = text.lower()
    found_pos = [w for w in POSITIVE_WORDS if w in lower]
    found_neg = [w for w in NEGATIVE_WORDS if w in lower]
    # Prefer SENTIMENT-bearing words first, then long tokens (proper nouns).
    seen: set[str] = set()
    out: list[str] = []
    for w in (*found_pos, *found_neg):
        if w not in seen:
            seen.add(w)
            out.append(w)
        if len(out) >= limit:
            return tuple(out)
    # Heuristic fallback: pluck capitalized words, then any 6+ letter words.
    for tok in text.split():
        clean = tok.strip(".,!?\"'()[]{}:;").lower()
        if not clean or clean in seen:
            continue
        if len(clean) >= 6:
            seen.add(clean)
            out.append(clean)
        if len(out) >= limit:
            break
    return tuple(out)


class FeedParser:
    """Glue between the dashboard scenario panel and the ingestion stack.

    Construct once per FastAPI app instance (the predict endpoint does this).
    All parse_* methods are stateless except for the wrapped RssFeedSource's
    own dedup cache, which we recreate per call so each /api/feed/parse
    request fetches fresh items independently of the last call.
    """

    def __init__(
        self,
        category_router: Any | None = None,
        llm_backend: Any | None = None,
    ) -> None:
        self._router = category_router
        self._llm = llm_backend

    # ---- public surface --------------------------------------------------

    def parse_text(self, text: str) -> ParsedFeed:
        if not text or not text.strip():
            raise ValueError("parse_text requires a non-empty string")
        if self._llm is not None:
            try:
                llm_payload = self._call_llm(text)
                if llm_payload is not None:
                    return self._llm_to_parsed_feed(llm_payload, text=text)
            except Exception as e:
                logger.warning("feed_parser LLM call failed; falling back to heuristic: %s", e)
        return self._heuristic_parse(text, source="manual")

    def parse_rss(self, feed_url: str, max_items: int = 5) -> list[ParsedFeed]:
        # Lazy import keeps RssFeedSource (and feedparser) out of the import
        # graph until someone actually parses an RSS URL.
        from realm.ingestion.sources.rss_feed import RssFeedSource

        src = RssFeedSource(feed_url, source_id=feed_url)
        events = src.fetch()[:max_items]
        out: list[ParsedFeed] = []
        for ev in events:
            text = f"{ev.headline}\n{ev.body}".strip()
            if not text:
                continue
            parsed = self._heuristic_parse(text, source="rss", title=ev.headline, timestamp=ev.timestamp)
            out.append(parsed)
        return out

    def parse_multiple(self, texts: list[str]) -> ParsedFeed:
        clean = [t for t in (texts or []) if t and t.strip()]
        if not clean:
            raise ValueError("parse_multiple requires at least one non-empty text")
        sentiments = [parse_sentiment(t) for t in clean]
        avg = sum(sentiments) / len(sentiments)
        joined = "\n---\n".join(clean)
        keywords = _extract_keywords(joined, limit=15)
        category = self._detect_category(joined)
        return ParsedFeed(
            source="multi",
            title=f"aggregated feed ({len(clean)} items)",
            content=joined,
            timestamp=datetime.now(UTC),
            sentiment_score=round(max(-1.0, min(1.0, avg)), 4),
            keywords=keywords,
            detected_category=category,
            items=tuple(clean),
        )

    # ---- helpers ---------------------------------------------------------

    def _heuristic_parse(
        self, text: str,
        *,
        source: str,
        title: str | None = None,
        timestamp: datetime | None = None,
    ) -> ParsedFeed:
        sentiment = parse_sentiment(text)
        keywords = _extract_keywords(text)
        return ParsedFeed(
            source=source,
            title=(title or text.strip().splitlines()[0][:140]),
            content=text,
            timestamp=timestamp or datetime.now(UTC),
            sentiment_score=round(sentiment, 4),
            keywords=keywords,
            detected_category=self._detect_category(text),
        )

    def _detect_category(self, text: str) -> str | None:
        if self._router is None or not text or not text.strip():
            return None
        try:
            match = self._router.route(text)
        except Exception:
            return None
        return match.category_id

    def _call_llm(self, text: str) -> dict[str, Any] | None:
        """Best-effort call into the parser LLM backend with the
        feed_parser prompt template. Returns the parsed JSON dict or None
        if the call did not produce a usable shape."""
        try:
            from pathlib import Path

            import yaml
        except ImportError:
            return None
        prompt_path = (
            Path(__file__).resolve().parents[2]
            / "prompts" / "feed_parser" / "analyze_feed.yaml"
        )
        if not prompt_path.exists():
            return None
        cfg = yaml.safe_load(prompt_path.read_text(encoding="utf-8")) or {}
        system = str(cfg.get("system", "")).strip()
        user_template = str(cfg.get("user", "")).strip()
        user = user_template.format(text=text)
        if not system or not user:
            return None
        data = self._llm.complete_json(system, user, temperature=0.1)
        if not isinstance(data, dict):
            return None
        return data

    def _llm_to_parsed_feed(self, payload: dict[str, Any], *, text: str) -> ParsedFeed:
        sentiment = float(payload.get("sentiment", 0.0))
        sentiment = max(-1.0, min(1.0, sentiment))
        keywords = tuple(str(k) for k in payload.get("keywords", []))
        category = payload.get("domain") or payload.get("category")
        return ParsedFeed(
            source="llm",
            title=text.strip().splitlines()[0][:140],
            content=text,
            timestamp=datetime.now(UTC),
            sentiment_score=round(sentiment, 4),
            keywords=keywords,
            detected_category=str(category) if category else None,
        )


__all__ = ("FeedParser", "ParsedFeed")
