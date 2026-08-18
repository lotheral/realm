"""ReactionDistribution — pooled stance shares + segment breakdown (Sprint 21)."""

from datetime import UTC, datetime
from types import SimpleNamespace

from realm.demographics.interfaces import DemographicProfile
from realm.output.reaction import (
    ReactionDistribution,
    StanceShares,
    age_band,
    bucket_three_way,
    compute_reaction_distribution,
    stance_shift,
)


def make_profile(i: int, country: str = "TR", region: str = "mena",
                 age: int = 25, gender: str = "M") -> DemographicProfile:
    return DemographicProfile(
        agent_id=f"AGT_{i:06d}", name_first="A", name_last="B", gender=gender,
        country=country, city="X",
        birth_datetime=datetime(2000, 1, 1, tzinfo=UTC),
        birth_latitude=0.0, birth_longitude=0.0, birth_timezone="UTC",
        age_years=age, profession_code="p", profession_name="P",
        income_annual_usd=1000.0, education_level="secondary",
        marginal_flag=False, marginal_category=None,
        primary_religion="none", region=region,
    )


def make_sim(trait_values: list[float], profiles: list[DemographicProfile]):
    agents = [
        SimpleNamespace(traits=SimpleNamespace(openness=v), profile=p)
        for v, p in zip(trait_values, profiles, strict=True)
    ]
    return SimpleNamespace(agents=agents, drift_engine=None)


BASELINE = {"openness": 0.5}
WEIGHTS = {"openness": 1.0}


class TestAgeBand:
    def test_bands(self):
        assert age_band(18) == "18-29"
        assert age_band(29) == "18-29"
        assert age_band(30) == "30-44"
        assert age_band(45) == "45-59"
        assert age_band(60) == "60+"
        assert age_band(90) == "60+"


class TestBucketThreeWay:
    def test_fixed_threshold_overrides_sigma(self):
        devs = [0.2, 0.2, -0.2, 0.0]
        sup, opp, neu = bucket_three_way(devs, threshold=0.1)
        assert (sup, opp, neu) == (0.5, 0.25, 0.25)

    def test_default_threshold_matches_legacy(self):
        # No threshold arg -> same sigma-based behavior as the old
        # api/predict.py _bucket_three_way.
        sup, opp, neu = bucket_three_way([])
        assert (sup, opp, neu) == (0.34, 0.33, 0.33)


class TestComputeReactionDistribution:
    def test_pools_across_all_branches(self):
        profiles = [make_profile(i) for i in range(4)]
        sim_a = make_sim([0.9, 0.9, 0.9, 0.9], profiles)   # all support
        sim_b = make_sim([0.1, 0.1, 0.1, 0.1], profiles)   # all oppose
        rd = compute_reaction_distribution(
            [sim_a, sim_b], BASELINE, WEIGHTS, min_segment_size=1,
        )
        assert rd.n_agents == 8
        assert abs(rd.stances.support - 0.5) < 1e-9
        assert abs(rd.stances.oppose - 0.5) < 1e-9
        assert abs(rd.stances.support + rd.stances.oppose + rd.stances.neutral - 1.0) < 1e-9

    def test_segments_split_by_country(self):
        profiles = (
            [make_profile(i, country="TR", region="mena") for i in range(3)]
            + [make_profile(i + 3, country="DE", region="europe_west") for i in range(3)]
        )
        # TR agents pushed up, DE agents pushed down
        sim = make_sim([0.9, 0.9, 0.9, 0.1, 0.1, 0.1], profiles)
        rd = compute_reaction_distribution([sim], BASELINE, WEIGHTS, min_segment_size=1)
        by_key = {(s.dimension, s.segment): s for s in rd.segments}
        tr = by_key[("country", "TR")]
        de = by_key[("country", "DE")]
        assert tr.shares.support == 1.0 and tr.shares.oppose == 0.0
        assert de.shares.oppose == 1.0 and de.shares.support == 0.0
        assert tr.mean_deviation > 0 > de.mean_deviation
        assert {"country", "region", "age_band", "gender"} <= {s.dimension for s in rd.segments}

    def test_min_segment_size_drops_small_segments(self):
        profiles = [make_profile(i, country="TR") for i in range(5)]
        profiles.append(make_profile(99, country="DE", region="europe_west"))
        sim = make_sim([0.9] * 6, profiles)
        rd = compute_reaction_distribution([sim], BASELINE, WEIGHTS, min_segment_size=5)
        countries = {s.segment for s in rd.segments if s.dimension == "country"}
        assert "DE" not in countries
        assert "TR" in countries

    def test_empty_sims_returns_neutral_distribution(self):
        rd = compute_reaction_distribution([], BASELINE, WEIGHTS)
        assert isinstance(rd, ReactionDistribution)
        assert rd.n_agents == 0
        assert rd.segments == ()
        assert (rd.stances.support, rd.stances.oppose, rd.stances.neutral) == (0.34, 0.33, 0.33)


class TestStanceShift:
    def test_elementwise_delta(self):
        shift = stance_shift(
            StanceShares(support=0.6, oppose=0.2, neutral=0.2),
            StanceShares(support=0.4, oppose=0.4, neutral=0.2),
        )
        assert abs(shift.support - 0.2) < 1e-9
        assert abs(shift.oppose + 0.2) < 1e-9
        assert abs(shift.neutral) < 1e-9
