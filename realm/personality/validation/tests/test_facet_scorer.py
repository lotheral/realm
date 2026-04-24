"""Tests for IPIP-NEO-120 facet scorer."""

from __future__ import annotations

import numpy as np
import pytest

from realm.personality.validation.facet_scorer import (
    DEFAULT_DAT_PATH,
    DOMAINS,
    FACET_CODES,
    FACET_TO_DOMAIN,
    _parse_row,
    load_scoring_key,
    score_dataset,
)


def _neutral_row(case: int = 1, sex: str = "1", age: int = 30) -> bytes:
    """Build a 151-char IPIP120.dat row: demographics + 120 items all '3' (neutral)."""
    case_str = f"{case:6d}"
    # sex (1 char), age (2 chars), SEC/MIN/HOUR/DAY/MONTH (2 chars each = 10), YEAR (3), COUNTRY (9)
    prefix = case_str + sex + f"{age:2d}" + "00" + "00" + "00" + "01" + "00" + "115" + "USA      "
    items = "3" * 120
    return (prefix + items).encode("ascii")


def _extreme_row(value: str = "5") -> bytes:
    """All items = `value` for testing scoring extremes."""
    prefix = "     1" + "1" + "30" + "000000010011" + "0USA      "[:9]
    # Keep row length at 151; reuse helper layout consistent with neutral_row
    prefix = "     1" + "1" + "30" + "00" + "00" + "00" + "01" + "00" + "115" + "USA      "
    items = value * 120
    return (prefix + items).encode("ascii")


class TestScoringKey:
    def test_loads_120_items(self):
        k = load_scoring_key()
        assert len(k.item_to_facet) == 120

    def test_30_unique_facets_four_items_each(self):
        k = load_scoring_key()
        from collections import Counter
        counts = Counter(k.item_to_facet.values())
        assert len(counts) == 30
        for facet, n in counts.items():
            assert n == 4, f"{facet} has {n} items"

    def test_facet_codes_match_canonical_list(self):
        k = load_scoring_key()
        assert set(k.item_to_facet.values()) == set(FACET_CODES)


class TestFacetCodes:
    def test_30_facet_codes(self):
        assert len(FACET_CODES) == 30

    def test_facet_to_domain_mapping(self):
        for facet in FACET_CODES:
            assert FACET_TO_DOMAIN[facet] == facet[0]


class TestRowParsing:
    def test_parse_neutral_row(self):
        row = _neutral_row()
        assert len(row) == 151
        rec = _parse_row(row)
        assert rec is not None
        assert rec.case == 1
        assert rec.sex == "M"
        assert rec.age == 30
        assert rec.country == "USA"
        assert rec.items.shape == (120,)
        assert (rec.items == 3).all()

    def test_parse_short_row_returns_none(self):
        assert _parse_row(b"not enough chars") is None

    def test_parse_extreme_row_items_all_5(self):
        row = _extreme_row("5")
        rec = _parse_row(row)
        assert rec is not None
        assert (rec.items == 5).all()


class TestScoring:
    def test_neutral_produces_mid_scores(self):
        rows = [_parse_row(_neutral_row(case=i)) for i in range(10)]
        facets, domains, kept = score_dataset([r for r in rows if r])
        assert facets.shape == (10, 30)
        assert domains.shape == (10, 5)
        # (3-1)/4 = 0.5
        np.testing.assert_allclose(facets, 0.5, atol=1e-6)
        np.testing.assert_allclose(domains, 0.5, atol=1e-6)

    def test_extreme_high_produces_one(self):
        rows = [_parse_row(_extreme_row("5")) for _ in range(5)]
        facets, domains, kept = score_dataset([r for r in rows if r])
        np.testing.assert_allclose(facets, 1.0, atol=1e-6)
        np.testing.assert_allclose(domains, 1.0, atol=1e-6)

    def test_extreme_low_produces_zero(self):
        rows = [_parse_row(_extreme_row("1")) for _ in range(5)]
        facets, domains, kept = score_dataset([r for r in rows if r])
        np.testing.assert_allclose(facets, 0.0, atol=1e-6)
        np.testing.assert_allclose(domains, 0.0, atol=1e-6)

    def test_rows_with_too_many_missing_items_dropped(self):
        # Build a row where one facet has 3 missing items (only 1 valid) → dropped
        key = load_scoring_key()
        # Find items belonging to O1 (first facet)
        facet_items = [i for i, f in key.item_to_facet.items() if f == "O1"]
        items = bytearray(b"3" * 120)
        for item_num in facet_items[:3]:
            items[item_num - 1] = ord("0")  # mark missing
        prefix = "     1" + "1" + "30" + "00" + "00" + "00" + "01" + "00" + "115" + "USA      "
        row = prefix.encode("ascii") + bytes(items)
        rec = _parse_row(row)
        assert rec is not None
        _, _, kept = score_dataset([rec], min_valid_per_facet=3)
        assert len(kept) == 0


@pytest.mark.skipif(
    not DEFAULT_DAT_PATH.exists(),
    reason="IPIP120.dat not downloaded — see data/external/MANIFEST.md",
)
class TestRealDataSmoke:
    """Only runs if IPIP120.dat is present locally."""

    def test_load_first_500_rows(self):
        from realm.personality.validation.facet_scorer import load_ipip120
        recs = load_ipip120(max_rows=500)
        assert len(recs) == 500
        assert all(r.items.shape == (120,) for r in recs)

    def test_score_500_rows(self):
        from realm.personality.validation.facet_scorer import load_ipip120
        recs = load_ipip120(max_rows=500)
        facets, domains, kept = score_dataset(recs)
        # Real-world data should retain most rows (≥95%)
        assert len(kept) >= int(0.90 * len(recs)), (
            f"Only {len(kept)} of {len(recs)} retained"
        )
        assert facets.shape == (len(kept), 30)
        assert domains.shape == (len(kept), 5)
        # Real means ought to sit around mid-scale, not extreme
        for di, dom in enumerate(DOMAINS):
            mean = float(domains[:, di].mean())
            assert 0.3 <= mean <= 0.8, f"{dom} domain mean {mean:.3f} suspicious"
