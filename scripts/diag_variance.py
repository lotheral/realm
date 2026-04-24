"""Trait variance diagnostic (Phase 1 of variance-compression fix).

Generates N agents once, then runs a 2D sweep over (dampening, weight_floor)
and logs per-stage (S1..S5) mean/std for every trait.

Stages
------
    S1  per-planet raw contribution, summed (pre-dampening)
    S2  per-planet contribution after × dampening, summed
    S3  accumulated scores (starts at 0.5 baseline) pre-clamp
    S4  post-clamp TraitVector (Mode A output, natal-only)
    S5  after cultural modifier (final trait)

Output
------
    - compact heatmap on stdout (mean-over-traits σ at S5 for each sweep cell)
    - full breakdown in outputs/diag_variance.md
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
from realm.astro.dignity_analyzer import planet_strength  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.core.types import NatalChart  # noqa: E402
from realm.culture.modifier import CulturalModifier  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.personality.aspect_modifiers import planet_aspect_multiplier  # noqa: E402
from realm.personality.rule_based import (  # noqa: E402
    MAX_ORB_FOR_TIGHTNESS,
    RuleBasedEmbedder,
)
from realm.personality.trait_vector import TraitVector  # noqa: E402

logger = get_logger(__name__)

DAMPENING_VALUES = (0.12, 0.20, 0.28, 0.40)
WEIGHT_FLOOR_VALUES = (0.35, 0.50, 0.65)
TARGET_STD = 0.17  # Big Five adult population norm on [0,1] scale


class InstrumentedRuleBasedEmbedder(RuleBasedEmbedder):
    """Mirror of RuleBasedEmbedder.embed() that also returns per-stage dicts."""

    def embed_with_stages(
        self, chart: NatalChart
    ) -> tuple[dict[str, float], dict[str, float], dict[str, float], TraitVector]:
        names = TraitVector.trait_names()
        s1 = dict.fromkeys(names, 0.0)
        s2 = dict.fromkeys(names, 0.0)
        scores = dict.fromkeys(names, 0.5)

        for p in chart.planets:
            trait_deltas = self._planet_trait_map.get(p.name)
            if not trait_deltas:
                continue
            strength = planet_strength(p)
            weight = self._planet_weights.get(p.name, 0.3)
            sign_shifts = self._sign_modifiers.get(p.sign, {})
            aspect_mult = planet_aspect_multiplier(
                p.name, chart.aspects, self._aspect_weights, MAX_ORB_FOR_TIGHTNESS,
            )
            for trait, base in trait_deltas.items():
                if trait not in scores:
                    continue
                sign_shift = sign_shifts.get(trait, 0.0)
                raw = (base + sign_shift) * strength * weight * aspect_mult
                damped = raw * self._dampening
                s1[trait] += raw
                s2[trait] += damped
                scores[trait] += damped

        s3 = dict(scores)
        s4 = TraitVector.from_dict(scores)
        return s1, s2, s3, s4


def _apply_weight_floor(
    planet_weights: dict[str, float], floor: float
) -> dict[str, float]:
    return {p: max(w, floor) for p, w in planet_weights.items()}


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return (m, s)


def run_sweep(
    agents,
    dampening: float,
    weight_floor: float,
) -> dict[str, dict[str, tuple[float, float]]]:
    """Return stats[stage][trait] = (mean, std) for N agents."""
    from realm.personality.planet_traits import load_aspect_weights

    aspect_weights, default_planet_weights = load_aspect_weights()
    floored = _apply_weight_floor(default_planet_weights, weight_floor)

    embedder = InstrumentedRuleBasedEmbedder(
        aspect_weights=aspect_weights,
        planet_weights=floored,
        dampening=dampening,
    )
    culture = CulturalModifier()  # reads blend_ratio from config (0.3)

    names = TraitVector.trait_names()
    # stage -> trait -> list of values
    stage_values: dict[str, dict[str, list[float]]] = {
        stage: {n: [] for n in names}
        for stage in ("S1", "S2", "S3", "S4", "S5")
    }

    for agent in agents:
        s1, s2, s3, s4 = embedder.embed_with_stages(agent.natal_chart)
        s5 = culture.apply(s4, agent.profile)
        for n in names:
            stage_values["S1"][n].append(s1[n])
            stage_values["S2"][n].append(s2[n])
            stage_values["S3"][n].append(s3[n])
            stage_values["S4"][n].append(getattr(s4, n))
            stage_values["S5"][n].append(getattr(s5, n))

    stats: dict[str, dict[str, tuple[float, float]]] = {}
    for stage, per_trait in stage_values.items():
        stats[stage] = {n: _mean_std(per_trait[n]) for n in names}
    return stats


def _trait_avg_std(per_trait_stats: dict[str, tuple[float, float]]) -> float:
    stds = [s for (_m, s) in per_trait_stats.values()]
    return statistics.mean(stds) if stds else 0.0


def _pick_winner(
    grid: dict[tuple[float, float], dict[str, dict[str, tuple[float, float]]]],
) -> tuple[float, float]:
    """Cell whose S5 mean-over-traits σ is closest to TARGET_STD without overshoot.
    If all undershoot, pick the largest. If all overshoot, pick the smallest overshoot.
    """
    best: tuple[float, float] | None = None
    best_score = float("inf")
    for (damp, floor), stats in grid.items():
        s5_avg = _trait_avg_std(stats["S5"])
        # prefer not overshooting: distance to target, overshoot doubly penalized
        gap = TARGET_STD - s5_avg
        score = abs(gap) + (0.0 if gap >= 0 else abs(gap))
        if score < best_score:
            best_score = score
            best = (damp, floor)
    assert best is not None
    return best


def _format_heatmap(
    grid: dict[tuple[float, float], dict[str, dict[str, tuple[float, float]]]],
    stage: str = "S5",
) -> str:
    header = "             | " + " | ".join(
        f"floor={f:.2f}" for f in WEIGHT_FLOOR_VALUES
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for damp in DAMPENING_VALUES:
        row = f"damp={damp:.2f}    | "
        cells = []
        for floor in WEIGHT_FLOOR_VALUES:
            avg = _trait_avg_std(grid[(damp, floor)][stage])
            cells.append(f"   {avg:.3f}  ")
        lines.append(row + " | ".join(cells))
    return "\n".join(lines)


def _format_trait_table(
    stats: dict[str, dict[str, tuple[float, float]]],
    damp: float,
    floor: float,
) -> str:
    names = TraitVector.trait_names()
    lines = [
        "",
        f"### Full trait breakdown — dampening={damp:.2f}, weight_floor={floor:.2f}",
        "",
        "| trait | S1 µ | S1 σ | S2 σ | S4 µ | S4 σ | S5 µ | S5 σ |",
        "|-------|------|------|------|------|------|------|------|",
    ]
    for n in names:
        s1m, s1s = stats["S1"][n]
        _, s2s = stats["S2"][n]
        s4m, s4s = stats["S4"][n]
        s5m, s5s = stats["S5"][n]
        lines.append(
            f"| {n} | {s1m:+.3f} | {s1s:.3f} | {s2s:.3f} | "
            f"{s4m:.3f} | {s4s:.3f} | {s5m:.3f} | {s5s:.3f} |",
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    setup_logging(level="WARNING")
    n_agents = int(argv[1]) if len(argv) > 1 else 2000

    print(f"# REALM Trait Variance Diagnostic (N={n_agents})")
    print(f"Sweep: dampening in {list(DAMPENING_VALUES)}")
    print(f"       weight_floor in {list(WEIGHT_FLOOR_VALUES)}")
    print(f"Target std = {TARGET_STD} (Big Five adult norm on [0,1])")

    t0 = time.perf_counter()
    gen = WorldGenerator(master_seed=42)
    factory = AgentFactory()
    profiles = gen.generate(n_agents)
    agents = factory.build_batch(profiles)
    t_gen = time.perf_counter() - t0
    print(f"\nGenerated {len(agents)}/{n_agents} agents in {t_gen:.1f}s")

    grid: dict[tuple[float, float], dict[str, dict[str, tuple[float, float]]]] = {}
    total = len(DAMPENING_VALUES) * len(WEIGHT_FLOOR_VALUES)
    done = 0
    t1 = time.perf_counter()
    for damp in DAMPENING_VALUES:
        for floor in WEIGHT_FLOOR_VALUES:
            grid[(damp, floor)] = run_sweep(agents, damp, floor)
            done += 1
            print(f"  [{done}/{total}] damp={damp:.2f} floor={floor:.2f} done")
    t_sweep = time.perf_counter() - t1
    print(f"\nSweep complete in {t_sweep:.1f}s")

    print("\n## Heatmap -- mean-over-traits std at S5 (post-cultural)")
    print()
    print(_format_heatmap(grid, "S5"))

    winner = _pick_winner(grid)
    winner_avg = _trait_avg_std(grid[winner]["S5"])
    print(f"\nWinner cell: dampening={winner[0]:.2f}, weight_floor={winner[1]:.2f}")
    print(f"   mean std (S5) = {winner_avg:.3f}   (target {TARGET_STD:.2f})")

    # Sanity print: S1 vs S2 vs S4 vs S5 for default (damp=0.12, floor=0.35)
    default_stats = grid[(0.12, 0.35)]
    print("\n## Stage-by-stage avg std at default (damp=0.12, floor=0.35)")
    for stage in ("S1", "S2", "S3", "S4", "S5"):
        avg = _trait_avg_std(default_stats[stage])
        print(f"   {stage} avg std = {avg:.3f}")

    # Write markdown report
    out_dir = ROOT / "outputs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "diag_variance.md"
    lines: list[str] = []
    lines.append(f"# REALM Trait Variance Diagnostic (N={n_agents})")
    lines.append("")
    lines.append(f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Target σ: **{TARGET_STD}** (Big Five adult norm, [0,1] scale)")
    lines.append(
        f"- Winner cell: dampening=**{winner[0]:.2f}**, weight_floor=**{winner[1]:.2f}** "
        f"(S5 avg σ = {winner_avg:.3f})",
    )
    lines.append("")
    lines.append("## Heatmap — mean-over-traits σ at S5 (post-cultural)")
    lines.append("")
    lines.append("```")
    lines.append(_format_heatmap(grid, "S5"))
    lines.append("```")
    lines.append("")
    lines.append("## Stage-by-stage avg σ (across 24 traits, each sweep combo)")
    lines.append("")
    stage_hdr = "| damp | floor | " + " | ".join(
        f"{s} σ" for s in ("S1", "S2", "S3", "S4", "S5")
    ) + " |"
    stage_sep = "|------|-------|------|------|------|------|------|"
    lines.append(stage_hdr)
    lines.append(stage_sep)
    for damp in DAMPENING_VALUES:
        for floor in WEIGHT_FLOOR_VALUES:
            s = grid[(damp, floor)]
            row = f"| {damp:.2f} | {floor:.2f} "
            for stage in ("S1", "S2", "S3", "S4", "S5"):
                row += f"| {_trait_avg_std(s[stage]):.3f} "
            row += "|"
            lines.append(row)
    lines.append("")
    lines.append("## Winner cell — 24-trait full breakdown")
    lines.append(_format_trait_table(grid[winner], winner[0], winner[1]))
    lines.append("")
    lines.append("## Default cell (damp=0.12, floor=0.35) — baseline")
    lines.append(_format_trait_table(grid[(0.12, 0.35)], 0.12, 0.35))
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
