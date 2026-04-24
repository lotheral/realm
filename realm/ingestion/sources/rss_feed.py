"""RSS / Atom feed data source.

Uses `feedparser` (pure Python, no API key). Dedupes across fetch() calls via
the entry GUID / link. Safe to call offline — returns [] when the feed is
unreachable, logging a warning.

SeedEvents produced here are UN-enriched: they carry raw headline/body/url with
topic='news', sentiment=0.0. A downstream ISeedProcessor chain (entity
extractor, sentiment, topic classifier) refines them before they hit the
NewsChannel.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

import feedparser

from realm.core.logging import get_logger
from realm.ingestion.interfaces import IDataSource, SeedEvent

logger = get_logger(__name__)


class RssFeedSource(IDataSource):
    def __init__(
        self,
        feed_url: str,
        source_id: str | None = None,
        *,
        request_timeout: float = 10.0,
    ) -> None:
        self._url = feed_url
        self._name = source_id or feed_url
        self._timeout = request_timeout
        self._seen_ids: set[str] = set()

    @property
    def name(self) -> str:
        return self._name

    def fetch(self) -> list[SeedEvent]:
        try:
            parsed = feedparser.parse(self._url, request_headers={"User-Agent": "REALM/0.1"})
        except Exception as e:
            logger.warning("RSS fetch failed for %s: %s", self._url, e)
            return []

        if parsed.bozo and not parsed.entries:
            logger.warning("RSS parse returned no entries for %s (bozo=%s)",
                           self._url, getattr(parsed, "bozo_exception", ""))
            return []

        events: list[SeedEvent] = []
        for entry in parsed.entries:
            eid = self._entry_id(entry)
            if eid in self._seen_ids:
                continue
            self._seen_ids.add(eid)
            events.append(self._entry_to_event(entry, eid))
        logger.info("RssFeedSource(%s): %d new events", self._name, len(events))
        return events

    # ---- helpers ---------------------------------------------------------

    def _entry_id(self, entry) -> str:
        """Stable dedup key: prefer `id`, then `link`, then hash of title+pubdate."""
        if getattr(entry, "id", None):
            return f"{self._name}:{entry.id}"
        if getattr(entry, "link", None):
            return f"{self._name}:{entry.link}"
        title = getattr(entry, "title", "")
        pub = getattr(entry, "published", "") or getattr(entry, "updated", "")
        h = hashlib.sha1(f"{title}|{pub}".encode()).hexdigest()[:12]
        return f"{self._name}:{h}"

    def _entry_to_event(self, entry, eid: str) -> SeedEvent:
        ts = self._parse_timestamp(entry)
        return SeedEvent(
            event_id=eid,
            source=f"rss://{self._url}",
            timestamp=ts,
            headline=getattr(entry, "title", "").strip(),
            body=(getattr(entry, "summary", "") or getattr(entry, "description", "") or "").strip(),
            topic="news",
            sentiment=0.0,
            virality=1.5,
            entities=(),
            geography=None,
            url=getattr(entry, "link", None),
            raw={"feed_source": self._name},
        )

    @staticmethod
    def _parse_timestamp(entry) -> datetime:
        for attr in ("published_parsed", "updated_parsed", "created_parsed"):
            t = getattr(entry, attr, None)
            if t is not None:
                return datetime(*t[:6], tzinfo=UTC)
        return datetime.now(UTC)


def multi_feed_sources(feeds: Iterable[tuple[str, str]]) -> list[RssFeedSource]:
    """Convenience: build a list of RssFeedSource from [(source_id, url), ...]."""
    return [RssFeedSource(url, source_id=sid) for sid, url in feeds]
