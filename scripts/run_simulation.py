"""REALM Sprint 9 WP4 — full-scale simulation runner.

Runs N agents × M ticks with the ExperienceDriftEngine wired in, writes
performance profiling, population statistics, and drift analysis to the
specified output directory.

Usage:
    python scripts/run_simulation.py --agents=10000 --ticks=50 --output=outputs/sim_10k_run1

Determinism: seeded via Clock.master_seed (default 42).
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path
from statistics import mean, stdev

# Ensure repo root is on PYTHONPATH when script is run directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402
from realm.simulation.climate import ClimateEngine  # noqa: E402
from realm.simulation.clock import Clock  # noqa: E402
from realm.simulation.drift import ExperienceDriftEngine  # noqa: E402
from realm.simulation.engine import SimulationEngine  # noqa: E402
from realm.simulation.network import NetworkConfig, NetworkTopology  # noqa: E402
from realm.simulation.platforms.social_media import SocialMediaPlatform  # noqa: E402
from realm.simulation.transit_modulator import TransitModulator  # noqa: E402

logger = get_logger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="REALM full simulation runner")
    p.add_argument("--agents", type=int, default=10000, help="agent count (default 10000)")
    p.add_argument("--ticks", type=int, default=50, help="simulation ticks (default 50)")
    p.add_argument("--seed", type=int, default=42, help="master seed (default 42)")
    p.add_argument("--drift", action="store_true", default=True, help="enable drift (default on)")
    p.add_argument("--no-drift", dest="drift", action="store_false", help="disable drift")
    p.add_argument("--checkpoint-interval", type=int, default=10,
                   help="ticks between JSON checkpoints (0 = none)")
    p.add_argument("--output", type=str, default="outputs/sim_run",
                   help="output directory")
    p.add_argument("--profile", action="store_true", default=True,
                   help="run under cProfile (default on)")
    p.add_argument("--no-profile", dest="profile", action="store_false")
    return p.parse_args(argv)


def build_simulation(
    n_agents: int, seed: int, enable_drift: bool,
) -> tuple[SimulationEngine, Clock, ExperienceDriftEngine | None, float]:
    """Return (engine, clock, drift_engine_or_none, agent_build_seconds)."""
    t0 = time.perf_counter()
    gen = WorldGenerator(master_seed=seed)
    factory = AgentFactory()
    profiles = gen.generate(n_agents)
    agents = factory.build_batch(profiles)
    build_secs = time.perf_counter() - t0

    clock = Clock.from_config()
    clock.master_seed = seed

    network = NetworkTopology(
        agents, NetworkConfig(local_k=10, rewire_p=0.1, hub_ratio=0.05),
    )
    network.build(clock.rng("network"))

    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    platform = SocialMediaPlatform(memory_ticks=5)
    climate = ClimateEngine(modulator, dampening=0.7)

    drift_engine = ExperienceDriftEngine(max_drift_ratio=0.10) if enable_drift else None

    sim = SimulationEngine(
        agents=agents,
        network=network,
        modulator=modulator,
        platforms=[platform],
        clock=clock,
        climate=climate,
        drift_engine=drift_engine,
    )
    return sim, clock, drift_engine, build_secs


def snapshot_trait_distribution(agents) -> dict[str, dict[str, float]]:
    """Per-trait mean/std/min/max across all agents."""
    trait_names = TraitVector.trait_names()
    result: dict[str, dict[str, float]] = {}
    for t in trait_names:
        values = [getattr(a.traits, t) for a in agents]
        if not values:
            continue
        result[t] = {
            "mean": mean(values),
            "std": stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    return result


def snapshot_drifted_traits(agents, drift_engine: ExperienceDriftEngine) -> dict[str, dict[str, float]]:
    trait_names = TraitVector.trait_names()
    result: dict[str, dict[str, float]] = {}
    drifted_vectors = [drift_engine.current_traits(a) for a in agents]
    for t in trait_names:
        values = [getattr(v, t) for v in drifted_vectors]
        result[t] = {
            "mean": mean(values),
            "std": stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    return result


def write_checkpoint(
    out_dir: Path,
    tick: int,
    sim: SimulationEngine,
    drift_engine: ExperienceDriftEngine | None,
) -> Path:
    """Minimal JSON checkpoint — per-tick summary + drift state."""
    ck_dir = out_dir / "checkpoints"
    ck_dir.mkdir(parents=True, exist_ok=True)
    path = ck_dir / f"tick_{tick:04d}.json"
    payload = {
        "tick": tick,
        "n_agents": len(sim.agents),
        "history_tail": [
            {
                "tick": s.tick,
                "posts": s.posts,
                "engagements": s.engagements,
                "actions_by_type": dict(s.actions_by_type),
            }
            for s in sim.history[-10:]
        ],
    }
    if drift_engine is not None:
        payload["drift_state"] = drift_engine.to_state()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def country_trait_summary(agents) -> dict[str, dict[str, float]]:
    """Per-country trait means — Hofstede visibility proxy."""
    by_country: dict[str, list] = {}
    for a in agents:
        by_country.setdefault(a.profile.country, []).append(a.traits)
    trait_names = TraitVector.trait_names()
    out: dict[str, dict[str, float]] = {}
    for country, vecs in by_country.items():
        entry: dict[str, float] = {"n": len(vecs)}
        for t in trait_names:
            entry[t] = mean(getattr(v, t) for v in vecs)
        out[country] = entry
    return out


def drift_magnitude_summary(drift_engine: ExperienceDriftEngine, agents) -> dict:
    mags = [drift_engine.cumulative_magnitude(a.agent_id) for a in agents]
    events = [drift_engine.event_count(a.agent_id) for a in agents]
    if not mags:
        return {"n": 0}
    return {
        "n": len(mags),
        "mean_magnitude": mean(mags),
        "std_magnitude": stdev(mags) if len(mags) > 1 else 0.0,
        "max_magnitude": max(mags),
        "mean_event_count": mean(events),
        "max_event_count": max(events),
        "agents_with_drift": sum(1 for m in mags if m > 0),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    setup_logging(level="INFO")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Build phase ---------------------------------------------------
    print(f"[build] {args.agents} agents, seed={args.seed} ...")
    tracemalloc.start()
    sim, clock, drift_engine, build_secs = build_simulation(
        args.agents, args.seed, args.drift,
    )
    cur_mem, peak_mem = tracemalloc.get_traced_memory()
    print(f"[build] done in {build_secs:.2f}s - "
          f"mem cur={cur_mem / 1e6:.1f}MB peak={peak_mem / 1e6:.1f}MB", flush=True)

    tick0_traits = snapshot_trait_distribution(sim.agents)
    country_summary = country_trait_summary(sim.agents)

    # --- Run phase -----------------------------------------------------
    run_start = time.perf_counter()
    per_tick_secs: list[float] = []
    profiler = cProfile.Profile() if args.profile else None
    if profiler:
        profiler.enable()

    for i in range(args.ticks):
        ts = time.perf_counter()
        sim.tick()
        per_tick_secs.append(time.perf_counter() - ts)
        if args.checkpoint_interval and (i + 1) % args.checkpoint_interval == 0:
            ck = write_checkpoint(out_dir, i + 1, sim, drift_engine)
            print(f"[tick {i + 1}] checkpoint -> {ck.name}  "
                  f"(tick mean {mean(per_tick_secs):.3f}s)", flush=True)

    if profiler:
        profiler.disable()
    run_secs = time.perf_counter() - run_start
    cur_mem2, peak_mem2 = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # --- Analysis ------------------------------------------------------
    tickn_traits = snapshot_trait_distribution(sim.agents)
    drifted_snapshot = (
        snapshot_drifted_traits(sim.agents, drift_engine)
        if drift_engine is not None else tickn_traits
    )
    drift_summary = (
        drift_magnitude_summary(drift_engine, sim.agents)
        if drift_engine is not None else {"n": 0}
    )

    # Action breakdown aggregated
    total_actions: Counter = Counter()
    for s in sim.history:
        for k, v in s.actions_by_type.items():
            total_actions[k] += v

    # --- Write outputs -------------------------------------------------
    population_stats = {
        "tick_0": tick0_traits,
        "tick_N": tickn_traits,
        "tick_N_drifted": drifted_snapshot,
    }
    (out_dir / "population_stats.json").write_text(
        json.dumps(population_stats, indent=2), encoding="utf-8")

    simulation_log = {
        "n_agents": args.agents,
        "n_ticks": args.ticks,
        "seed": args.seed,
        "drift_enabled": args.drift,
        "per_tick": [
            {
                "tick": s.tick,
                "posts": s.posts,
                "engagements": s.engagements,
                "actions_by_type": dict(s.actions_by_type),
                "seconds": per_tick_secs[i] if i < len(per_tick_secs) else None,
            }
            for i, s in enumerate(sim.history)
        ],
        "totals": dict(total_actions),
    }
    (out_dir / "simulation_log.json").write_text(
        json.dumps(simulation_log, indent=2), encoding="utf-8")

    (out_dir / "drift_analysis.json").write_text(
        json.dumps(drift_summary, indent=2), encoding="utf-8")

    # Country summary, top-30 by n
    top_countries = dict(
        sorted(country_summary.items(), key=lambda kv: -kv[1]["n"])[:30]
    )
    (out_dir / "country_summary_top30.json").write_text(
        json.dumps(top_countries, indent=2), encoding="utf-8")

    # Performance profile (top 30 cumulative)
    profile_text = ""
    if profiler:
        buf = io.StringIO()
        ps = pstats.Stats(profiler, stream=buf).sort_stats("cumulative")
        ps.print_stats(30)
        profile_text = buf.getvalue()
        (out_dir / "performance_profile.txt").write_text(profile_text, encoding="utf-8")

    # --- Summary report -----------------------------------------------
    total_posts = sum(s.posts for s in sim.history)
    total_engagements = sum(s.engagements for s in sim.history)

    report = [
        "# Simulation Run Report",
        "",
        f"- Agents: **{args.agents:,}**",
        f"- Ticks: **{args.ticks}**",
        f"- Seed: {args.seed}",
        f"- Drift: {'on' if args.drift else 'off'}",
        "",
        "## Performance",
        "",
        f"- Agent build: {build_secs:.2f}s",
        f"- Simulation: {run_secs:.2f}s ({run_secs / args.ticks:.3f}s/tick mean)",
        f"- Tick min/median/max: "
        f"{min(per_tick_secs):.3f} / "
        f"{sorted(per_tick_secs)[len(per_tick_secs) // 2]:.3f} / "
        f"{max(per_tick_secs):.3f} s",
        f"- Peak memory: {peak_mem2 / 1e6:.1f} MB "
        f"({peak_mem2 / 1e9:.2f} GB)",
        "",
        "## Activity Totals",
        "",
        f"- Total posts: {total_posts:,}",
        f"- Total engagements: {total_engagements:,}",
        f"- Actions breakdown: {dict(total_actions)}",
        "",
        "## Drift Summary",
        "",
        f"- {drift_summary}",
        "",
        "## Tick 0 → Tick N Trait Drift (representative traits)",
        "",
        "| Trait | μ@0 | μ@N(drifted) | Δμ | σ@N | Δσ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    focus = [
        "empathy", "risk_appetite", "loss_aversion", "analytical_depth",
        "neuroticism", "openness", "social_dominance", "contrarian_tendency",
    ]
    for t in focus:
        m0 = tick0_traits[t]["mean"]
        m_end = drifted_snapshot[t]["mean"]
        s0 = tick0_traits[t]["std"]
        s_end = drifted_snapshot[t]["std"]
        report.append(
            f"| {t} | {m0:.4f} | {m_end:.4f} | {m_end - m0:+.4f} | {s_end:.4f} | {s_end - s0:+.4f} |"
        )

    if profile_text:
        report += [
            "",
            "## Top 10 Profile Entries (cumulative time)",
            "",
            "```",
            "\n".join(profile_text.splitlines()[:40]),
            "```",
        ]
    report_path = out_dir / "sim_10k_report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\n[done] report -> {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
