"""Phase 4-LLM validation — exercises LLM embedder, hybrid, spotlight, and
router with whatever backends are configured in the environment.

If no API keys are set, the script prints setup instructions and exits 0.
Add MOONSHOT_API_KEY (or OPENAI_API_KEY) to a `.env` file at the project root
and re-run.

Usage:
    python scripts/validate_phase4_llm.py
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env if present so the user can put API keys there.
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.astro.fixtures import STEVE_JOBS  # noqa: E402
from realm.core.logging import setup_logging  # noqa: E402
from realm.llm.router import is_llm_configured  # noqa: E402
from realm.llm.spotlight import SpotlightAnnotator, get_post_body  # noqa: E402
from realm.personality.hybrid import HybridEmbedder  # noqa: E402
from realm.personality.llm_based import LLMEmbedder  # noqa: E402
from realm.personality.rule_based import RuleBasedEmbedder  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

SETUP_HELP = """
No LLM backend key detected. To enable Phase 4 LLM features:

    1. Copy .env.example to .env
    2. Set MOONSHOT_API_KEY (preferred) and/or OPENAI_API_KEY
    3. Re-run this script

Expected env vars:
    MOONSHOT_API_KEY   - Moonshot (Kimi k2.6) API key
    OPENAI_API_KEY     - OpenAI (gpt-5.4) API key
    OLLAMA_HOST        - http://localhost:11434 (if running local Ollama)
"""


def compare_vectors(label: str, a: TraitVector, b: TraitVector, top_n: int = 8):
    dv = a.to_dict()
    dw = b.to_dict()
    diffs = sorted(
        ((name, dw[name] - dv[name]) for name in dv),
        key=lambda kv: -abs(kv[1]),
    )
    print(f"\n[ {label} ] biggest shifts (top {top_n}):")
    for name, d in diffs[:top_n]:
        arrow = "↑" if d > 0 else "↓"
        print(f"  {name:32s}  {dv[name]:.3f} → {dw[name]:.3f}  ({d:+.3f}) {arrow}")


def main():
    setup_logging(level="INFO")

    if not is_llm_configured():
        print(SETUP_HELP)
        return 0

    print("=== Phase 4-LLM validation ===")
    print(f"MOONSHOT_API_KEY: {'set' if os.getenv('MOONSHOT_API_KEY') else 'unset'}")
    print(f"OPENAI_API_KEY:   {'set' if os.getenv('OPENAI_API_KEY') else 'unset'}")

    # Build the natal chart for Steve Jobs
    engine = get_astro_engine("auto")
    chart = engine.calculate_natal_chart(
        STEVE_JOBS.birth_dt, STEVE_JOBS.latitude,
        STEVE_JOBS.longitude, STEVE_JOBS.timezone,
    )
    print(f"\nSubject: {STEVE_JOBS.name}  ({engine.backend_name})")
    sun = chart.planet("Sun")
    moon = chart.planet("Moon")
    print(f"  Sun  {sun.sign} {sun.sign_degree:.1f}°")
    print(f"  Moon {moon.sign} {moon.sign_degree:.1f}°")

    # --- Rule-based baseline ---
    t0 = time.perf_counter()
    tv_rule = RuleBasedEmbedder().embed(chart)
    dt_rule = time.perf_counter() - t0
    print(f"\n[ rule-based ] {dt_rule*1000:.0f}ms")

    # --- LLM Mode B ---
    try:
        t0 = time.perf_counter()
        tv_llm = LLMEmbedder(fallback_to_rule_based=False).embed(chart)
        dt_llm = time.perf_counter() - t0
        print(f"\n[ LLM Mode B ] {dt_llm:.1f}s")
        compare_vectors("Rule-based → LLM", tv_rule, tv_llm)
    except Exception as e:
        print(f"\n[ LLM Mode B ] FAILED: {e}")
        tv_llm = None

    # --- Hybrid Mode C ---
    try:
        t0 = time.perf_counter()
        tv_hybrid = HybridEmbedder(blend_ratio=0.6).embed(chart)
        dt_hybrid = time.perf_counter() - t0
        print(f"\n[ Hybrid Mode C ] {dt_hybrid:.1f}s  (blend_ratio=0.6)")
        compare_vectors("Rule-based → Hybrid", tv_rule, tv_hybrid)
    except Exception as e:
        print(f"\n[ Hybrid Mode C ] FAILED: {e}")

    # --- Spotlight narrative ---
    print("\n[ Spotlight narrative demo ]")
    try:
        from realm.agents.factory import AgentFactory
        from realm.demographics.world_generator import WorldGenerator
        from realm.simulation.clock import Clock
        from realm.simulation.engine import SimulationEngine
        from realm.simulation.network import NetworkConfig, NetworkTopology
        from realm.simulation.platforms.social_media import SocialMediaPlatform
        from realm.simulation.transit_modulator import TransitModulator

        agents = AgentFactory().build_batch(
            WorldGenerator(master_seed=42).generate(40)
        )
        clock = Clock.from_config()
        net = NetworkTopology(agents, NetworkConfig(local_k=4))
        net.build(clock.rng("network"))
        mod = TransitModulator.from_config(engine)
        sim = SimulationEngine(
            agents=agents, network=net, modulator=mod,
            platforms=[SocialMediaPlatform(virality_threshold=1.3)], clock=clock,
        )
        sim.run(2)

        annotator = SpotlightAnnotator(ratio=0.15, max_posts_per_tick=2, min_virality=1.0)
        if not annotator.is_enabled():
            print("  Spotlight disabled (no LLM backend) — skipping.")
        else:
            annotated = annotator.annotate_tick(sim)
            platform = sim.platforms[0]
            for post in annotated:
                body = get_post_body(platform, post.post_id)
                author = next(
                    (a for a in sim.agents if a.agent_id == post.author_id), None,
                )
                name = f"{author.profile.name_first} {author.profile.name_last}" if author else post.author_id
                print(f"\n  >>> {name} ({post.topic}, sent={post.sentiment:+.2f})")
                print(f"      \"{body}\"")
    except Exception as e:
        print(f"  Spotlight demo FAILED: {e}")

    print("\n" + "=" * 60)
    print("  Phase 4-LLM validation complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
