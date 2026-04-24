"""Tests for individual sampler functions (name, profession, socioeconomic)."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from realm.demographics.name_generator import generate_name
from realm.demographics.profession_generator import (
    sample_profession,
    tier_for_country,
)
from realm.demographics.socioeconomic import (
    sample_age,
    sample_education,
    sample_gender,
    sample_income,
    sample_marginal,
)


@pytest.fixture
def rng():
    return random.Random(12345)


class TestAge:
    def test_is_integer_in_bounds(self, rng):
        for _ in range(100):
            a = sample_age("US", rng)
            assert 18 <= a <= 90
            assert isinstance(a, int)

    def test_developing_country_younger_on_average(self):
        developing_ages = [sample_age("IN", random.Random(i)) for i in range(500)]
        developed_ages = [sample_age("JP", random.Random(i)) for i in range(500)]
        # Japan has much older population than India
        assert sum(developed_ages) / len(developed_ages) > sum(developing_ages) / len(developing_ages)


class TestGender:
    def test_values_valid(self, rng):
        for _ in range(100):
            assert sample_gender(rng) in {"M", "F", "X"}

    def test_distribution_roughly_balanced(self):
        rng = random.Random(0)
        counts = Counter(sample_gender(rng) for _ in range(10000))
        assert 0.45 <= counts["M"] / 10000 <= 0.53
        assert 0.45 <= counts["F"] / 10000 <= 0.53
        assert 0.005 <= counts["X"] / 10000 <= 0.035


class TestProfession:
    def test_tier_assigned_for_all_countries(self):
        for iso in ["CN", "IN", "US", "JP", "DE", "TR"]:
            assert tier_for_country(iso) in ("developed", "mid", "developing")

    def test_young_agent_often_student(self):
        profs = [sample_profession("US", random.Random(i), age_years=19)
                 for i in range(500)]
        counts = Counter(p["code"] for p in profs)
        # 60% chance student gate; distribution should show majority students
        assert counts["student"] > 200

    def test_old_developed_agent_often_retired(self):
        profs = [sample_profession("JP", random.Random(i), age_years=72)
                 for i in range(500)]
        counts = Counter(p["code"] for p in profs)
        assert counts["retired"] > 200

    def test_working_age_produces_diverse_professions(self):
        profs = [sample_profession("US", random.Random(i), age_years=35)
                 for i in range(1000)]
        counts = Counter(p["code"] for p in profs)
        # At least 6 distinct profession codes should appear
        assert len(counts) >= 6


class TestIncome:
    def test_income_positive(self, rng):
        inc = sample_income("US", 1.5, rng)
        assert inc > 0

    def test_zero_multiplier_gives_zero(self, rng):
        # homemaker with multiplier 0 → income 0
        inc = sample_income("US", 0.0, rng)
        assert inc == 0.0

    def test_developed_country_higher_than_developing(self):
        dev = [sample_income("US", 1.0, random.Random(i)) for i in range(500)]
        ing = [sample_income("BD", 1.0, random.Random(i)) for i in range(500)]
        assert sum(dev) / len(dev) > sum(ing) / len(ing) * 5  # US ≫ Bangladesh


class TestEducation:
    def test_value_in_known_bins(self, rng):
        for _ in range(100):
            assert sample_education("DE", rng) in {"primary", "secondary", "bachelor", "graduate"}

    def test_developing_lower_education_on_average(self):
        dev = Counter(sample_education("JP", random.Random(i)) for i in range(500))
        ing = Counter(sample_education("ET", random.Random(i)) for i in range(500))
        # Developing has much more "primary" than developed
        assert ing["primary"] > dev["primary"] * 3


class TestMarginal:
    def test_small_fraction_marginal(self):
        rng = random.Random(0)
        results = [sample_marginal(rng) for _ in range(10000)]
        flagged = sum(1 for flag, _ in results if flag)
        # ~10% marginal total (2% + 4% + 4%)
        assert 800 < flagged < 1200

    def test_category_when_flagged(self):
        rng = random.Random(0)
        for _ in range(100):
            flag, cat = sample_marginal(rng)
            if flag:
                assert cat in {"expert", "outlier", "influencer"}
            else:
                assert cat is None


class TestNameGeneration:
    def test_faker_locale_produces_name(self, rng):
        first, last = generate_name("TR", "M", rng)
        assert first and last
        assert isinstance(first, str) and isinstance(last, str)

    def test_fallback_pool_used_for_null_locale(self):
        # Pakistan has no faker_locale → uses fallback JSON
        first, last = generate_name("PK", "M", random.Random(0))
        # Fallback Urdu names
        from realm.core.config import load_json
        pk = load_json("names/pk.json")
        assert first in pk["first_names_m"]
        assert last in pk["last_names"]

    def test_gender_matches_pool(self):
        # Fallback pools have gender-specific lists
        for seed in range(20):
            first_m, _ = generate_name("ET", "M", random.Random(seed))
            first_f, _ = generate_name("ET", "F", random.Random(seed + 100))
            from realm.core.config import load_json
            et = load_json("names/et.json")
            assert first_m in et["first_names_m"]
            assert first_f in et["first_names_f"]
