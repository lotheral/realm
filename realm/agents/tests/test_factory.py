"""Integration test for AgentFactory — composes all Phase 1+2 layers."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.agents.interfaces import Agent
from realm.demographics.world_generator import WorldGenerator


@pytest.fixture(scope="module")
def agents():
    gen = WorldGenerator(master_seed=42)
    factory = AgentFactory()
    profiles = gen.generate(30)
    return factory.build_batch(profiles)


class TestBatchBuild:
    def test_produces_agents(self, agents):
        assert len(agents) >= 25  # Some may fail if birth year < 1899

    def test_agent_type(self, agents):
        assert all(isinstance(a, Agent) for a in agents)

    def test_traits_in_unit_range(self, agents):
        for a in agents:
            for name, v in a.traits.to_dict().items():
                assert 0.0 <= v <= 1.0, f"{a.agent_id}.{name}={v}"

    def test_natal_chart_has_all_bodies(self, agents):
        from realm.core.types import PLANETS_ALL_PHASE1
        for a in agents[:5]:
            names = {p.name for p in a.natal_chart.planets}
            assert names == set(PLANETS_ALL_PHASE1)

    def test_determinism_across_runs(self):
        gen = WorldGenerator(master_seed=123)
        factory = AgentFactory()
        run1 = factory.build_batch(gen.generate(20))
        run2 = factory.build_batch(gen.generate(20))
        # Trait vectors should be bit-identical
        for a, b in zip(run1, run2, strict=True):
            assert a.traits == b.traits


class TestIndividualBuild:
    def test_build_single(self):
        gen = WorldGenerator(master_seed=42)
        factory = AgentFactory()
        profile = gen.generate(1)[0]
        agent = factory.build(profile)
        assert agent.agent_id == profile.agent_id
        assert agent.traits is not None
