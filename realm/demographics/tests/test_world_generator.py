"""Integration tests for WorldGenerator."""

from __future__ import annotations

from collections import Counter

from realm.demographics.interfaces import DemographicProfile
from realm.demographics.world_generator import WorldGenerator


class TestGeneration:
    def test_zero_agents_returns_empty(self):
        gen = WorldGenerator(master_seed=42)
        assert gen.generate(0) == []

    def test_fifty_agents(self):
        gen = WorldGenerator(master_seed=42)
        profiles = gen.generate(50)
        assert len(profiles) == 50
        assert all(isinstance(p, DemographicProfile) for p in profiles)

    def test_unique_agent_ids(self):
        gen = WorldGenerator(master_seed=42)
        profiles = gen.generate(100)
        ids = [p.agent_id for p in profiles]
        assert len(set(ids)) == len(ids)

    def test_age_within_bounds(self):
        gen = WorldGenerator(master_seed=42)
        for p in gen.generate(100):
            assert 18 <= p.age_years <= 90

    def test_birth_datetime_timezone_aware(self):
        gen = WorldGenerator(master_seed=42)
        for p in gen.generate(50):
            assert p.birth_datetime.tzinfo is not None

    def test_latitude_longitude_in_bounds(self):
        gen = WorldGenerator(master_seed=42)
        for p in gen.generate(200):
            assert -90 <= p.birth_latitude <= 90
            assert -180 <= p.birth_longitude <= 180


class TestDistributions:
    def test_country_distribution_reflects_population(self):
        gen = WorldGenerator(master_seed=42)
        profiles = gen.generate(2000)
        counts = Counter(p.country for p in profiles)
        # China + India should dominate (combined > 35%)
        cn_in = counts["CN"] + counts["IN"]
        assert cn_in / 2000 > 0.35

    def test_multiple_cities_per_country(self):
        gen = WorldGenerator(master_seed=42)
        profiles = gen.generate(2000)
        # Most large countries should have at least 3 distinct cities represented
        by_country_cities: dict[str, set[str]] = {}
        for p in profiles:
            by_country_cities.setdefault(p.country, set()).add(p.city)
        # India/China should each have 4+ distinct cities in a 2000-agent sample
        assert len(by_country_cities.get("IN", set())) >= 3
        assert len(by_country_cities.get("CN", set())) >= 3


class TestDeterminism:
    def test_same_seed_same_output(self):
        a = WorldGenerator(master_seed=42).generate(100)
        b = WorldGenerator(master_seed=42).generate(100)
        assert [p.agent_id for p in a] == [p.agent_id for p in b]
        assert [(p.country, p.city, p.gender) for p in a] == \
               [(p.country, p.city, p.gender) for p in b]

    def test_different_seeds_different_output(self):
        a = WorldGenerator(master_seed=42).generate(100)
        b = WorldGenerator(master_seed=999).generate(100)
        assert [(p.country, p.city) for p in a] != [(p.country, p.city) for p in b]


class TestMarginals:
    def test_some_agents_marginal(self):
        gen = WorldGenerator(master_seed=42)
        profiles = gen.generate(1000)
        flagged = sum(1 for p in profiles if p.marginal_flag)
        assert 50 < flagged < 150  # ~10% expected

    def test_marginal_category_consistent(self):
        gen = WorldGenerator(master_seed=42)
        for p in gen.generate(500):
            if p.marginal_flag:
                assert p.marginal_category in {"expert", "outlier", "influencer"}
            else:
                assert p.marginal_category is None
