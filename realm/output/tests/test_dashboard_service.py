"""Tests for DashboardService — snapshot shapes, no web framework."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.output.dashboard_service import DashboardService
from realm.simulation.climate import ClimateEngine
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


@pytest.fixture(scope="module")
def service():
    agents = AgentFactory().build_batch(
        WorldGenerator(master_seed=42).generate(30)
    )
    clock = Clock.from_config()
    net = NetworkTopology(agents, NetworkConfig(local_k=4))
    net.build(clock.rng("network"))
    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    climate = ClimateEngine(modulator)
    sim = SimulationEngine(
        agents=agents, network=net, modulator=modulator,
        platforms=[SocialMediaPlatform()], clock=clock, climate=climate,
    )
    sim.run(3)
    kg = KnowledgeGraph()
    return DashboardService(sim=sim, network=net, climate=climate, knowledge_graph=kg)


class TestStats:
    def test_shape(self, service):
        s = service.stats()
        for key in ("current_tick", "sim_time", "n_agents",
                    "total_posts", "total_engagements", "master_seed"):
            assert key in s

    def test_values(self, service):
        s = service.stats()
        assert s["n_agents"] == 30
        assert s["current_tick"] == 3


class TestTimeline:
    def test_returns_history_per_tick(self, service):
        tl = service.timeline()
        assert len(tl) == 3
        for e in tl:
            assert "tick" in e
            assert "posts" in e


class TestAgents:
    def test_agents_summary(self, service):
        a = service.agents_summary(limit=10)
        assert len(a) <= 10
        for brief in a:
            assert {"agent_id", "name", "country", "top_trait"} <= set(brief.keys())

    def test_agent_detail(self, service):
        first = service.agents_summary(limit=1)[0]
        detail = service.agent_detail(first["agent_id"])
        assert detail is not None
        assert "traits" in detail
        assert "natal_chart" in detail
        assert detail["network"]["degree"] >= 0

    def test_unknown_agent_returns_none(self, service):
        assert service.agent_detail("bogus") is None


class TestNetworkSnapshot:
    def test_returns_nodes_and_edges(self, service):
        snap = service.network_snapshot()
        assert "nodes" in snap
        assert "edges" in snap
        assert len(snap["nodes"]) == 30

    def test_sample_truncates(self, service):
        small = service.network_snapshot(sample_size=10)
        assert len(small["nodes"]) <= 15  # with hub expansion


class TestClimateSnapshot:
    def test_climate_enabled(self, service):
        c = service.climate_snapshot()
        assert c["enabled"]
        assert "outer_planets" in c
        assert c["moon_phase"] in {"new", "waxing", "full", "waning"}


class TestKGSnapshot:
    def test_empty_graph(self, service):
        k = service.kg_snapshot()
        assert k["enabled"]
        assert k["nodes"] == 0


class TestMoodAndPosts:
    def test_mood_shape(self, service):
        m = service.mood()
        assert "trait_means" in m
        assert "strongest_up" in m and len(m["strongest_up"]) == 5
        assert "strongest_down" in m and len(m["strongest_down"]) == 5

    def test_top_posts(self, service):
        p = service.top_posts(n=5)
        assert len(p) <= 5
        for post in p:
            for key in ("post_id", "author_id", "topic", "sentiment", "engagement"):
                assert key in post
