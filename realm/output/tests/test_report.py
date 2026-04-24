"""Tests for the markdown report generator."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.output.report_generator import generate_report
from realm.simulation.climate import ClimateEngine
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


@pytest.fixture(scope="module")
def sim_triple():
    agents = AgentFactory().build_batch(
        WorldGenerator(master_seed=42).generate(20)
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
    return sim, net, climate


class TestReport:
    def test_generates_markdown(self, sim_triple):
        sim, net, climate = sim_triple
        md = generate_report(sim, network=net, climate=climate, kg=KnowledgeGraph())
        assert md.startswith("# ")
        assert "## Setup" in md
        assert "## Aggregate activity" in md
        assert "## Trait mean snapshot" in md
        assert "## Network topology" in md

    def test_includes_climate_section(self, sim_triple):
        sim, net, climate = sim_triple
        md = generate_report(sim, network=net, climate=climate)
        assert "## Astrological climate" in md
        assert "Moon phase" in md

    def test_without_optional_sections(self, sim_triple):
        sim, _, _ = sim_triple
        md = generate_report(sim)   # no network, no climate, no kg
        assert md.startswith("# ")
        assert "## Setup" in md
        assert "## Astrological climate" not in md
