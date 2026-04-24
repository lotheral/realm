"""Phase 6 end-to-end validation.

Runs a simulation, exercises every OutputLayer surface:
  - DashboardService snapshots (stats, timeline, agents, network, climate, KG, mood)
  - Multi-branch PredictionEngine on 3 sample questions
  - Markdown report generator (writes to outputs/phase6_report.md)

No web server is launched — use `scripts/serve_dashboard.py` for that.

Usage:
    python scripts/validate_phase6.py [N_AGENTS] [N_TICKS]
    Default: 200 agents, 15 ticks (~20s).
"""

from __future__ import annotations

import contextlib
import sys
import time
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
from realm.core.logging import setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.ingestion.entity_extractor import EnrichingProcessor  # noqa: E402
from realm.ingestion.knowledge_graph import KnowledgeGraph  # noqa: E402
from realm.ingestion.manager import IngestionManager  # noqa: E402
from realm.ingestion.sources.manual_upload import ManualUploadSource  # noqa: E402
from realm.output.dashboard_service import DashboardService  # noqa: E402
from realm.output.predictor import predict  # noqa: E402
from realm.output.report_generator import generate_report  # noqa: E402
from realm.simulation.climate import ClimateEngine  # noqa: E402
from realm.simulation.clock import Clock  # noqa: E402
from realm.simulation.engine import SimulationEngine  # noqa: E402
from realm.simulation.network import NetworkConfig, NetworkTopology  # noqa: E402
from realm.simulation.platforms.news_channel import NewsChannelPlatform  # noqa: E402
from realm.simulation.platforms.social_media import SocialMediaPlatform  # noqa: E402
from realm.simulation.transit_modulator import TransitModulator  # noqa: E402

SAMPLE_QUESTIONS = [
    "Will tech dominate the topic mix?",
    "Will mean empathy rise above 0.65?",
    "Will engagement rate stay above 1.3?",
]


def main(argv: list[str]) -> int:
    setup_logging(level="INFO")
    n_agents = int(argv[1]) if len(argv) > 1 else 200
    n_ticks = int(argv[2]) if len(argv) > 2 else 15
    master_seed = 42

    print(f"\n=== Phase 6 validation — {n_agents} agents, {n_ticks} ticks ===")
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
    climate = ClimateEngine(modulator, dampening=0.7)
    social = SocialMediaPlatform(memory_ticks=5)
    news = NewsChannelPlatform(memory_ticks=5)

    # Feed sample news
    news_path = PROJECT_ROOT / "data" / "sample_news.json"
    src = ManualUploadSource.from_json_file(news_path) if news_path.exists() else ManualUploadSource()
    kg = KnowledgeGraph()
    mgr = IngestionManager(
        sources=[src], processors=[EnrichingProcessor()],
        knowledge_graph=kg, news_channel=news,
    )

    sim = SimulationEngine(
        agents=agents, network=network, modulator=modulator,
        platforms=[social, news], clock=clock, climate=climate,
        pre_tick_hooks=[lambda t: mgr.pull(t)],
    )
    sim.run(n_ticks)
    print(f"  Simulation: {time.perf_counter() - t0:.1f}s")

    # --- DashboardService surfaces ---
    svc = DashboardService(sim=sim, network=network, climate=climate, knowledge_graph=kg)

    stats = svc.stats()
    print(f"\n[ stats ] tick={stats['current_tick']}  "
          f"posts={stats['total_posts']}  eng={stats['total_engagements']}")

    climate_snap = svc.climate_snapshot()
    print(f"[ climate ] moon={climate_snap['moon_phase']}  "
          f"retro={len(climate_snap['retrograde_bodies'])}")

    net_snap = svc.network_snapshot(sample_size=80)
    print(f"[ network ] {len(net_snap['nodes'])} nodes, {len(net_snap['edges'])} edges (sampled)")

    mood = svc.mood()
    top_up = mood["strongest_up"][0]
    print(f"[ mood ] top up: {top_up['trait']} = {top_up['value']}")

    kg_snap = svc.kg_snapshot(top_n=5)
    print(f"[ kg ] {kg_snap['nodes']} nodes, {kg_snap['edges']} edges")

    posts = svc.top_posts(n=3)
    if posts:
        print(f"[ posts ] #1 topic={posts[0]['topic']}  eng={posts[0]['engagement']}")

    # --- PredictionEngine ---
    print("\n[ predictions ]")
    for q in SAMPLE_QUESTIONS:
        t1 = time.perf_counter()
        outcome = predict(q, master_seed=master_seed)
        print(f"  Q: {q}")
        print(f"     → P={outcome.probability:.2f}  "
              f"mean={outcome.mean_value:.3f}  "
              f"stdev={outcome.stddev_value:.3f}  "
              f"conf={outcome.confidence:.2f}  "
              f"({time.perf_counter() - t1:.1f}s)")

    # --- Report ---
    report_dir = PROJECT_ROOT / "outputs"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "phase6_report.md"
    md = generate_report(sim, network=network, climate=climate, kg=kg,
                         title=f"REALM run · seed {master_seed} · {n_agents} agents / {n_ticks} ticks")
    report_path.write_text(md, encoding="utf-8")
    print(f"\n[ report ] wrote {report_path}  ({len(md)} chars)")

    elapsed = time.perf_counter() - t0
    print(f"\n{'=' * 60}")
    print(f"  Phase 6 validation complete in {elapsed:.1f}s")
    print("  Launch the live dashboard: python scripts/serve_dashboard.py")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
