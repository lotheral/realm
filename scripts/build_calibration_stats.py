"""Build per-trait population statistics for the soft-rescale calibrator.

Generates a diverse population, runs the FULL post-Phase-2 pipeline (raw
adapter -> cultural modifier, calibration OFF), and records (mean, std) per
trait. The resulting JSON is what realm.personality.calibration loads to
decide how much to stretch each trait toward target.

Adapter-aware + source-aware:
  --adapter=astrological  (default) - WorldGenerator demographics, natal-chart
                                       embedder.
  --adapter=big_five                 - WorldGenerator demographics + synthetic
                                       OCEAN scores via build_bf_profiles
                                       (when --source=synthetic, default), or
                                       the real automoto/big-five-data
                                       stratified sample (when --source=real).
  --adapter=demographic              - WorldGenerator demographics, demographic
                                       adapter.
  --adapter=blended                  - WorldGenerator demographics + synthetic
                                       OCEAN scores (same profile builder as
                                       big_five path) passed through the
                                       blended pipeline. Output: config/
                                       trait_calibration_blended.json.

  --source=synthetic (default) - stats from a synthetically-generated
                                 population.
                                 Output: config/trait_calibration_{adapter}.json
  --source=real                 - only valid for --adapter=big_five. Loads a
                                 stratified real-population sample via
                                 scripts/load_bigfive_real.load_real_population.
                                 Output: config/trait_calibration_big_five_real.json

Re-run for the relevant (adapter, source) pair whenever:
  - rule_based_embedder.dampening or planet_trait_map changes (astrological)
  - data/personality/big_five_derivation.json changes (big_five, any source)
  - cultural_modifier.blend_ratio changes (any)
  - the real dataset is refreshed or its country mapping changes (big_five, real)

Usage:
    python scripts/build_calibration_stats.py [N=5000] [--adapter=astrological]
    python scripts/build_calibration_stats.py 5000 --adapter=big_five
    python scripts/build_calibration_stats.py 5000 --adapter=big_five --source=real
"""

from __future__ import annotations

import contextlib as _ctx
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.core.logging import setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.personality.adapters import get_input_adapter  # noqa: E402
from realm.personality.calibration import CalibrationStats, TraitCalibrator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

# Reuse BF population helper for the big_five adapter path.
sys.path.insert(0, str(ROOT / "scripts"))


def _build_profiles(
    adapter_type: str, source: str, n_agents: int, seed: int = 7,
):
    """Build N profiles appropriate for the requested (adapter, source).

    BigFive adapter requires `big_five_scores` populated. With
    source=synthetic (default) that comes from `build_bf_profiles` (Costa
    & McCrae norms); with source=real it comes from a stratified
    `load_real_population` sample.
    """
    if adapter_type in ("big_five", "blended"):
        if source == "real":
            if adapter_type != "big_five":
                raise ValueError(
                    f"--source=real is only supported for --adapter=big_five; "
                    f"got adapter={adapter_type!r}.",
                )
            from load_bigfive_real import load_real_population
            profiles, _ = load_real_population(n=n_agents, seed=seed)
            return profiles
        from generate_bf_population import build_bf_profiles
        return build_bf_profiles(n_agents, seed=seed)
    if source != "synthetic":
        raise ValueError(
            f"--source={source!r} is only supported for --adapter=big_five; "
            f"got adapter={adapter_type!r}.",
        )
    return WorldGenerator(master_seed=seed).generate(n_agents)


def _parse_argv(argv: list[str]) -> tuple[int, str, str]:
    n_agents = 5000
    adapter_type = "astrological"
    source = "synthetic"
    for arg in argv[1:]:
        if arg.startswith("--adapter="):
            adapter_type = arg.split("=", 1)[1].strip()
        elif arg.startswith("--source="):
            source = arg.split("=", 1)[1].strip()
        elif arg.isdigit():
            n_agents = int(arg)
    return n_agents, adapter_type, source


def _output_path_for(adapter_type: str, source: str) -> Path:
    base = f"trait_calibration_{adapter_type}"
    if source and source != "synthetic":
        base = f"{base}_{source}"
    return ROOT / "config" / f"{base}.json"


def main(argv: list[str]) -> int:
    setup_logging(level="WARNING")
    n_agents, adapter_type, source = _parse_argv(argv)
    output_path = _output_path_for(adapter_type, source)

    print(
        f"Building calibration stats: adapter={adapter_type}, "
        f"source={source}, N={n_agents}",
    )
    print(f"Output: {output_path}")
    t0 = time.perf_counter()

    profiles = _build_profiles(adapter_type, source, n_agents, seed=7)
    adapter = get_input_adapter(adapter_type)
    # Calibration OFF so we measure raw post-cultural-modifier traits.
    factory = AgentFactory(
        adapter=adapter,
        calibrator=TraitCalibrator(enabled=False),
    )
    agents = factory.build_batch(profiles)

    t_gen = time.perf_counter() - t0
    print(f"Generated {len(agents)}/{n_agents} agents in {t_gen:.1f}s")

    per_trait: dict[str, tuple[float, float]] = {}
    for n in TraitVector.trait_names():
        vals = [getattr(a.traits, n) for a in agents]
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        per_trait[n] = (mean, std)

    stats = CalibrationStats(per_trait=per_trait)
    stats.to_json(output_path)
    print(f"Wrote {output_path}")

    print("\nPer-trait observed stats:")
    print(f"  {'trait':32s}  {'mean':>6s}  {'std':>6s}")
    for n in TraitVector.trait_names():
        m, s = per_trait[n]
        print(f"  {n:32s}  {m:.3f}   {s:.3f}")

    avg_std = statistics.mean(s for _, s in per_trait.values())
    print(f"\nMean std across 24 traits: {avg_std:.3f}")
    print(f"Calibration will stretch toward target std=0.17 (factor ~{0.17 / max(avg_std, 1e-4):.2f}x)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
