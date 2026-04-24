"""Butterfly-effect demo.

Runs the same prediction twice - once with NO injected news (baseline), once
with a burst of TECH-themed SeedEvents injected at tick 0 - and compares the
resulting `tech_share` distributions branch by branch.

This is the multi-branch what-if test described in decision #13. A positive
delta (scenario > baseline) proves that news events propagate through the
simulation and reshape agent posting behaviour.

Usage:
    python scripts/demo_butterfly.py
"""

from __future__ import annotations

import contextlib
import statistics
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import contextlib as _ctx  # noqa: E402

with _ctx.suppress(ImportError):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from realm.core.logging import setup_logging  # noqa: E402
from realm.ingestion.scenarios import build_tech_scenario  # noqa: E402
from realm.output.predictor import (  # noqa: E402
    BranchSpec,
    PredictionEngine,
    observe_topic_share,
)


def run_prediction(name: str, spec: BranchSpec, master_seed: int) -> list[float]:
    engine = PredictionEngine(master_seed=master_seed)
    t0 = time.perf_counter()
    outcome = engine.run(spec, question=f"[{name}] tech dominates?")
    dt = time.perf_counter() - t0
    print(f"\n[ {name} ]  {dt:.1f}s")
    print(f"  branches: {[f'{v:.3f}' for v in outcome.branch_values]}")
    print(f"  mean={outcome.mean_value:.3f}  stdev={outcome.stddev_value:.3f}  "
          f"P(>{spec.threshold:.2f})={outcome.probability:.2f}  conf={outcome.confidence:.2f}")
    return list(outcome.branch_values)


def main() -> int:
    setup_logging(level="WARNING")
    master_seed = 42

    # Keep the sim light so both runs complete quickly
    common = {
        "name": "tech_share",
        "observe": observe_topic_share("tech"),
        "threshold": 0.30,
        "horizon_ticks": 12,
        "n_branches": 3,
        "n_agents": 150,
    }

    baseline = BranchSpec(**common)
    scenario = BranchSpec(**common, initial_events=build_tech_scenario())

    print(f"Butterfly effect demo - master_seed={master_seed}, "
          f"{common['n_agents']} agents x {common['horizon_ticks']} ticks x "
          f"{common['n_branches']} branches")
    print(f"Threshold: tech_share >= {common['threshold']:.2f} for 'tech dominates'.")

    base = run_prediction("BASELINE (no news injection)", baseline, master_seed)
    scn = run_prediction("SCENARIO (Apple AI device + 4 cascades)", scenario, master_seed)

    print("\n" + "=" * 66)
    print("  Branch-by-branch comparison")
    print("=" * 66)
    print(f"  {'branch':>7}  {'baseline':>10}  {'scenario':>10}  {'delta':>8}")
    for i, (b, s) in enumerate(zip(base, scn, strict=True)):
        delta = s - b
        marker = "up" if delta > 0 else ("dn" if delta < 0 else "=")
        print(f"  {i:>7d}  {b:>10.3f}  {s:>10.3f}  {delta:>+7.3f} {marker}")

    mean_base = statistics.mean(base)
    mean_scn = statistics.mean(scn)
    lift = mean_scn - mean_base

    print(f"\n  mean shift: {mean_base:.3f} -> {mean_scn:.3f}  (delta {lift:+.3f})")
    if lift > 0.05:
        print("  [+] News injection propagated - the butterfly flapped its wings.")
    elif lift > 0.0:
        print("  [~] Small lift; butterfly is whispering.")
    else:
        print("  [-] No lift - either the feedback loop isn't wired or news signal too weak.")

    crossed_base = sum(1 for v in base if v >= common["threshold"])
    crossed_scn = sum(1 for v in scn if v >= common["threshold"])
    print(f"\n  branches crossing threshold: baseline={crossed_base}/{len(base)}  "
          f"scenario={crossed_scn}/{len(scn)}")

    print("\n" + "=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
