"""Sprint 18 WP1 — PolymarketClient tests.

Hermetic — uses ``httpx.MockTransport`` so no live API calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from realm.validation.polymarket import (
    BrierResult,
    PolymarketClient,
    ResolvedMarket,
    _parse_end_date,
    _parse_outcome_prices,
    _parse_resolved_market,
    aggregate_brier,
)

# ---- _parse_outcome_prices --------------------------------------------------


def test_parse_outcome_prices_from_json_string() -> None:
    """Polymarket returns the list JSON-encoded as a string."""
    assert _parse_outcome_prices('["0.99", "0.01"]') == (0.99, 0.01)


def test_parse_outcome_prices_from_plain_list() -> None:
    assert _parse_outcome_prices(["0.5", "0.5"]) == (0.5, 0.5)


def test_parse_outcome_prices_none_on_bad_input() -> None:
    for bad in (None, 42, "not json", '["only one"]', '[]', '"x"'):
        assert _parse_outcome_prices(bad) is None


# ---- _parse_end_date --------------------------------------------------------


def test_parse_end_date_handles_z_suffix() -> None:
    dt = _parse_end_date("2024-01-15T12:00:00Z")
    assert dt == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)


def test_parse_end_date_returns_none_on_garbage() -> None:
    assert _parse_end_date("not a date") is None
    assert _parse_end_date(None) is None


# ---- _parse_resolved_market ------------------------------------------------


def _good_market(**overrides) -> dict:
    base = {
        "closed": True,
        "question": "Will X happen?",
        "conditionId": "0xabc",
        "outcomePrices": '["0.99", "0.01"]',
        "volumeNum": 50000.0,
        "endDate": "2024-01-15T12:00:00Z",
        "category": "Politics",
        "resolutionSource": "https://example.com/resolved",
    }
    base.update(overrides)
    return base


def test_parses_clean_yes_resolution() -> None:
    m = _parse_resolved_market(_good_market(), min_volume=1000)
    assert m is not None
    assert m.outcome is True
    assert m.final_price_yes == 0.99
    assert m.category == "Politics"
    assert m.condition_id == "0xabc"


def test_parses_clean_no_resolution() -> None:
    m = _parse_resolved_market(
        _good_market(outcomePrices='["0.005", "0.995"]'),
        min_volume=1000,
    )
    assert m is not None
    assert m.outcome is False
    assert m.final_price_yes == 0.005


def test_rejects_degenerate_both_zero() -> None:
    """Refunded / unresolved Polymarket markets show 0 / 0 prices."""
    raw = _good_market(outcomePrices='["0", "0"]')
    assert _parse_resolved_market(raw, min_volume=1000) is None


def test_rejects_low_volume() -> None:
    raw = _good_market(volumeNum=500.0)
    assert _parse_resolved_market(raw, min_volume=1000) is None


def test_rejects_open_market() -> None:
    raw = _good_market(closed=False)
    assert _parse_resolved_market(raw, min_volume=1000) is None


def test_rejects_missing_question() -> None:
    raw = _good_market()
    del raw["question"]
    assert _parse_resolved_market(raw, min_volume=1000) is None


# ---- BrierResult.brier ----------------------------------------------------


def test_brier_zero_when_perfect_yes() -> None:
    assert BrierResult.brier(prob=1.0, actual=True) == 0.0


def test_brier_zero_when_perfect_no() -> None:
    assert BrierResult.brier(prob=0.0, actual=False) == 0.0


def test_brier_max_when_completely_wrong() -> None:
    assert BrierResult.brier(prob=1.0, actual=False) == 1.0
    assert BrierResult.brier(prob=0.0, actual=True) == 1.0


def test_brier_quarter_at_50_50() -> None:
    """A 50% guess always scores 0.25."""
    assert BrierResult.brier(prob=0.5, actual=True) == 0.25
    assert BrierResult.brier(prob=0.5, actual=False) == 0.25


# ---- aggregate_brier ------------------------------------------------------


def test_aggregate_brier_handles_empty() -> None:
    out = aggregate_brier([])
    assert out["realm"]["n"] == 0
    assert out["polymarket"]["mean"] == 0.0


def test_aggregate_brier_computes_mean() -> None:
    rows = [
        BrierResult(
            question="q1", condition_id="c1", actual_outcome=True,
            polymarket_price=0.95,
            realm_probability=0.8, llm_only_probability=0.7, sim_only_probability=0.5,
            realm_brier=0.04, llm_only_brier=0.09, sim_only_brier=0.25,
            polymarket_brier=0.0025,
        ),
        BrierResult(
            question="q2", condition_id="c2", actual_outcome=False,
            polymarket_price=0.10,
            realm_probability=0.2, llm_only_probability=0.3, sim_only_probability=0.5,
            realm_brier=0.04, llm_only_brier=0.09, sim_only_brier=0.25,
            polymarket_brier=0.01,
        ),
    ]
    agg = aggregate_brier(rows)
    assert agg["realm"]["mean"] == pytest.approx(0.04)
    assert agg["llm_only"]["mean"] == pytest.approx(0.09)
    assert agg["sim_only"]["mean"] == pytest.approx(0.25)
    assert agg["polymarket"]["mean"] == pytest.approx(0.00625)
    assert agg["realm"]["n"] == 2


# ---- PolymarketClient via MockTransport ----------------------------------


def test_fetch_resolved_markets_via_mock_transport() -> None:
    """Inject a mock transport so we can simulate the Gamma API offline."""
    page1 = [
        _good_market(question=f"Question {i}", conditionId=f"0x{i:04x}")
        for i in range(3)
    ]
    # Add a degenerate market that should be filtered out
    page1.append(_good_market(question="degen", outcomePrices='["0", "0"]'))
    page2: list[dict] = []  # empty page → pagination ends

    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        offset = int(request.url.params.get("offset", "0"))
        body = page1 if offset == 0 else page2
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as inner:
        client = PolymarketClient(client=inner)
        markets = client.fetch_resolved_markets(limit=10, min_volume=1000)
    assert len(markets) == 3  # degenerate filtered
    assert all(isinstance(m, ResolvedMarket) for m in markets)
    assert all(m.outcome is True for m in markets)


def test_fetch_handles_http_error_gracefully() -> None:
    """If the API returns 500 we get an empty list, not a crash."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as inner:
        client = PolymarketClient(client=inner)
        markets = client.fetch_resolved_markets(limit=10)
    assert markets == []


def test_fetch_stops_at_limit() -> None:
    """Pagination stops as soon as ``limit`` clean markets have been
    collected, even if more pages are available."""
    page = [
        _good_market(question=f"q-{i}", conditionId=f"0x{i:04x}")
        for i in range(100)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as inner:
        client = PolymarketClient(client=inner)
        markets = client.fetch_resolved_markets(
            limit=5, max_pages=10, min_volume=1000,
        )
    assert len(markets) == 5
