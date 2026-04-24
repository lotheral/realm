"""Tests for CulturalModifier end-to-end."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from realm.culture.modifier import CulturalModifier, compose_modifiers
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector


def _profile(country: str, religion: str, region: str) -> DemographicProfile:
    return DemographicProfile(
        agent_id="AGT_TEST",
        name_first="Test", name_last="Agent", gender="M",
        country=country, city="Test City",
        birth_datetime=datetime(1990, 1, 1, tzinfo=UTC),
        birth_latitude=0.0, birth_longitude=0.0, birth_timezone="UTC",
        age_years=35,
        profession_code="professionals", profession_name="Professionals",
        income_annual_usd=30000, education_level="bachelor",
        marginal_flag=False, marginal_category=None,
        primary_religion=religion, region=region,
    )


class TestComposedModifiers:
    def test_japan_boosts_patience_and_conscientiousness(self):
        p = _profile("JP", "shinto_buddhist", "asia_east")
        m = compose_modifiers(p)
        # High LTO + shinto_buddhist + asia_east all push patience up
        assert m.get("patience", 0) > 0.10
        assert m.get("conscientiousness", 0) > 0.05

    def test_usa_boosts_individualism(self):
        p = _profile("US", "christian", "america_north")
        m = compose_modifiers(p)
        assert m.get("individualism", 0) > 0.10

    def test_egypt_raises_authority_compliance(self):
        p = _profile("EG", "muslim", "mena")
        m = compose_modifiers(p)
        # High PDI + muslim religion + mena region all contribute
        assert m.get("authority_compliance", 0) > 0.05


class TestCulturalModifier:
    def test_blend_zero_returns_input(self):
        cm = CulturalModifier(blend_ratio=0.0)
        tv = TraitVector(openness=0.6)
        p = _profile("JP", "shinto_buddhist", "asia_east")
        assert cm.apply(tv, p) == tv

    def test_applies_modifier(self):
        cm = CulturalModifier(blend_ratio=1.0)
        tv = TraitVector.neutral()
        p = _profile("US", "christian", "america_north")
        new = cm.apply(tv, p)
        # Individualism should have risen
        assert new.individualism > tv.individualism

    def test_bounded_output(self):
        cm = CulturalModifier(blend_ratio=1.0)
        tv = TraitVector.neutral()
        for country, religion, region in [
            ("US", "christian", "america_north"),
            ("JP", "shinto_buddhist", "asia_east"),
            ("EG", "muslim", "mena"),
            ("IN", "hindu", "asia_south"),
        ]:
            p = _profile(country, religion, region)
            new = cm.apply(tv, p)
            for name, v in new.to_dict().items():
                assert 0.0 <= v <= 1.0, f"{country}.{name}={v}"


class TestBlendRatio:
    def test_ratio_half_produces_smaller_shift(self):
        cm_full = CulturalModifier(blend_ratio=1.0)
        cm_half = CulturalModifier(blend_ratio=0.5)
        tv = TraitVector.neutral()
        p = _profile("JP", "shinto_buddhist", "asia_east")

        full = cm_full.apply(tv, p)
        half = cm_half.apply(tv, p)

        # Shift from neutral is ~2x for full vs half
        full_shift = abs(full.patience - 0.5)
        half_shift = abs(half.patience - 0.5)
        assert full_shift > half_shift
        assert pytest.approx(full_shift / 2, abs=0.01) == half_shift
