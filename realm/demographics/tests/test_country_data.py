"""Tests for demographics.country_data."""

from __future__ import annotations

import pytest

from realm.core.exceptions import DataError
from realm.demographics.country_data import (
    cities_by_country,
    countries_by_iso,
    get_cities_for,
    get_country,
    get_hofstede,
    load_cities,
    load_countries,
    load_hofstede,
)


class TestLoaders:
    def test_countries_loaded(self):
        cs = load_countries()
        assert len(cs) >= 25
        assert all("iso2" in c and "population" in c for c in cs)

    def test_cities_loaded(self):
        cs = load_cities()
        assert len(cs) >= 100
        assert all("lat" in c and "lon" in c and "country" in c for c in cs)

    def test_hofstede_loaded(self):
        h = load_hofstede()
        assert "CN" in h and "US" in h
        for scores in h.values():
            assert set(scores.keys()) == {"pdi", "idv", "mas", "uai", "lto", "ivr"}


class TestIndexedLookups:
    def test_countries_by_iso_is_unique(self):
        by_iso = countries_by_iso()
        assert len(by_iso) == len(load_countries())

    def test_cities_by_country_groups(self):
        groups = cities_by_country()
        assert "CN" in groups
        assert len(groups["CN"]) >= 3

    def test_get_country_known(self):
        c = get_country("TR")
        assert c["iso2"] == "TR"
        assert c["name"].startswith("Türkiye") or c["name"] == "Turkey"

    def test_get_country_unknown_raises(self):
        with pytest.raises(DataError):
            get_country("XX")

    def test_get_cities_for_country(self):
        cities = get_cities_for("DE")
        assert len(cities) >= 3
        assert {"Berlin", "Hamburg"} <= {c["name"] for c in cities}

    def test_get_cities_unknown_raises(self):
        with pytest.raises(DataError):
            get_cities_for("XX")


class TestHofstede:
    def test_known_country_returns_scores(self):
        h = get_hofstede("JP")
        assert h["pdi"] == 54
        assert h["mas"] == 95  # Japan's famous MAS score

    def test_unknown_country_falls_back_to_global_mean(self):
        h = get_hofstede("XX")
        assert set(h.keys()) == {"pdi", "idv", "mas", "uai", "lto", "ivr"}

    def test_scores_in_valid_range(self):
        # Hofstede scale is nominally 0-100 but empirical country values can
        # slightly exceed the endpoint (e.g. PT uai=104, GR uai=112, SK pdi=104).
        # Cap at 120 to absorb this published-value leakage.
        for iso, scores in load_hofstede().items():
            for dim, v in scores.items():
                assert 0 <= v <= 120, f"{iso}.{dim}={v} out of range"

    def test_estimated_countries_still_have_all_six_dims(self):
        """Countries using a regional proxy must still carry all 6 dims."""
        import json
        from pathlib import Path
        raw = json.loads(
            (Path(__file__).resolve().parents[3] / "data"
             / "hofstede_scores.json").read_text(encoding="utf-8"),
        )
        estimated = raw.get("_estimated_countries", {})
        for iso2 in estimated:
            assert iso2 in raw["scores"], f"estimated {iso2} missing from scores"
            dims = set(raw["scores"][iso2].keys())
            assert dims == {"pdi", "idv", "mas", "uai", "lto", "ivr"}, (
                f"estimated {iso2} missing dims: {dims}"
            )
