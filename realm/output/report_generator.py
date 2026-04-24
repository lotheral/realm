"""Markdown report generator.

Given a completed SimulationEngine (+ optional climate/KG), produce a
structured markdown report suitable for sharing or archiving.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.personality.trait_vector import mean_trait_vector
from realm.simulation.climate import ClimateEngine
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkTopology


def _bar(frac: float, width: int = 30) -> str:
    filled = int(round(frac * width))
    return "█" * filled + "·" * (width - filled)


def generate_report(
    sim: SimulationEngine,
    network: NetworkTopology | None = None,
    climate: ClimateEngine | None = None,
    kg: KnowledgeGraph | None = None,
    title: str = "REALM simulation report",
) -> str:
    lines: list[str] = []

    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"*Generated: {datetime.now(UTC).isoformat()}*")
    lines.append("")

    # ---- Setup ----
    lines.append("## Setup")
    lines.append("")
    lines.append(f"- Master seed: `{sim.clock.master_seed}`")
    lines.append(f"- Agents: **{len(sim.agents)}**")
    lines.append(f"- Ticks run: **{sim.clock.tick}**")
    lines.append(f"- Epoch: `{sim.clock.epoch.isoformat()}`")
    lines.append(f"- Tick interval: `{sim.clock.interval}`")
    lines.append("")

    # ---- Aggregates ----
    agg = sim.aggregate_stats()
    lines.append("## Aggregate activity")
    lines.append("")
    lines.append(f"- Total posts: **{agg.get('posts', 0)}**")
    lines.append(f"- Total engagements: **{agg.get('engagements', 0)}**")
    lines.append(f"- Posts per tick: **{agg.get('posts_per_tick', 0):.2f}**")
    lines.append(f"- Engagements per tick: **{agg.get('engagements_per_tick', 0):.2f}**")
    if agg.get("posts", 0):
        er = agg.get("engagements", 0) / agg["posts"]
        lines.append(f"- Engagement rate: **{er:.2f} engagements per post**")
    lines.append("")

    # ---- Topic distribution ----
    topic_totals: Counter[str] = Counter()
    for s in sim.history:
        for t, c in s.posts_by_topic.items():
            topic_totals[t] += c
    total_posts = sum(topic_totals.values())
    if total_posts:
        lines.append("## Topic distribution")
        lines.append("")
        lines.append("| Topic | Count | Share |")
        lines.append("| --- | ---: | ---: |")
        for topic, c in topic_totals.most_common():
            lines.append(f"| `{topic}` | {c} | {c/total_posts:.1%} |")
        lines.append("")

    # ---- Trait snapshot ----
    mean = mean_trait_vector([a.traits for a in sim.agents])
    d = mean.to_dict()
    ranked = sorted(d.items(), key=lambda kv: kv[1] - 0.5)
    lines.append("## Trait mean snapshot")
    lines.append("")
    lines.append("Top upward:")
    for n, v in ranked[-5:][::-1]:
        lines.append(f"- **{n}** — {v:.3f}  (Δ {v-0.5:+.3f})")
    lines.append("")
    lines.append("Top downward:")
    for n, v in ranked[:5]:
        lines.append(f"- **{n}** — {v:.3f}  (Δ {v-0.5:+.3f})")
    lines.append("")

    # ---- Top influencers ----
    engagement_per_author: Counter[str] = Counter()
    post_count: Counter[str] = Counter()
    for plat in sim.platforms:
        if hasattr(plat, "top_posts"):
            for post in plat.top_posts(10_000):
                engagement_per_author[post.author_id] += post.engagement
                post_count[post.author_id] += 1
    agents_by_id = {a.agent_id: a for a in sim.agents}
    top_inf = [
        (aid, eng) for aid, eng in engagement_per_author.most_common(10)
        if aid in agents_by_id
    ][:10]
    if top_inf:
        lines.append("## Top influencers")
        lines.append("")
        lines.append("| Rank | Name | City / Country | Posts | Engagements | Profile |")
        lines.append("| ---: | --- | --- | ---: | ---: | --- |")
        for i, (aid, eng) in enumerate(top_inf, start=1):
            a = agents_by_id[aid]
            name = f"{a.profile.name_first} {a.profile.name_last}"
            loc = f"{a.profile.city} / {a.profile.country}"
            marginal = a.profile.marginal_category or "ordinary"
            lines.append(
                f"| {i} | {name} | {loc} | {post_count[aid]} | {eng} | {marginal} |"
            )
        lines.append("")

    # ---- Climate ----
    if climate is not None:
        snap = climate.describe(sim.clock.sim_time)
        mods = climate.compute(sim.clock.sim_time)
        lines.append("## Astrological climate (current)")
        lines.append("")
        lines.append("Outer planets:")
        for name, (sign, direction) in snap["outer_planets"].items():
            lines.append(f"- **{name}**: {sign} {'(R)' if direction == 'R' else ''}")
        lines.append("")
        lines.append(f"Moon phase: **{snap['moon_phase']}**  "
                     f"Eclipse: **{snap['eclipse'] or 'none'}**")
        if snap["retrograde"]:
            lines.append(f"Retrograde: {', '.join(snap['retrograde'])}")
        lines.append("")
        if mods:
            lines.append("Top climate modifiers:")
            for trait, delta in sorted(mods.items(), key=lambda kv: -abs(kv[1]))[:5]:
                arrow = "↑" if delta > 0 else "↓"
                lines.append(f"- **{trait}** {delta:+.4f} {arrow}")
            lines.append("")

    # ---- KG hot entities ----
    if kg is not None:
        nodes, edges = kg.size()
        lines.append("## Knowledge graph")
        lines.append("")
        lines.append(f"- Nodes: {nodes}")
        lines.append(f"- Edges: {edges}")
        lines.append("")
        hot = kg.hot_entities(10)
        if hot:
            lines.append("Top entities:")
            for name, count in hot:
                sent = kg.sentiment_of(name)
                lines.append(f"- **{name}** — mentions: {count}, sentiment: {sent:+.2f}")
            lines.append("")

    # ---- Network structure ----
    if network is not None:
        g = network.graph
        import networkx as nx
        lines.append("## Network topology")
        lines.append("")
        lines.append(f"- Nodes: {g.number_of_nodes()}")
        lines.append(f"- Edges: {g.number_of_edges()}")
        avg_deg = 2 * g.number_of_edges() / max(g.number_of_nodes(), 1)
        lines.append(f"- Average degree: {avg_deg:.1f}")
        lines.append(f"- Clustering coefficient: {nx.average_clustering(g):.3f}")
        lines.append("")
        lines.append("Top hubs:")
        for aid, deg in network.top_hubs(5):
            a = agents_by_id.get(aid)
            name = f"{a.profile.name_first} {a.profile.name_last}" if a else aid
            lines.append(f"- **{name}** — degree {deg}")
        lines.append("")

    lines.append("---")
    lines.append("*End of report.*")
    return "\n".join(lines)
