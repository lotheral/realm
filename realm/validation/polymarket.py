"""Sprint 18 WP1 — Polymarket Gamma API client + Brier scoring.

Fetches RESOLVED markets (``closed=true``) from Polymarket's public Gamma
API for backtesting. We only care about resolved markets where one
outcome cleanly won (price ~1.0) so the actual outcome is unambiguous.
``outcomePrices`` arrives as a JSON-encoded string list (e.g.
``'["0.99", "0.01"]'``) — the client parses it and surfaces a clean
``ResolvedMarket`` dataclass.

No authentication required for public Gamma endpoints. The client uses
synchronous httpx to fit REALM's blocking simulation pipeline (a separate
async client lives in the polyargus project but isn't reused here).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DEFAULT_TIMEOUT_SEC = 30.0
# Outcome-resolution threshold: a market counts as "cleanly resolved
# YES" when outcomePrices[0] >= this. Polymarket usually settles to
# exactly 1.0 / 0.0 but degenerate / refunded markets show 0 / 0.
_CLEAN_RESOLUTION_THRESHOLD = 0.99


@dataclass(frozen=True)
class ResolvedMarket:
    """One Polymarket market that resolved cleanly to YES or NO."""

    question: str
    condition_id: str
    category: str | None        # Polymarket's own tag (e.g. "Politics")
    outcome: bool               # True = YES won, False = NO won
    final_price_yes: float      # YES price at resolution (~0 or ~1)
    volume: float               # total trading volume (USD-ish)
    end_date: datetime
    resolution_source: str | None


@dataclass(frozen=True)
class BrierResult:
    """One row of the backtest report — Brier score per method."""

    question: str
    condition_id: str
    actual_outcome: bool
    polymarket_price: float
    realm_probability: float
    llm_only_probability: float
    sim_only_probability: float
    realm_brier: float          # (realm_prob - actual)^2
    llm_only_brier: float
    sim_only_brier: float
    polymarket_brier: float

    @staticmethod
    def brier(prob: float, actual: bool) -> float:
        target = 1.0 if actual else 0.0
        return (prob - target) ** 2


class PolymarketClient:
    """Synchronous wrapper around the public Gamma Markets API.

    Usage::

        client = PolymarketClient()
        markets = client.fetch_resolved_markets(limit=50, min_volume=10000)
        for m in markets:
            print(m.question, m.outcome, m.final_price_yes)
    """

    def __init__(
        self,
        base_url: str = GAMMA_HOST,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_sec
        # Allow injection of a custom client for testing (e.g. mocked
        # transport); construct one if not provided.
        self._client = client if client is not None else httpx.Client(
            timeout=timeout_sec,
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PolymarketClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Fetch endpoints
    # ------------------------------------------------------------------

    def fetch_raw_closed_markets(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Fetch one page of closed markets as raw API dicts.

        Caller usually wants :meth:`fetch_resolved_markets` instead.
        """
        params = {
            "closed": "true",
            "limit": str(limit),
            "offset": str(offset),
        }
        resp = self._client.get(f"{self._base_url}/markets", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def fetch_resolved_markets(
        self,
        limit: int = 100,
        min_volume: float = 10000.0,
        max_pages: int = 20,
    ) -> list[ResolvedMarket]:
        """Fetch closed markets and parse them into clean ``ResolvedMarket``.

        Filters out:
        - Markets with both outcome prices at 0 (refunded / unresolved)
        - Markets with neither outcome price >= 0.99 (still in dispute)
        - Markets with volume below ``min_volume`` (low-quality, illiquid)

        ``limit`` is the number of CLEAN resolved markets returned; the
        client pages through Gamma until that count is reached or
        ``max_pages`` is hit.
        """
        out: list[ResolvedMarket] = []
        offset = 0
        page_size = 100
        for _page in range(max_pages):
            try:
                raw_batch = self.fetch_raw_closed_markets(
                    limit=page_size, offset=offset,
                )
            except httpx.HTTPError as e:
                logger.warning(
                    "Gamma API request failed at offset %d (%s); "
                    "stopping pagination",
                    offset, e,
                )
                break
            if not raw_batch:
                break
            for raw in raw_batch:
                m = _parse_resolved_market(raw, min_volume=min_volume)
                if m is not None:
                    out.append(m)
                    if len(out) >= limit:
                        return out
            if len(raw_batch) < page_size:
                break
            offset += page_size
        return out


# ----------------------------------------------------------------------
# Parsing helpers (module-level for easier testing)
# ----------------------------------------------------------------------


def _parse_outcome_prices(raw: object) -> tuple[float, float] | None:
    """Polymarket returns ``outcomePrices`` as a JSON-encoded string list
    (e.g. ``'["0.99", "0.01"]'``). Decode + coerce to floats."""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, (list, tuple)):
        parsed = raw
    else:
        return None
    if not isinstance(parsed, (list, tuple)) or len(parsed) < 2:
        return None
    try:
        return float(parsed[0]), float(parsed[1])
    except (TypeError, ValueError):
        return None


def _parse_end_date(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).astimezone(UTC)
    except ValueError:
        return None


def _parse_resolved_market(
    raw: dict, *, min_volume: float,
) -> ResolvedMarket | None:
    """Parse one Gamma API market dict into a ResolvedMarket, or None
    if it doesn't pass the cleanliness filters."""
    if not raw.get("closed"):
        return None

    question = raw.get("question")
    cond_id = raw.get("conditionId")
    if not isinstance(question, str) or not isinstance(cond_id, str):
        return None

    prices = _parse_outcome_prices(raw.get("outcomePrices"))
    if prices is None:
        return None
    yes_price, no_price = prices
    # Reject degenerate / unresolved settlements
    if yes_price < _CLEAN_RESOLUTION_THRESHOLD and no_price < _CLEAN_RESOLUTION_THRESHOLD:
        return None
    outcome_yes = yes_price >= _CLEAN_RESOLUTION_THRESHOLD

    volume = raw.get("volumeNum")
    if not isinstance(volume, (int, float)):
        try:
            volume = float(raw.get("volume", 0))
        except (TypeError, ValueError):
            volume = 0.0
    volume = float(volume)
    if volume < min_volume:
        return None

    end_date = _parse_end_date(raw.get("endDate") or raw.get("endDateIso"))
    if end_date is None:
        return None

    return ResolvedMarket(
        question=question,
        condition_id=cond_id,
        category=raw.get("category") if isinstance(raw.get("category"), str) else None,
        outcome=outcome_yes,
        final_price_yes=yes_price,
        volume=volume,
        end_date=end_date,
        resolution_source=raw.get("resolutionSource") if isinstance(
            raw.get("resolutionSource"), str
        ) else None,
    )


def aggregate_brier(results: Iterable[BrierResult]) -> dict[str, dict[str, float]]:
    """Compute mean / median / std for each method's Brier score.

    Returns a dict like::

        {
          "realm":      {"mean": 0.18, "median": 0.16, "std": 0.09, "n": 50},
          "llm_only":   {...},
          "sim_only":   {...},
          "polymarket": {...},
        }
    """
    import statistics
    rows = list(results)
    out: dict[str, dict[str, float]] = {}
    for key, attr in (
        ("realm", "realm_brier"),
        ("llm_only", "llm_only_brier"),
        ("sim_only", "sim_only_brier"),
        ("polymarket", "polymarket_brier"),
    ):
        values = [getattr(r, attr) for r in rows]
        if not values:
            out[key] = {"mean": 0.0, "median": 0.0, "std": 0.0, "n": 0}
            continue
        out[key] = {
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "n": len(values),
        }
    return out
