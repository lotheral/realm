"""Phase 4 end-to-end validation — news injection into the simulation.

Loads a sample news feed (data/sample_news.json), runs a simulation that pulls
new events at each tick, and shows:
  - news injection counts
  - topic distribution shift compared to Phase 3 baseline
  - knowledge graph top entities
  - engagement funnel (news posts → agent engagements)
  - sample agents whose mood was pushed by news

Usage:
    python scripts/validate_phase4.py [N_AGENTS] [N_TICKS]
    Default: 300 agents, 12 ticks.
"""

from __future__ import annotations

import contextlib
import statistics
import sys
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

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.core.config import DATA_DIR  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.ingestion.entity_extractor import EnrichingProcessor  # noqa: E402
from realm.ingestion.knowledge_graph import KnowledgeGraph  # noqa: E402
from realm.ingestion.manager import IngestionManager  # noqa: E402
from realm.ingestion.sources.manual_upload import ManualUploadSource  # noqa: E402
from realm.simulation.clock import Clock  # noqa: E402
from realm.simulation.engine import SimulationEngine  # noqa: E402
from realm.simulation.network import NetworkConfig, NetworkTopology  # noqa: E402
from realm.simulation.platforms.news_channel import NewsChannelPlatform  # noqa: E402
from realm.simulation.platforms.social_media import SocialMediaPlatform  # noqa: E402
from realm.simulation.transit_modulator import TransitModulator  # noqa: E402

logger = get_logger(__name__)


def bar(frac: float, width: int = 30) -> str:
    filled = int(round(frac * width))
    return "#" * filled + "." * (width - filled)


def split_news_across_ticks(
    source: ManualUploadSource, all_events: list, n_ticks: int,
):
    """Return a pre_tick_hook that drip-feeds events from `all_events` so the
    simulation receives news throughout the run, not all at tick 0."""
    per_bucket = [[] for _ in range(n_ticks)]
    for i, ev in enumerate(all_events):
        per_bucket[i % n_ticks].append(ev)

    def hook(tick: int):
        if 0 <= tick < n_ticks:
            for ev in per_bucket[tick]:
                source.enqueue(ev)

    return hook


def main(argv: list[str]) -> int:
    setup_logging(level="INFO")

    n_agents = int(argv[1]) if len(argv) > 1 else 300
    n_ticks = int(argv[2]) if len(argv) > 2 else 12
    master_seed = 42

    # ---- Load news ----
    news_path = DATA_DIR / "sample_news.json"
    print(f"\nLoading news fixture: {news_path}")
    manual_src_prefetch = ManualUploadSource.from_json_file(news_path)
    all_events = manual_src_prefetch.fetch()
    print(f"  Loaded {len(all_events)} raw events")

    # ---- Build sim ----
    t0 = time.perf_counter()
    gen = WorldGenerator(master_seed=master_seed)
    factory = AgentFactory()
    agents = factory.build_batch(gen.generate(n_agents))
    clock = Clock.from_config()
    clock.master_seed = master_seed
    network = NetworkTopology(
        agents, NetworkConfig(local_k=10, rewire_p=0.1, hub_ratio=0.05),
    )
    network.build(clock.rng("network"))
    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    social = SocialMediaPlatform(memory_ticks=5, virality_threshold=1.5)
    news = NewsChannelPlatform(memory_ticks=5)

    # Live manual source that we feed at each tick
    live_src = ManualUploadSource(source_id="live")
    kg = KnowledgeGraph()
    mgr = IngestionManager(
        sources=[live_src],
        processors=[EnrichingProcessor()],
        knowledge_graph=kg,
        news_channel=news,
    )
    feed_hook = split_news_across_ticks(live_src, all_events, n_ticks)

    sim = SimulationEngine(
        agents=agents, network=network, modulator=modulator,
        platforms=[social, news], clock=clock,
        pre_tick_hooks=[feed_hook, lambda t: mgr.pull(t)],
    )
    print(f"Built sim with {len(agents)} agents in {time.perf_counter()-t0:.1f}s")

    # ---- Run ----
    t1 = time.perf_counter()
    sim.run(n_ticks)
    elapsed = time.perf_counter() - t1
    print(f"Ran {n_ticks} ticks in {elapsed:.1f}s "
          f"({elapsed*1000/n_ticks:.0f}ms/tick, "
          f"{elapsed*1000/(n_ticks*n_agents):.1f}ms/agent-tick)")

    # ---- Reports ----
    print_news_injection(news, all_events)
    print_tick_timeline(sim)
    print_topic_distribution(sim)
    print_kg_summary(kg)
    print_top_news_posts(news, sim)
    print_mood_contagion_sample(sim, news, agents)

    print(f"\n{'=' * 78}")
    print(f"  Phase 4 validation complete — {n_agents} agents, {n_ticks} ticks,"
          f" {len(all_events)} news events.")
    print("=" * 78)
    return 0


def print_news_injection(news: NewsChannelPlatform, all_events) -> None:
    print("\n[ News injection ]")
    print(f"  Raw events loaded:  {len(all_events)}")
    print(f"  NewsChannel posts:  {news.total_posts()}")


def print_tick_timeline(sim: SimulationEngine) -> None:
    print("\n[ Tick-by-tick activity ]")
    print("  tick   posts  engagements  lurkers   top_topic")
    for s in sim.history:
        top = max(s.posts_by_topic.items(), key=lambda kv: kv[1]) if s.posts_by_topic else ("—", 0)
        print(f"  {s.tick:4d}  {s.posts:6d}  {s.engagements:11d}  {s.lurkers:7d}   "
              f"{top[0]:8s}({top[1]})")


def print_topic_distribution(sim: SimulationEngine) -> None:
    total = Counter()
    for s in sim.history:
        for topic, c in s.posts_by_topic.items():
            total[topic] += c
    grand = sum(total.values())
    if grand == 0:
        return
    print("\n[ Topic distribution of agent-authored posts ]")
    for topic, c in total.most_common():
        frac = c / grand
        print(f"  {topic:10s}  {c:5d}  {frac*100:5.1f}%  [{bar(frac, 30)}]")


def print_kg_summary(kg: KnowledgeGraph) -> None:
    nodes, edges = kg.size()
    print("\n[ Knowledge graph ]")
    print(f"  Nodes: {nodes}   Edges: {edges}")
    print("  Top entities by mention count:")
    for name, c in kg.hot_entities(10):
        print(f"    {name:30s}  mentions={c:3d}  sentiment={kg.sentiment_of(name):+.2f}")


def print_top_news_posts(news: NewsChannelPlatform, sim: SimulationEngine) -> None:
    print("\n[ Top news posts by engagement ]")
    for p in news.top_posts(5):
        print(f"  tick {p.tick:2d}  {p.topic:8s}  sent={p.sentiment:+.2f}  "
              f"virality={p.virality:.2f}  eng={p.engagement}")


def print_mood_contagion_sample(
    sim: SimulationEngine, news: NewsChannelPlatform, agents,
) -> None:
    """Pick a handful of agents and show how their sentiment would shift given
    the news they saw."""
    print("\n[ Mood contagion sample (5 random agents) ]")
    import random as _r
    sample = _r.Random(42).sample(agents, k=min(5, len(agents)))
    for a in sample:
        visible = news.visible_for(a.profile.country, limit=5)
        avg_sent = 0.0 if not visible else statistics.mean(p.sentiment for p in visible)
        # How much that would nudge financial_optimism via mood contagion:
        delta = avg_sent * 0.05 * a.traits.herd_susceptibility
        print(f"  {a.profile.short_label():55s}  "
              f"herd={a.traits.herd_susceptibility:.2f}  "
              f"news_avg_sent={avg_sent:+.2f}  "
              f"opt_shift={delta:+.4f}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
