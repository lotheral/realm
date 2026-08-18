"""Tests for PopulationSpec — per-question target population (Sprint 21)."""

import pytest

from realm.demographics.population_spec import PopulationSpec


class TestValidation:
    def test_empty_spec_is_unrestricted(self):
        spec = PopulationSpec()
        assert spec.is_unrestricted()
        assert len(spec.resolve_countries()) == 66

    def test_country_filter_resolves_subset(self):
        spec = PopulationSpec(countries=("TR", "DE"))
        isos = {c["iso2"] for c in spec.resolve_countries()}
        assert isos == {"TR", "DE"}
        assert not spec.is_unrestricted()

    def test_region_filter_resolves_member_countries(self):
        spec = PopulationSpec(regions=("mena",))
        resolved = spec.resolve_countries()
        assert resolved
        assert all(c["region"] == "mena" for c in resolved)

    def test_countries_and_regions_are_unioned(self):
        spec = PopulationSpec(countries=("TR",), regions=("mena",))
        isos = {c["iso2"] for c in spec.resolve_countries()}
        mena_only = {c["iso2"] for c in PopulationSpec(regions=("mena",)).resolve_countries()}
        assert isos == mena_only | {"TR"}

    def test_unknown_country_raises(self):
        with pytest.raises(ValueError, match="unknown country"):
            PopulationSpec(countries=("XX",)).resolve_countries()

    def test_unknown_region_raises(self):
        with pytest.raises(ValueError, match="unknown region"):
            PopulationSpec(regions=("atlantis",)).resolve_countries()

    def test_inverted_age_range_raises(self):
        with pytest.raises(ValueError, match="age_min"):
            PopulationSpec(age_min=60, age_max=30).validate()

    def test_unknown_gender_raises(self):
        with pytest.raises(ValueError, match="gender"):
            PopulationSpec(genders=("Q",)).validate()

    def test_unknown_education_raises(self):
        with pytest.raises(ValueError, match="education"):
            PopulationSpec(education_levels=("phd",)).validate()

    def test_valid_filters_pass_validate(self):
        PopulationSpec(
            countries=("TR",), age_min=18, age_max=29,
            genders=("F",), education_levels=("bachelor", "graduate"),
        ).validate()


class TestDescribe:
    def test_unrestricted_describes_as_global(self):
        assert PopulationSpec().describe() == "global"

    def test_describe_lists_active_filters(self):
        spec = PopulationSpec(countries=("TR", "DE"), age_min=18, age_max=29, genders=("F",))
        desc = spec.describe()
        assert "TR" in desc and "DE" in desc
        assert "18-29" in desc
        assert "F" in desc
