"""build_branch_sim + PopulationSpec plumbing (Sprint 21)."""

from realm.demographics.population_spec import PopulationSpec
from realm.output.predictor import build_branch_sim


class TestBranchSimPopulation:
    def test_default_builder_honors_population_spec(self):
        spec = PopulationSpec(countries=("TR",), age_min=18, age_max=29)
        sim = build_branch_sim(42, 20, population_spec=spec)
        assert len(sim.agents) == 20
        assert all(a.profile.country == "TR" for a in sim.agents)
        assert all(18 <= a.profile.age_years <= 29 for a in sim.agents)

    def test_no_spec_matches_legacy_population(self):
        base = build_branch_sim(42, 15)
        specd = build_branch_sim(42, 15, population_spec=None)
        assert [a.profile for a in base.agents] == [a.profile for a in specd.agents]

    def test_custom_agent_builder_wins_over_spec(self):
        marker = build_branch_sim(42, 5).agents  # any legacy population

        def builder(seed: int, n: int) -> list:
            return list(marker[:n])

        sim = build_branch_sim(
            42, 5,
            agent_builder=builder,
            population_spec=PopulationSpec(countries=("TR",)),
        )
        assert sim.agents == list(marker[:5])
