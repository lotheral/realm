"""Manual upload data source — load events from a local JSON or list.

Primary use cases:
  - Deterministic tests and validation scripts (live RSS isn't reproducible).
  - Offline replay of previously captured news streams.
  - Hand-crafted what-if scenarios.

File schema (JSON array):

    [
      {
        "event_id": "manual:001",
        "timestamp": "2026-04-23T12:00:00Z",
        "headline": "…",
        "body": "…",
        "topic": "finance",               # optional, default "news"
        "sentiment": -0.4,                # optional, default 0.0
        "entities": ["Apple", "China"],   # optional
        "geography": "US",                # optional
        "url": null
      },
      ...
    ]
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from realm.core.exceptions import DataError
from realm.core.logging import get_logger
from realm.ingestion.interfaces import IDataSource, SeedEvent

logger = get_logger(__name__)


class ManualUploadSource(IDataSource):
    """Queue-backed source. Pre-load with events; fetch() drains the queue."""

    def __init__(self, source_id: str = "manual", events: Iterable[SeedEvent] = ()) -> None:
        self._name = source_id
        self._pending: list[SeedEvent] = list(events)

    @property
    def name(self) -> str:
        return self._name

    def enqueue(self, event: SeedEvent) -> None:
        self._pending.append(event)

    def enqueue_many(self, events: Iterable[SeedEvent]) -> None:
        self._pending.extend(events)

    def fetch(self) -> list[SeedEvent]:
        batch, self._pending = self._pending, []
        if batch:
            logger.info("ManualUploadSource(%s): drained %d events", self._name, len(batch))
        return batch

    # ---- convenience loaders --------------------------------------------

    @classmethod
    def from_json_file(cls, path: str | Path, source_id: str | None = None) -> ManualUploadSource:
        p = Path(path)
        if not p.exists():
            raise DataError(f"Manual upload file not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            raise DataError(f"Manual upload file must contain a JSON array: {p}")
        events = [_event_from_dict(d, default_source=str(p)) for d in raw]
        return cls(source_id=source_id or f"manual:{p.stem}", events=events)


def _event_from_dict(d: dict[str, Any], default_source: str = "manual") -> SeedEvent:
    ts_raw = d.get("timestamp")
    if isinstance(ts_raw, str):
        ts = _parse_iso(ts_raw)
    elif isinstance(ts_raw, datetime):
        ts = ts_raw
    else:
        ts = datetime.fromisoformat("2026-01-01T00:00:00+00:00")

    entities_raw = d.get("entities", [])
    entities = tuple(str(e) for e in entities_raw) if entities_raw else ()

    return SeedEvent(
        event_id=str(d.get("event_id") or d.get("id") or f"manual:{hash(d.get('headline',''))}"),
        source=str(d.get("source") or default_source),
        timestamp=ts,
        headline=str(d.get("headline") or d.get("title") or ""),
        body=str(d.get("body") or d.get("description") or ""),
        topic=str(d.get("topic") or "news"),
        sentiment=float(d.get("sentiment", 0.0)),
        virality=float(d.get("virality", 1.5)),
        entities=entities,
        geography=d.get("geography"),
        url=d.get("url"),
        raw={},
    )


def _parse_iso(s: str) -> datetime:
    # Accept "Z" suffix and common ISO variants
    s2 = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s2)
