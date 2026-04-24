"""Integration tests for SimulationEngine — end-to-end tick loop."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


@pytest.fixture(scope="module")
def engine_setup():
    gen = WorldGenerator(master_seed=42)
    factory = AgentFactory()
    agents = factory.build_batch(gen.generate(40))

    clock = Clock.from_config()
    network = NetworkTopology(
        agents, NetworkConfig(local_k=6, rewire_p=0.1, hub_ratio=0.1),
    )
    network.build(clock.rng("network"))

    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    platform = SocialMediaPlatform(memory_ticks=3)

    sim = SimulationEngine(
        agents=agents,
        network=network,
        modulator=modulator,
        platforms=[platform],
        clock=clock,
    )
    return sim, platform


class TestSingleTick:
    def test_tick_runs_without_error(self, engine_setup):
        sim, _ = engine_setup
        # Reset to tick 0 for a clean run
        sim.clock.tick = 0
        sim.history.clear()
        stats = sim.tick()
        assert stats.tick == 0

    def test_action_counts_sum_to_total_agents(self, engine_setup):
        sim, _ = engine_setup
        sim.clock.tick = 0
        sim.history.clear()
        stats = sim.tick()
        total = sum(stats.actions_by_type.values())
        assert total == len(sim.agents)


class TestMultiTick:
    def test_run_five_ticks(self, engine_setup):
        sim, platform = engine_setup
        sim.clock.tick = 0
        sim.history.clear()
        sim.run(5)
        assert len(sim.history) == 5
        agg = sim.aggregate_stats()
        assert agg["ticks"] == 5
        # With 40 agents × 5 ticks, expect at least some posts
        assert agg["posts"] > 0

    def test_engagement_affects_feed(self, engine_setup):
        sim, platform = engine_setup
        sim.clock.tick = 0
        sim.history.clear()
        sim.run(5)
        # Some posts should have received engagement
        engaged_posts = [p for p in platform.top_posts(20) if p.engagement > 0]
        # Not a hard guarantee with 40 agents × 5 ticks but usually holds
        assert len(engaged_posts) > 0


class TestDeterminism:
    def test_same_seed_same_stats(self):
        def run():
            gen = WorldGenerator(master_seed=123)
            factory = AgentFactory()
            agents = factory.build_batch(gen.generate(30))
            clock = Clock(
                epoch=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc),
                interval=__import__("datetime").timedelta(days=1),
                master_seed=123,
            )
            net = NetworkTopology(agents, NetworkConfig(local_k=6))
            net.build(clock.rng("network"))
            mod = TransitModulator.from_config(get_astro_engine("auto"))
            plat = SocialMediaPlatform()
            sim = SimulationEngine(agents, net, mod, [plat], clock)
            sim.run(3)
            return [(s.tick, s.posts, s.engagements, s.lurkers) for s in sim.history]

        assert run() == run()


class TestActionsRespectProbabilities:
    def test_post_and_engage_bounded(self, engine_setup):
        sim, _ = engine_setup
        sim.clock.tick = 0
        sim.history.clear()
        sim.run(10)
        # Over 10 ticks with 40 agents, lurking should dominate (p_post < 0.35 per tick)
        total_agents_ticks = 40 * 10
        total_posts = sum(s.posts for s in sim.history)
        total_engagements = sum(s.engagements for s in sim.history)
        assert total_posts < total_agents_ticks * 0.4
        assert total_engagements < total_agents_ticks * 0.5
