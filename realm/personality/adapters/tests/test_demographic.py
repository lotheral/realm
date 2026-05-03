"""Tests for DemographicAdapter — DemographicProfile → TraitVector (Hofstede primary)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from realm.core.exceptions import PersonalityEmbeddingError
from realm.demographics.interfaces import DemographicProfile
from realm.personality.adapters import DemographicAdapter
from realm.personality.trait_vector import TraitVector


def _profile(country: str = "US", city: str = "San Francisco",
             religion: str = "non-religious", region: str = "americas") -> DemographicProfile:
    return DemographicProfile(
        agent_id="test-1",
        name_first="Test", name_last="Agent",
        gender="X",
        country=country, city=city,
        birth_datetime=datetime(1985, 6, 15, 12, 0, tzinfo=UTC),
        birth_latitude=37.77, birth_longitude=-122.42, birth_timezone="America/Los_Angeles",
        age_years=40,
        profession_code="2-T", profession_name="software engineer",
        income_annual_usd=120000.0,
        education_level="bachelor",
        marginal_flag=False, marginal_category=None,
        primary_religion=religion, region=region,
    )


class TestDemographicAdapterInterface:
    def test_adapter_type(self):
        assert DemographicAdapter().adapter_type == "demographic"

    def test_applies_cultural_modifier_false(self):
        """Hofstede is primary here; CulturalModifier would double-count."""
        assert DemographicAdapter().applies_cultural_modifier is False

    def test_rejects_non_profile_input(self):
        a = DemographicAdapter()
        with pytest.raises(PersonalityEmbeddingError, match="DemographicProfile"):
            a.build({"country": "US"})


class TestDemographicAdapterBehavior:
    def test_build_returns_trait_vector(self):
        a = DemographicAdapter()
        tv = a.build(_profile())
        assert isinstance(tv, TraitVector)

    def test_output_in_unit_interval(self):
        a = DemographicAdapter()
        tv = a.build(_profile())
        for name in TraitVector.trait_names():
            assert 0.0 <= getattr(tv, name) <= 1.0

    def test_deterministic_same_profile(self):
        a = DemographicAdapter()
        p = _profile()
        tv1 = a.build(p)
        tv2 = a.build(p)
        assert tv1 == tv2

    def test_different_countries_produce_different_traits(self):
        """Hofstede varies by country → adapter output should vary too."""
        a = DemographicAdapter()
        us = a.build(_profile(country="US"))
        jp = a.build(_profile(country="JP"))
        assert us != jp

    def test_political_spectrum_varies_by_country(self):
        """Sprint 11: political_spectrum is no longer hard-coded 0.5; it is
        derived from Hofstede pdi+idv so different countries diverge."""
        a = DemographicAdapter()
        us = a.build(_profile(country="US"))
        jp = a.build(_profile(country="JP"))
        cn = a.build(_profile(country="CN"))
        dk = a.build(_profile(country="DK"))
        # All four must produce distinct values.
        values = {us.political_spectrum, jp.political_spectrum,
                  cn.political_spectrum, dk.political_spectrum}
        assert len(values) == 4

    def test_political_spectrum_within_bounds(self):
        """All 66 supported countries must keep political_spectrum in [0, 1]
        and the spread must be wide enough to be meaningful (>0.20)."""
        from realm.demographics.country_data import load_hofstede

        a = DemographicAdapter()
        spectrum_values: list[float] = []
        for iso2 in load_hofstede():
            tv = a.build(_profile(country=iso2))
            assert 0.0 <= tv.political_spectrum <= 1.0
            spectrum_values.append(tv.political_spectrum)
        spread = max(spectrum_values) - min(spectrum_values)
        assert spread >= 0.20, f"political_spectrum spread {spread:.3f} below 0.20"

    def test_political_spectrum_deterministic(self):
        """Same country + same call must yield identical political_spectrum."""
        a = DemographicAdapter()
        first = a.build(_profile(country="US")).political_spectrum
        second = a.build(_profile(country="US")).political_spectrum
        assert first == second
