"""Tests for NetworkTopology."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import networkx as nx
import pytest

from realm.agents.interfaces import Agent
from realm.astro.fixtures import synthetic_chart
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector
from realm.simulation.network import NetworkConfig, NetworkTopology


def _mk_agent(idx: int, country: str = "US", influencer: bool = False,
              dom: float = 0.5) -> Agent:
    p = DemographicProfile(
        agent_id=f"AGT_{idx:04d}",
        name_first="A", name_last=str(idx), gender="M",
        country=country, city=f"{country}City",
        birth_datetime=datetime(1990, 1, 1, tzinfo=UTC),
        birth_latitude=0.0, birth_longitude=0.0, birth_timezone="UTC",
        age_years=30,
        profession_code="professionals", profession_name="Professional",
        income_annual_usd=30000, education_level="bachelor",
        marginal_flag=influencer,
        marginal_category="influencer" if influencer else None,
        primary_religion="christian", region="america_north",
    )
    return Agent(profile=p, natal_chart=synthetic_chart(),
                 traits=TraitVector(social_dominance=dom))


def _agents(n: int, countries: list[str] | None = None) -> list[Agent]:
    cs = countries or ["US", "CN", "IN", "DE", "TR"]
    return [_mk_agent(i, cs[i % len(cs)]) for i in range(n)]


class TestBasicBuild:
    def test_rejects_empty_agents(self):
        with pytest.raises(ValueError):
            NetworkTopology([])

    def test_graph_not_built_until_build_called(self):
        nt = NetworkTopology(_agents(20))
        with pytest.raises(RuntimeError):
            _ = nt.graph

    def test_build_returns_graph_with_all_agents(self):
        agents = _agents(50)
        nt = NetworkTopology(agents)
        g = nt.build(random.Random(0))
        assert g.number_of_nodes() == 50

    def test_nodes_are_agent_ids(self):
        agents = _agents(30)
        nt = NetworkTopology(agents)
        g = nt.build(random.Random(0))
        assert {a.agent_id for a in agents} == set(g.nodes())

    def test_has_edges(self):
        agents = _agents(50)
        nt = NetworkTopology(agents, NetworkConfig(local_k=6, rewire_p=0.1))
        g = nt.build(random.Random(0))
        assert g.number_of_edges() > 0


class TestSmallWorldProperty:
    def test_clustering_higher_than_random(self):
        """Watts-Strogatz should give high local clustering."""
        agents = _agents(100)
        nt = NetworkTopology(agents, NetworkConfig(local_k=8, rewire_p=0.1))
        g = nt.build(random.Random(0))

        ws_clustering = nx.average_clustering(g)
        # Random graph of same density has clustering ≈ p = avg_deg/n
        avg_deg = 2 * g.number_of_edges() / g.number_of_nodes()
        random_expected = avg_deg / g.number_of_nodes()

        assert ws_clustering > random_expected * 3, (
            f"clustering={ws_clustering:.3f} vs random baseline={random_expected:.3f}"
        )


class TestHybridHubs:
    def test_hubs_have_higher_degree(self):
        """Hub agents should end up with more edges than average."""
        # Build with 5 influencers out of 100
        agents = []
        for i in range(100):
            agents.append(_mk_agent(i, influencer=(i < 5)))
        nt = NetworkTopology(
            agents,
            NetworkConfig(local_k=8, rewire_p=0.1, hub_boost_factor=3.0, hub_ratio=0.05),
        )
        g = nt.build(random.Random(0))

        hub_ids = [a.agent_id for a in agents if a.profile.marginal_category == "influencer"]
        hub_degree = sum(g.degree(h) for h in hub_ids) / len(hub_ids)
        all_degree = 2 * g.number_of_edges() / g.number_of_nodes()

        assert hub_degree > all_degree * 1.5, (
            f"hub avg degree={hub_degree:.1f} vs overall={all_degree:.1f}"
        )


class TestCrossCountry:
    def test_cross_country_ratio_near_target(self):
        countries = ["US", "CN", "IN", "DE", "TR", "BR", "NG"]
        agents = [_mk_agent(i, countries[i % len(countries)]) for i in range(150)]
        nt = NetworkTopology(
            agents,
            NetworkConfig(local_k=8, rewire_p=0.1, cross_country_ratio=0.10),
        )
        g = nt.build(random.Random(0))

        cross = sum(
            1 for u, v in g.edges()
            if nt._agents[u].profile.country != nt._agents[v].profile.country
        )
        ratio = cross / g.number_of_edges()
        # Small-world ring structure pushes country clustering, so the WS base
        # naturally has some cross-country edges; final ratio should be ≥ target.
        assert ratio >= 0.08, f"cross-country ratio={ratio:.3f} below target 0.10"


class TestDeterminism:
    def test_same_rng_same_graph(self):
        agents = _agents(50)
        g1 = NetworkTopology(agents).build(random.Random(42))
        g2 = NetworkTopology(agents).build(random.Random(42))
        assert set(g1.edges()) == set(g2.edges())

    def test_different_rng_different_graph(self):
        agents = _agents(80)
        g1 = NetworkTopology(agents).build(random.Random(1))
        g2 = NetworkTopology(agents).build(random.Random(2))
        assert set(g1.edges()) != set(g2.edges())


class TestIntrospection:
    def test_neighbors_and_degree(self):
        agents = _agents(40)
        nt = NetworkTopology(agents)
        nt.build(random.Random(0))
        aid = agents[0].agent_id
        nbrs = nt.neighbors_of(aid)
        assert isinstance(nbrs, list)
        assert nt.degree_of(aid) == len(nbrs)

    def test_top_hubs(self):
        agents = [_mk_agent(i, influencer=(i < 3)) for i in range(60)]
        nt = NetworkTopology(
            agents,
            NetworkConfig(hub_boost_factor=4.0, hub_ratio=0.05),
        )
        nt.build(random.Random(0))
        hubs = nt.top_hubs(5)
        assert len(hubs) == 5
        # Top of list should include at least one flagged influencer
        hub_ids = {h[0] for h in hubs}
        flagged_ids = {a.agent_id for a in agents if a.profile.marginal_category == "influencer"}
        assert hub_ids & flagged_ids
