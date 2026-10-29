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
import ipaddress
import socket
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx

from realm.core.logging import get_logger
from realm.ingestion.interfaces import IDataSource, SeedEvent

logger = get_logger(__name__)

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_REDIRECTS = 5
_USER_AGENT = "REALM/0.1"


def _validate_public_http_url(url: str) -> None:
    """Reject URLs that can target local, private, or otherwise non-public hosts."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("RSS URL must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("RSS URL must not include credentials")

    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, parsed.port)}
    except OSError as exc:
        raise ValueError(f"RSS host could not be resolved: {parsed.hostname}") from exc
    if not addresses:
        raise ValueError(f"RSS host could not be resolved: {parsed.hostname}")
    if any(not _is_global_address(address) for address in addresses):
        raise ValueError("RSS URL resolves to a non-public address")


def _is_global_address(address: str) -> bool:
    return ipaddress.ip_address(address.split("%", 1)[0]).is_global


def _check_peer_is_global(response: httpx.Response) -> None:
    """Re-check the address httpx actually connected to (closes the DNS-rebinding
    gap between the pre-flight resolve and httpx's own resolve)."""
    stream = response.extensions.get("network_stream")
    if stream is None:  # non-network transport (e.g. MockTransport in tests)
        return
    server_addr = stream.get_extra_info("server_addr")
    if server_addr and not _is_global_address(str(server_addr[0])):
        raise ValueError("RSS connection reached a non-public address")


def _check_deadline(deadline: float) -> None:
    # httpx timeouts are per-operation; a slow-drip server could otherwise
    # hold the fetch open indefinitely.
    if time.monotonic() > deadline:
        raise ValueError("RSS feed fetch exceeded the total timeout")


def _fetch_feed(url: str, *, timeout: float) -> bytes:
    current_url = url
    deadline = time.monotonic() + timeout
    with httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        trust_env=False,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        for redirect_count in range(_MAX_REDIRECTS + 1):
            _check_deadline(deadline)
            _validate_public_http_url(current_url)
            with client.stream("GET", current_url) as response:
                _check_peer_is_global(response)
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("RSS redirect is missing a Location header")
                    if redirect_count == _MAX_REDIRECTS:
                        raise ValueError("RSS feed exceeded the redirect limit")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    _check_deadline(deadline)
                    total += len(chunk)
                    if total > _MAX_RESPONSE_BYTES:
                        raise ValueError("RSS feed response is too large")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise ValueError("RSS feed redirect handling failed")


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
            content = _fetch_feed(self._url, timeout=self._timeout)
            parsed = feedparser.parse(content)
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
