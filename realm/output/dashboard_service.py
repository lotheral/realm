"""DashboardService — composes snapshots from every subsystem for the UI.

This is the single source of truth for /api/* endpoints. Keep pure — no web
framework imports here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from realm.agents.interfaces import Agent
from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.personality.trait_vector import TraitVector, mean_trait_vector
from realm.simulation.climate import ClimateEngine
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkTopology
from realm.simulation.platforms.base import Post
from realm.simulation.platforms.social_media import SocialMediaPlatform


@dataclass
class DashboardService:
    sim: SimulationEngine
    network: NetworkTopology
    climate: ClimateEngine | None = None
    knowledge_graph: KnowledgeGraph | None = None

    # ---- Stats ----------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        agg = self.sim.aggregate_stats()
        social = next(
            (p for p in self.sim.platforms if isinstance(p, SocialMediaPlatform)), None,
        )
        return {
            "current_tick": self.sim.clock.tick,
            "sim_time": self.sim.clock.sim_time.isoformat(),
            "n_agents": len(self.sim.agents),
            "n_platforms": len(self.sim.platforms),
            "total_posts": agg.get("posts", 0),
            "total_engagements": agg.get("engagements", 0),
            "posts_per_tick": round(agg.get("posts_per_tick", 0.0), 2),
            "engagements_per_tick": round(agg.get("engagements_per_tick", 0.0), 2),
            "social_platform_live_posts": social.total_posts() if social else 0,
            "master_seed": self.sim.clock.master_seed,
        }

    # ---- Timeline -------------------------------------------------------

    def timeline(self) -> list[dict[str, Any]]:
        return [
            {
                "tick": s.tick,
                "posts": s.posts,
                "engagements": s.engagements,
                "lurkers": s.lurkers,
                "posts_by_topic": dict(s.posts_by_topic),
                "actions_by_type": dict(s.actions_by_type),
            }
            for s in self.sim.history
        ]

    # ---- Agents ---------------------------------------------------------

    def agents_summary(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        subset = self.sim.agents[offset: offset + limit]
        return [self._agent_brief(a) for a in subset]

    def agent_detail(self, agent_id: str) -> dict[str, Any] | None:
        agent = next((a for a in self.sim.agents if a.agent_id == agent_id), None)
        if agent is None:
            return None
        # Natal chart may be None if the agent was built via a non-astrological
        # InputAdapter (BigFive/Demographic). Emit a null chart field in that case.
        if agent.natal_chart is None:
            natal_chart_payload: dict[str, Any] | None = None
        else:
            sun = agent.natal_chart.planet("Sun")
            moon = agent.natal_chart.planet("Moon")
            natal_chart_payload = {
                "sun": _planet_to_dict(sun) if sun else None,
                "moon": _planet_to_dict(moon) if moon else None,
                "ascendant": round(agent.natal_chart.ascendant, 2),
                "midheaven": round(agent.natal_chart.midheaven, 2),
                "element_balance": {
                    k: round(v, 3) for k, v in agent.natal_chart.element_balance.items()
                },
            }
        return {
            **self._agent_brief(agent),
            "traits": {k: round(v, 3) for k, v in agent.traits.to_dict().items()},
            "natal_chart": natal_chart_payload,
            "network": {
                "degree": self.network.degree_of(agent.agent_id),
                "neighbors": self.network.neighbors_of(agent.agent_id)[:20],
            },
        }

    def _agent_brief(self, agent: Agent) -> dict[str, Any]:
        p = agent.profile
        top_trait = max(
            agent.traits.to_dict().items(),
            key=lambda kv: abs(kv[1] - 0.5),
        )
        return {
            "agent_id": p.agent_id,
            "name": f"{p.name_first} {p.name_last}",
            "country": p.country,
            "city": p.city,
            "age": p.age_years,
            "gender": p.gender,
            "profession": p.profession_code,
            "marginal": p.marginal_category,
            "top_trait": top_trait[0],
            "top_trait_value": round(top_trait[1], 3),
        }

    # ---- Network --------------------------------------------------------

    def network_snapshot(self, sample_size: int | None = None) -> dict[str, Any]:
        """Return nodes + edges as JSON. If sample_size given, pick a subgraph
        around the top-degree nodes (useful when the full network is too big
        to render in the browser)."""
        g = self.network.graph
        if sample_size and g.number_of_nodes() > sample_size:
            hub_ids = [aid for aid, _ in self.network.top_hubs(n=sample_size // 4)]
            include = set(hub_ids)
            # Expand with one-hop neighbors until we hit the budget
            for h in hub_ids:
                for nb in g.neighbors(h):
                    if len(include) >= sample_size:
                        break
                    include.add(nb)
            sub = g.subgraph(include)
        else:
            sub = g

        agents_by_id = {a.agent_id: a for a in self.sim.agents}
        nodes = []
        for node_id in sub.nodes():
            agent = agents_by_id.get(node_id)
            nodes.append({
                "id": node_id,
                "country": agent.profile.country if agent else "?",
                "profession": agent.profile.profession_code if agent else "?",
                "marginal": agent.profile.marginal_category if agent else None,
                "degree": int(sub.degree(node_id)),
                "traits_top": _top_trait_tag(agent.traits) if agent else None,
            })
        edges = [
            {
                "source": u, "target": v,
                "type": data.get("type", "local"),
                "weight": round(float(data.get("weight", 1.0)), 3),
            }
            for u, v, data in sub.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    # ---- Climate --------------------------------------------------------

    def climate_snapshot(self) -> dict[str, Any]:
        if self.climate is None:
            return {"enabled": False}
        snap = self.climate.describe(self.sim.clock.sim_time)
        mods = self.climate.compute(self.sim.clock.sim_time)
        top = sorted(mods.items(), key=lambda kv: -abs(kv[1]))[:8]
        return {
            "enabled": True,
            "outer_planets": {
                name: {"sign": sign, "retrograde": direction == "R"}
                for name, (sign, direction) in snap["outer_planets"].items()
            },
            "moon_phase": snap["moon_phase"],
            "retrograde_bodies": list(snap["retrograde"]),
            "eclipse": snap["eclipse"],
            "top_modifiers": [
                {"trait": n, "delta": round(d, 4)} for n, d in top
            ],
        }

    # ---- Knowledge graph -----------------------------------------------

    def kg_snapshot(self, top_n: int = 20) -> dict[str, Any]:
        if self.knowledge_graph is None:
            return {"enabled": False, "nodes": 0, "edges": 0}
        nodes, edges = self.knowledge_graph.size()
        return {
            "enabled": True,
            "nodes": nodes,
            "edges": edges,
            "hot_entities": [
                {
                    "name": name,
                    "mentions": count,
                    "sentiment": round(self.knowledge_graph.sentiment_of(name), 3),
                }
                for name, count in self.knowledge_graph.hot_entities(top_n)
            ],
        }

    # ---- Mood --------------------------------------------------------

    def mood(self) -> dict[str, Any]:
        """Aggregate current mood: mean trait vector + dominant signal."""
        mean = mean_trait_vector([a.traits for a in self.sim.agents])
        d = mean.to_dict()
        # Top positive and negative deviations from neutral
        ranked = sorted(d.items(), key=lambda kv: kv[1] - 0.5)
        return {
            "trait_means": {k: round(v, 4) for k, v in d.items()},
            "strongest_up": [{"trait": n, "value": round(v, 3)} for n, v in ranked[-5:][::-1]],
            "strongest_down": [{"trait": n, "value": round(v, 3)} for n, v in ranked[:5]],
        }

    # ---- Top posts --------------------------------------------------

    def top_posts(self, n: int = 10) -> list[dict[str, Any]]:
        results: list[Post] = []
        for plat in self.sim.platforms:
            if hasattr(plat, "top_posts"):
                results.extend(plat.top_posts(n))
        results.sort(key=lambda p: -p.engagement)
        return [_post_to_dict(p) for p in results[:n]]


# ---- helpers -------------------------------------------------------------

def _planet_to_dict(p) -> dict[str, Any]:
    return {
        "sign": p.sign,
        "sign_degree": round(p.sign_degree, 2),
        "house": p.house,
        "retrograde": p.is_retrograde,
    }


def _top_trait_tag(traits: TraitVector) -> str:
    d = traits.to_dict()
    top = max(d.items(), key=lambda kv: abs(kv[1] - 0.5))
    return top[0]


def _post_to_dict(p: Post) -> dict[str, Any]:
    return {
        "post_id": p.post_id,
        "author_id": p.author_id,
        "tick": p.tick,
        "topic": p.topic,
        "sentiment": round(p.sentiment, 3),
        "virality": round(p.virality, 3),
        "engagement": p.engagement,
    }
