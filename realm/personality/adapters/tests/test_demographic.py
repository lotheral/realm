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

    def test_political_spectrum_stays_neutral(self):
        """Scope boundary: political_spectrum is excluded across the pipeline."""
        a = DemographicAdapter()
        tv = a.build(_profile())
        # Must stay at 0.5 default — demographic adapter reuses compose_modifiers
        # which derives from Hofstede/religion/region, none of which map here.
        assert abs(tv.political_spectrum - 0.5) < 1e-9
