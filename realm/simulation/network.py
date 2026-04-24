"""Hybrid social network topology (decision #4).

Base layer  : Watts–Strogatz small-world graph (high clustering, low diameter).
Scale-free  : top-degree hubs get extra Barabási-Albert–style edges.
Geography   : a target fraction of edges are forced to be cross-country.

Produces a networkx.Graph keyed by agent_id. Deterministic for a given RNG.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import networkx as nx

from realm.agents.interfaces import Agent
from realm.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class NetworkConfig:
    topology: str = "hybrid"          # "small_world" | "scale_free" | "hybrid"
    local_k: int = 10                 # Watts-Strogatz k
    rewire_p: float = 0.1             # Watts-Strogatz rewire probability
    hub_boost_factor: float = 2.5     # extra edges per hub = boost * local_k
    hub_ratio: float = 0.05           # fraction of agents designated as hubs
    cross_country_ratio: float = 0.05 # target fraction of cross-country edges

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> NetworkConfig:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class NetworkTopology:
    """Builds and exposes the social graph.

    Graph nodes are agent_ids (strings). Edges are undirected (friendship /
    follow-relation). Edge data: {"weight": float, "type": "local"|"hub"|"cross_country"}.
    """

    def __init__(self, agents: list[Agent], config: NetworkConfig | None = None) -> None:
        if not agents:
            raise ValueError("NetworkTopology needs at least 1 agent")
        self._agents: dict[str, Agent] = {a.agent_id: a for a in agents}
        self._agent_list: list[Agent] = list(agents)
        self._cfg = config or NetworkConfig()
        self._graph: nx.Graph | None = None

    @property
    def graph(self) -> nx.Graph:
        if self._graph is None:
            raise RuntimeError("Graph not built yet — call build(rng) first")
        return self._graph

    def build(self, rng: random.Random) -> nx.Graph:
        n = len(self._agent_list)
        k = min(self._cfg.local_k, n - 1)
        if k < 2:
            k = 2

        seed_int = rng.randint(0, 2**31 - 1)

        if self._cfg.topology == "small_world":
            g = nx.watts_strogatz_graph(n, k, self._cfg.rewire_p, seed=seed_int)
        elif self._cfg.topology == "scale_free":
            # Barabási-Albert: m = k/2 to match average degree roughly
            g = nx.barabasi_albert_graph(n, max(k // 2, 1), seed=seed_int)
        else:  # hybrid
            g = nx.watts_strogatz_graph(n, k, self._cfg.rewire_p, seed=seed_int)
            self._add_hub_edges(g, rng)

        # Relabel integer nodes to agent_ids
        mapping = {i: a.agent_id for i, a in enumerate(self._agent_list)}
        g = nx.relabel_nodes(g, mapping)

        # Annotate edges with type
        for u, v in g.edges():
            g.edges[u, v].setdefault("type", "local")
            g.edges[u, v].setdefault("weight", 1.0)

        # Enforce cross-country share
        self._rewire_cross_country(g, rng)

        self._graph = g
        logger.info(
            "Network built: %d nodes, %d edges, avg degree %.1f, "
            "cross-country fraction %.3f",
            g.number_of_nodes(), g.number_of_edges(),
            2 * g.number_of_edges() / max(g.number_of_nodes(), 1),
            self._cross_country_fraction(g),
        )
        return g

    # ---- helpers ---------------------------------------------------------

    def _select_hubs(self) -> list[str]:
        """Prefer 'influencer'-flagged agents; fill up to hub_ratio with top
        social_dominance agents."""
        target_count = max(1, int(len(self._agent_list) * self._cfg.hub_ratio))
        flagged = [a.agent_id for a in self._agent_list
                   if a.profile.marginal_category == "influencer"]
        if len(flagged) >= target_count:
            return flagged[:target_count]

        # Fill remainder from highest social_dominance
        sorted_agents = sorted(
            self._agent_list, key=lambda a: -a.traits.social_dominance,
        )
        extra = [a.agent_id for a in sorted_agents
                 if a.agent_id not in flagged]
        return flagged + extra[: target_count - len(flagged)]

    def _add_hub_edges(self, g: nx.Graph, rng: random.Random) -> None:
        """Give each hub extra random edges (scale-free tail on top of small-world)."""
        hubs = self._select_hubs()
        extra_per_hub = int(self._cfg.local_k * self._cfg.hub_boost_factor)
        n = len(self._agent_list)
        id_to_index = {a.agent_id: i for i, a in enumerate(self._agent_list)}

        for hub_id in hubs:
            hub_idx = id_to_index[hub_id]
            candidate_pool = [i for i in range(n) if i != hub_idx]
            extra = min(extra_per_hub, len(candidate_pool))
            # Weighted by degree already in graph (preferential attachment flavour)
            if g.number_of_edges() > 0:
                weights = [g.degree(i) + 1 for i in candidate_pool]
                picks = _weighted_sample_without_replacement(
                    candidate_pool, weights, extra, rng,
                )
            else:
                picks = rng.sample(candidate_pool, extra)
            for t in picks:
                if not g.has_edge(hub_idx, t):
                    g.add_edge(hub_idx, t, type="hub", weight=1.2)

    def _cross_country_fraction(self, g: nx.Graph) -> float:
        if g.number_of_edges() == 0:
            return 0.0
        cross = sum(
            1 for u, v in g.edges()
            if self._agents[u].profile.country != self._agents[v].profile.country
        )
        return cross / g.number_of_edges()

    def _rewire_cross_country(self, g: nx.Graph, rng: random.Random) -> None:
        target = self._cfg.cross_country_ratio
        current = self._cross_country_fraction(g)
        if current >= target:
            return

        need_cross = int((target - current) * g.number_of_edges())
        if need_cross <= 0:
            return

        same_country_edges = [
            (u, v) for u, v in g.edges()
            if self._agents[u].profile.country == self._agents[v].profile.country
        ]
        rng.shuffle(same_country_edges)

        all_ids = [a.agent_id for a in self._agent_list]
        rewired = 0
        for u, v in same_country_edges:
            if rewired >= need_cross:
                break
            country_u = self._agents[u].profile.country
            candidates = [
                aid for aid in all_ids
                if self._agents[aid].profile.country != country_u and aid != u
                and not g.has_edge(u, aid)
            ]
            if not candidates:
                continue
            new_target = rng.choice(candidates)
            g.remove_edge(u, v)
            g.add_edge(u, new_target, type="cross_country", weight=0.8)
            rewired += 1

    # ---- introspection ---------------------------------------------------

    def neighbors_of(self, agent_id: str) -> list[str]:
        return list(self.graph.neighbors(agent_id))

    def degree_of(self, agent_id: str) -> int:
        return int(self.graph.degree(agent_id))

    def top_hubs(self, n: int = 10) -> list[tuple[str, int]]:
        """Return the top-n nodes by degree."""
        degs = [(node, int(deg)) for node, deg in self.graph.degree()]
        degs.sort(key=lambda t: -t[1])
        return degs[:n]


def _weighted_sample_without_replacement(
    items: list[int],
    weights: list[float],
    k: int,
    rng: random.Random,
) -> list[int]:
    """Sample k distinct items with given weights. O(k·n)."""
    items = list(items)
    weights = list(weights)
    picks: list[int] = []
    for _ in range(min(k, len(items))):
        total = sum(weights)
        if total <= 0:
            break
        r = rng.uniform(0, total)
        cum = 0.0
        for i, w in enumerate(weights):
            cum += w
            if r <= cum:
                picks.append(items[i])
                items.pop(i)
                weights.pop(i)
                break
    return picks
