"""Re-export of IDataSource so concrete source files import from one place."""

from __future__ import annotations

from realm.ingestion.interfaces import IDataSource, SeedEvent

__all__ = ["IDataSource", "SeedEvent"]
