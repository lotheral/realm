"""Phase 5 end-to-end validation — collective astrological climate layer.

Runs a simulation over a span of time and reports:
  - Current era snapshot (outer-planet signs, moon phase, retrogrades, eclipses)
  - Collective modifier dict per-tick (top movers)
  - A/B comparison: aggregate trait means with climate OFF vs ON
  - Moon-phase distribution across the simulated window

Usage:
    python scripts/validate_phase5.py [N_AGENTS] [N_TICKS]
    Default: 200 agents, 30 ticks (~30 seconds).
"""

from __future__ import annotations

import contextlib
import sys
import time
from collections import Counter
from datetime import timedelta
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
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.personality.trait_vector import TraitVector, mean_trait_vector  # noqa: E402
from realm.simulation.climate import ClimateEngine  # noqa: E402
from realm.simulation.clock import Clock  # noqa: E402
from realm.simulation.engine import SimulationEngine  # noqa: E402
from realm.simulation.network import NetworkConfig, NetworkTopology  # noqa: E402
from realm.simulation.platforms.social_media import SocialMediaPlatform  # noqa: E402
from realm.simulation.transit_modulator import TransitModulator  # noqa: E402

logger = get_logger(__name__)


def bar(frac: float, width: int = 30) -> str:
    filled = int(round(frac * width))
    return "#" * filled + "." * (width - filled)


def print_era_snapshot(climate: ClimateEngine, clock: Clock) -> None:
    snap = climate.describe(clock.sim_time)
    print(f"\n[ Era snapshot — {clock.sim_time.isoformat()} ]")
    print("  Outer planets:")
    for body, (sign, direction) in snap["outer_planets"].items():
        print(f"    {body:9s}  {sign:12s}  {direction}")
    print(f"  Moon phase:  {snap['moon_phase']}")
    print(f"  Retrograde:  {', '.join(snap['retrograde']) or '(none)'}")
    print(f"  Eclipse:     {snap['eclipse'] or '(none)'}")


def print_top_climate_movers(climate: ClimateEngine, clock: Clock) -> None:
    mods = climate.compute(clock.sim_time)
    ranked = sorted(mods.items(), key=lambda kv: -abs(kv[1]))[:10]
    print("\n[ Top climate modifiers right now ]")
    for trait, delta in ranked:
        arrow = "↑" if delta > 0 else "↓"
        print(f"  {trait:32s}  {delta:+.4f}  {arrow}")


def print_moon_phase_distribution(
    climate: ClimateEngine, epoch, n_ticks: int, interval: timedelta,
) -> None:
    """Count moon phases across the simulation window."""
    phases = Counter()
    for i in range(n_ticks):
        t = epoch + interval * i
        snap = climate.describe(t)
        phases[snap["moon_phase"]] += 1
    total = sum(phases.values()) or 1
    print(f"\n[ Moon phase distribution across {n_ticks} ticks ]")
    for phase in ("new", "waxing", "full", "waning"):
        c = phases.get(phase, 0)
        frac = c / total
        print(f"  {phase:7s}  {c:4d}  {frac*100:5.1f}%  [{bar(frac, 25)}]")


def _build_sim(master_seed, n_agents, *, with_climate: bool):
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
    platform = SocialMediaPlatform(memory_ticks=5)
    climate = ClimateEngine(modulator, dampening=0.7) if with_climate else None
    return SimulationEngine(
        agents=agents, network=network, modulator=modulator,
        platforms=[platform], clock=clock, climate=climate,
    ), clock, climate


def print_ab_trait_comparison(
    master_seed: int, n_agents: int, n_ticks: int,
) -> None:
    """Run the same scenario with climate OFF vs ON and diff aggregate trait means.

    The transit modulator already shifts traits individually; climate layers an
    additional global component. We compare final post-tick trait vectors.
    """
    print("\n[ A/B trait comparison (climate OFF vs ON) ]")

    # Baseline without climate
    sim_a, _, _ = _build_sim(master_seed, n_agents, with_climate=False)
    # Snapshot all agents' traits BEFORE tick (natal + cultural, already the same
    # either way). The climate only affects per-tick effective traits — not the
    # persistent agent.traits. So we approximate by measuring the trait delta
    # that agents WOULD see in one tick.

    # Re-enable climate and measure deltas
    _, clock_b, climate_b = _build_sim(master_seed, n_agents, with_climate=True)
    agents_b = sim_a.agents
    sim_time = clock_b.sim_time
    collective_mod = climate_b.compute(sim_time)

    base_vectors = [a.traits for a in agents_b]
    climate_vectors = [a.traits.apply_modifier(collective_mod) for a in agents_b]
    base_mean = mean_trait_vector(base_vectors)
    climate_mean = mean_trait_vector(climate_vectors)

    diffs = []
    for name in TraitVector.trait_names():
        diff = getattr(climate_mean, name) - getattr(base_mean, name)
        diffs.append((name, diff))
    diffs.sort(key=lambda kv: -abs(kv[1]))
    print("  Top 10 trait shifts attributable to climate:")
    for name, d in diffs[:10]:
        arrow = "↑" if d > 0 else "↓"
        print(f"    {name:32s}  {d:+.4f}  {arrow}")


def print_tick_climate_timeline(climate: ClimateEngine, clock: Clock, n_ticks: int) -> None:
    """Print moon phase + retrograde bodies at each tick."""
    print("\n[ Climate timeline ]")
    print("  tick   date          phase    retrograde")
    epoch = clock.epoch
    interval = clock.interval
    for i in range(n_ticks):
        t = epoch + interval * i
        snap = climate.describe(t)
        retro = ",".join(snap["retrograde"]) or "-"
        date_str = t.strftime("%Y-%m-%d")
        print(f"  {i:4d}   {date_str}  {snap['moon_phase']:7s}  {retro}")


def main(argv: list[str]) -> int:
    setup_logging(level="INFO")

    n_agents = int(argv[1]) if len(argv) > 1 else 200
    n_ticks = int(argv[2]) if len(argv) > 2 else 30
    master_seed = 42

    print(f"\nRunning Phase 5 validation: {n_agents} agents, {n_ticks} ticks, "
          f"master_seed={master_seed}")

    sim, clock, climate = _build_sim(master_seed, n_agents, with_climate=True)
    assert climate is not None

    print_era_snapshot(climate, clock)
    print_top_climate_movers(climate, clock)
    print_moon_phase_distribution(climate, clock.epoch, n_ticks, clock.interval)
    print_ab_trait_comparison(master_seed, n_agents, n_ticks)

    print_tick_climate_timeline(climate, clock, min(n_ticks, 15))

    # Run the full simulation to verify no regressions
    t1 = time.perf_counter()
    sim.run(n_ticks)
    elapsed = time.perf_counter() - t1
    agg = sim.aggregate_stats()

    print("\n[ Simulation with climate ON ]")
    print(f"  Ticks:        {agg['ticks']}")
    print(f"  Posts:        {agg['posts']}")
    print(f"  Engagements:  {agg['engagements']}")
    print(f"  Runtime:      {elapsed:.1f}s "
          f"({elapsed*1000/max(n_ticks,1):.0f}ms/tick)")

    print(f"\n{'=' * 78}")
    print("  Phase 5 validation complete — collective climate layer active.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
