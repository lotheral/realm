"""WorldGenerator + PopulationSpec constrained sampling (Sprint 21)."""

from realm.demographics.population_spec import PopulationSpec
from realm.demographics.world_generator import WorldGenerator


class TestPopulationSpecSampling:
    def test_none_spec_and_empty_spec_are_byte_identical(self):
        base = WorldGenerator(master_seed=42).generate(40)
        empty = WorldGenerator(master_seed=42, population_spec=PopulationSpec()).generate(40)
        assert base == empty

    def test_same_spec_same_seed_is_deterministic(self):
        spec = PopulationSpec(countries=("TR", "DE"), age_min=18, age_max=29)
        a = WorldGenerator(master_seed=7, population_spec=spec).generate(30)
        b = WorldGenerator(master_seed=7, population_spec=spec).generate(30)
        assert a == b

    def test_country_restriction_applies_to_every_agent(self):
        spec = PopulationSpec(countries=("TR",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(25)
        assert profiles
        assert all(p.country == "TR" for p in profiles)

    def test_region_restriction_applies_to_every_agent(self):
        spec = PopulationSpec(regions=("mena",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(25)
        assert profiles
        assert all(p.region == "mena" for p in profiles)

    def test_age_band_applies_to_every_agent(self):
        spec = PopulationSpec(age_min=18, age_max=29)
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(40)
        assert all(18 <= p.age_years <= 29 for p in profiles)

    def test_gender_filter_applies_to_every_agent(self):
        spec = PopulationSpec(genders=("F",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(40)
        assert all(p.gender == "F" for p in profiles)

    def test_education_filter_applies_to_every_agent(self):
        spec = PopulationSpec(education_levels=("bachelor", "graduate"))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(40)
        assert all(p.education_level in ("bachelor", "graduate") for p in profiles)

    def test_rare_gender_filter_terminates(self):
        # X is sampled at 2% — the 200-draw cap plus deterministic fallback
        # must still return n agents, all X.
        spec = PopulationSpec(genders=("X",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(15)
        assert len(profiles) == 15
        assert all(p.gender == "X" for p in profiles)

    def test_combined_filters(self):
        spec = PopulationSpec(countries=("TR",), age_min=30, age_max=44, genders=("M",))
        profiles = WorldGenerator(master_seed=11, population_spec=spec).generate(20)
        assert all(
            p.country == "TR" and 30 <= p.age_years <= 44 and p.gender == "M"
            for p in profiles
        )
