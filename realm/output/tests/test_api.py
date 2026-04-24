"""Tests for FastAPI endpoints using httpx.TestClient."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from fastapi.testclient import TestClient

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.output.api import create_app
from realm.output.dashboard_service import DashboardService
from realm.simulation.climate import ClimateEngine
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


@pytest.fixture(scope="module")
def client():
    agents = AgentFactory().build_batch(
        WorldGenerator(master_seed=42).generate(25)
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
    sim.run(2)
    svc = DashboardService(sim=sim, network=net, climate=climate, knowledge_graph=KnowledgeGraph())
    app = create_app(svc)
    return TestClient(app)


class TestEndpoints:
    def test_index_serves_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "REALM" in r.text

    def test_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["n_agents"] == 25
        assert "master_seed" in data

    def test_timeline(self, client):
        r = client.get("/api/timeline")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_agents_list(self, client):
        r = client.get("/api/agents?limit=5")
        assert r.status_code == 200
        a = r.json()
        assert 0 < len(a) <= 5

    def test_agent_detail(self, client):
        listing = client.get("/api/agents?limit=1").json()
        aid = listing[0]["agent_id"]
        r = client.get(f"/api/agents/{aid}")
        assert r.status_code == 200
        assert r.json()["agent_id"] == aid

    def test_agent_not_found(self, client):
        r = client.get("/api/agents/bogus")
        assert r.status_code == 404

    def test_network(self, client):
        r = client.get("/api/network")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data and "edges" in data

    def test_network_sample(self, client):
        r = client.get("/api/network?sample=15")
        assert r.status_code == 200

    def test_climate(self, client):
        r = client.get("/api/climate")
        assert r.status_code == 200
        assert r.json()["enabled"]

    def test_kg(self, client):
        r = client.get("/api/kg?top_n=5")
        assert r.status_code == 200

    def test_mood(self, client):
        r = client.get("/api/mood")
        assert r.status_code == 200
        assert "trait_means" in r.json()

    def test_top_posts(self, client):
        r = client.get("/api/top_posts?n=5")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestPredictEndpoint:
    def test_predict_runs(self, client):
        r = client.post("/api/predict", json={
            "question": "Will mean empathy rise above 0.6?",
            "n_agents": 40,
            "horizon_ticks": 3,
            "n_branches": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert 0.0 <= data["probability"] <= 1.0
        assert 0.0 <= data["confidence"] <= 1.0
        assert len(data["branch_values"]) == 2


class TestPredictScenarioEndpoint:
    def test_scenario_runs_with_events(self, client):
        r = client.post("/api/predict_scenario", json={
            "question": "Will tech dominate the topic mix?",
            "events": [
                {"headline": "Apple launches AI device", "topic": "tech",
                 "sentiment": 0.8, "virality": 4.0},
                {"headline": "OpenAI responds with new chip", "topic": "tech",
                 "sentiment": 0.7, "virality": 3.5},
            ],
            "n_agents": 40,
            "horizon_ticks": 4,
            "n_branches": 2,
        })
        assert r.status_code == 200
        data = r.json()
        # Envelope structure
        assert {"baseline", "scenario", "delta_mean", "delta_per_branch",
                "verdict", "verdict_text"} <= set(data.keys())
        assert len(data["baseline"]["branch_values"]) == 2
        assert len(data["scenario"]["branch_values"]) == 2
        assert len(data["delta_per_branch"]) == 2
        assert data["verdict"] in {"strong_lift", "lift", "counter", "neutral"}

    def test_empty_events_equivalent_to_baseline(self, client):
        """With zero scenario events the delta should be exactly zero."""
        r = client.post("/api/predict_scenario", json={
            "question": "Will tech dominate the topic mix?",
            "events": [],
            "n_agents": 40,
            "horizon_ticks": 3,
            "n_branches": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert abs(data["delta_mean"]) < 1e-9
        assert data["verdict"] == "neutral"
