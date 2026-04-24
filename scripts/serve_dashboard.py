"""Launch the REALM dashboard on a local port.

Builds a simulation, wires up ingestion + climate, optionally auto-ticks in a
background thread, and serves the FastAPI app with the D3.js UI at /.

Usage:
    python scripts/serve_dashboard.py                # defaults
    python scripts/serve_dashboard.py 500 --port 8888
    python scripts/serve_dashboard.py 300 --no-autotick
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import threading
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env BEFORE any realm imports so KERYKEION_GEONAMES_USERNAME,
# API keys, and model overrides are visible to downstream modules.
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn  # noqa: E402

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.ingestion.entity_extractor import EnrichingProcessor  # noqa: E402
from realm.ingestion.knowledge_graph import KnowledgeGraph  # noqa: E402
from realm.ingestion.manager import IngestionManager  # noqa: E402
from realm.ingestion.sources.manual_upload import ManualUploadSource  # noqa: E402
from realm.output.api import create_app  # noqa: E402
from realm.output.dashboard_service import DashboardService  # noqa: E402
from realm.simulation.climate import ClimateEngine  # noqa: E402
from realm.simulation.clock import Clock  # noqa: E402
from realm.simulation.engine import SimulationEngine  # noqa: E402
from realm.simulation.network import NetworkConfig, NetworkTopology  # noqa: E402
from realm.simulation.platforms.news_channel import NewsChannelPlatform  # noqa: E402
from realm.simulation.platforms.social_media import SocialMediaPlatform  # noqa: E402
from realm.simulation.transit_modulator import TransitModulator  # noqa: E402

logger = get_logger(__name__)


def build_everything(master_seed: int, n_agents: int, *, prewarm_ticks: int = 3):
    logger.info("Building %d agents…", n_agents)
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

    # Ingestion
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
    if prewarm_ticks > 0:
        logger.info("Pre-warming %d ticks…", prewarm_ticks)
        sim.run(prewarm_ticks)

    svc = DashboardService(sim=sim, network=network, climate=climate, knowledge_graph=kg)
    return svc


def auto_tick_thread(svc: DashboardService, interval_s: float, stop: threading.Event,
                     lock: threading.Lock):
    """Background ticker. Holds `lock` while advancing so /api/ reads don't
    see mid-tick state."""
    logger.info("Auto-ticker running every %.1fs", interval_s)
    while not stop.is_set():
        if stop.wait(interval_s):
            return
        with lock:
            try:
                svc.sim.tick()
            except Exception as e:
                logger.warning("auto_tick failed: %s", e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("n_agents", nargs="?", type=int, default=300)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prewarm", type=int, default=5)
    parser.add_argument("--no-autotick", action="store_true")
    parser.add_argument("--tick-interval", type=float, default=3.0)
    args = parser.parse_args()

    setup_logging(level="INFO")
    svc = build_everything(args.seed, args.n_agents, prewarm_ticks=args.prewarm)

    # Serialize writes with a lock the api wraps implicitly via single-thread
    # Uvicorn workers. For the MVP we trust the GIL + auto-ticker Lock — actual
    # API reads and tick writes interleave but each call is short.
    lock = threading.Lock()

    if not args.no_autotick:
        stop = threading.Event()
        t = threading.Thread(
            target=auto_tick_thread,
            args=(svc, args.tick_interval, stop, lock),
            daemon=True,
        )
        t.start()

    app = create_app(svc)
    print(f"\n  REALM dashboard running at  http://{args.host}:{args.port}/")
    print(f"  API docs:                    http://{args.host}:{args.port}/docs")
    if not args.no_autotick:
        print(f"  Auto-ticking every          {args.tick_interval}s")
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning",
                access_log=False)


if __name__ == "__main__":
    main()
