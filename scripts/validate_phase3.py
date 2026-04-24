"""Phase 3 end-to-end validation.

Runs a full simulation: generate agents → build network → tick loop → print
stats on posts, engagements, hubs, and topic distributions. Demonstrates
checkpoint round-trip at the end.

Usage:
    python scripts/validate_phase3.py [N_AGENTS] [N_TICKS]
    Default: 500 agents, 30 ticks (~30 seconds on GMKtec).
"""

from __future__ import annotations

import contextlib
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env so KERYKEION_GEONAMES_USERNAME / LLM keys / model overrides are visible.
import contextlib as _ctx  # noqa: E402

with _ctx.suppress(ImportError):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import networkx as nx  # noqa: E402

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.simulation import checkpoint as ckpt  # noqa: E402
from realm.simulation.clock import Clock  # noqa: E402
from realm.simulation.engine import SimulationEngine  # noqa: E402
from realm.simulation.network import NetworkConfig, NetworkTopology  # noqa: E402
from realm.simulation.platforms.social_media import SocialMediaPlatform  # noqa: E402
from realm.simulation.transit_modulator import TransitModulator  # noqa: E402

logger = get_logger(__name__)


def bar(frac: float, width: int = 40) -> str:
    filled = int(round(frac * width))
    return "#" * filled + "." * (width - filled)


def print_network_stats(net: NetworkTopology) -> None:
    g = net.graph
    degs = [d for _, d in g.degree()]
    print("\n[ Network topology ]")
    print(f"  Nodes: {g.number_of_nodes()}   Edges: {g.number_of_edges()}")
    print(f"  Avg degree: {statistics.mean(degs):.1f}   Max: {max(degs)}   Min: {min(degs)}")
    print(f"  Clustering coefficient: {nx.average_clustering(g):.3f}")
    if nx.is_connected(g):
        print(f"  Avg shortest path: {nx.average_shortest_path_length(g):.2f}")
    else:
        ccs = list(nx.connected_components(g))
        print(f"  Disconnected ({len(ccs)} components, largest={len(max(ccs, key=len))})")

    # Degree distribution buckets
    buckets = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 50), (50, 9999)]
    print("\n[ Degree distribution ]")
    for lo, hi in buckets:
        c = sum(1 for d in degs if lo <= d < hi)
        print(f"  [{lo:2d}-{hi-1:2d}]  {c:4d}  {c*100/len(degs):4.1f}%  [{bar(c/len(degs), 30)}]")


def print_tick_timeline(sim: SimulationEngine) -> None:
    print("\n[ Tick-by-tick activity ]")
    print("  tick   posts   engagements   lurkers   top_topic")
    for s in sim.history:
        top_topic = max(s.posts_by_topic.items(), key=lambda kv: kv[1]) if s.posts_by_topic else ("—", 0)
        print(f"  {s.tick:4d}   {s.posts:5d}   {s.engagements:11d}   {s.lurkers:7d}   "
              f"{top_topic[0]:8s}({top_topic[1]})")


def print_aggregate(sim: SimulationEngine) -> None:
    agg = sim.aggregate_stats()
    print(f"\n[ Aggregate over {agg['ticks']} ticks ]")
    print(f"  Total posts:        {agg['posts']}")
    print(f"  Total engagements:  {agg['engagements']}")
    print(f"  Posts per tick:     {agg['posts_per_tick']:.1f}")
    print(f"  Engagements / tick: {agg['engagements_per_tick']:.1f}")
    print(f"  Engagement rate:    {agg['engagements']/max(agg['posts'],1):.2f}x per post")


def print_topic_distribution(sim: SimulationEngine) -> None:
    total = Counter()
    for s in sim.history:
        for topic, c in s.posts_by_topic.items():
            total[topic] += c
    grand = sum(total.values())
    if grand == 0:
        return
    print("\n[ Topic distribution across all posts ]")
    for topic, c in total.most_common():
        frac = c / grand
        print(f"  {topic:10s}  {c:5d}  {frac*100:5.1f}%  [{bar(frac, 30)}]")


def print_top_influencers(sim: SimulationEngine) -> None:
    platform = sim.platforms[0]
    # Count engagements received per author
    engagement_per_author: Counter[str] = Counter()
    post_count: Counter[str] = Counter()
    for post in platform.top_posts(10_000):
        engagement_per_author[post.author_id] += post.engagement
        post_count[post.author_id] += 1

    agents_by_id = {a.agent_id: a for a in sim.agents}
    print("\n[ Top 10 influencers (by engagements received) ]")
    for aid, eng in engagement_per_author.most_common(10):
        a = agents_by_id.get(aid)
        if a is None:
            continue
        marginal = a.profile.marginal_category or "ordinary"
        posts = post_count[aid]
        print(f"  {a.profile.name_first:>15s} {a.profile.name_last:<18s}  "
              f"posts={posts:2d}  engagements={eng:3d}  {marginal}")


def print_top_posts(sim: SimulationEngine) -> None:
    platform = sim.platforms[0]
    print("\n[ Top 5 posts by engagement ]")
    for p in platform.top_posts(5):
        author = next((a for a in sim.agents if a.agent_id == p.author_id), None)
        name = f"{author.profile.name_first} {author.profile.name_last}" if author else p.author_id
        print(f"  tick {p.tick:2d}  {p.topic:8s}  sent={p.sentiment:+.2f}  "
              f"virality={p.virality:.2f}  eng={p.engagement}  by {name}")


def demo_checkpoint_round_trip(
    master_seed: int, n_agents: int, n_ticks: int,
) -> None:
    print("\n[ Checkpoint round-trip ]")
    half = n_ticks // 2

    # Full run
    sim_a = _build_sim(master_seed, n_agents)
    sim_a.run(n_ticks)
    final_a = (
        sim_a.clock.tick,
        sim_a.aggregate_stats()["posts"],
        sim_a.aggregate_stats()["engagements"],
    )

    # Split run: half → checkpoint → rebuild → half
    sim_b = _build_sim(master_seed, n_agents)
    sim_b.run(half)
    with tempfile.TemporaryDirectory() as td:
        path = ckpt.save(sim_b, Path(td) / "ck.bin")
        sim_c = _build_sim(master_seed, n_agents)
        ckpt.restore_into(sim_c, ckpt.load(path))
        sim_c.run(n_ticks - half)
    final_c = (
        sim_c.clock.tick,
        sim_c.aggregate_stats()["posts"],
        sim_c.aggregate_stats()["engagements"],
    )

    print(f"  Full run:             tick={final_a[0]}, posts={final_a[1]}, engagements={final_a[2]}")
    print(f"  Checkpoint+resume:    tick={final_c[0]}, posts={final_c[1]}, engagements={final_c[2]}")
    print(f"  Equivalence check:    {'PASS' if final_a == final_c else 'FAIL'}")


def _build_sim(master_seed: int, n_agents: int) -> SimulationEngine:
    gen = WorldGenerator(master_seed=master_seed)
    factory = AgentFactory()
    agents = factory.build_batch(gen.generate(n_agents))
    clock = Clock.from_config()
    clock.master_seed = master_seed
    network = NetworkTopology(
        agents, NetworkConfig(local_k=10, rewire_p=0.1, hub_ratio=0.05,
                              cross_country_ratio=0.05),
    )
    network.build(clock.rng("network"))
    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    platform = SocialMediaPlatform(memory_ticks=5, virality_threshold=1.5)
    return SimulationEngine(agents, network, modulator, [platform], clock)


def main(argv: list[str]) -> int:
    setup_logging(level="INFO")

    n_agents = int(argv[1]) if len(argv) > 1 else 500
    n_ticks = int(argv[2]) if len(argv) > 2 else 30
    master_seed = 42

    logger.info("Building %d agents, running %d ticks…", n_agents, n_ticks)
    t0 = time.perf_counter()

    sim = _build_sim(master_seed, n_agents)
    build_elapsed = time.perf_counter() - t0
    print(f"\nBuilt {len(sim.agents)} agents in {build_elapsed:.1f}s")

    print_network_stats(sim.network)

    t1 = time.perf_counter()
    sim.run(n_ticks)
    run_elapsed = time.perf_counter() - t1
    print(f"\nRan {n_ticks} ticks in {run_elapsed:.1f}s "
          f"({run_elapsed*1000/n_ticks:.0f}ms/tick, "
          f"{run_elapsed*1000/(n_ticks*n_agents):.1f}ms/agent-tick)")

    print_tick_timeline(sim)
    print_aggregate(sim)
    print_topic_distribution(sim)
    print_top_influencers(sim)
    print_top_posts(sim)

    demo_checkpoint_round_trip(master_seed, n_agents, n_ticks)

    print(f"\n{'=' * 78}")
    print(f"  Phase 3 validation complete — {n_agents} agents, {n_ticks} ticks.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
