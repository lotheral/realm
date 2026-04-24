"""Phase 4 validation: full trait-distribution report.

Runs 10K agents through the full pipeline twice:
  - pre-calibration (trait_calibration.enabled forced false)
  - post-calibration (trait_calibration.enabled forced true)

For each trait: mean, std, skew, kurtosis, ASCII histogram. Plus the
full 24x24 Pearson correlation matrix. Big Five subset is compared
against literature norms; domain traits are compared only against
REALM design targets (explicitly flagged as "no external ground truth").

Output
------
    outputs/trait_validation.md
"""

from __future__ import annotations

import contextlib as _ctx
import math
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
from realm.personality.calibration import TraitCalibrator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

BIG_FIVE = ("openness", "conscientiousness", "extraversion",
            "agreeableness", "neuroticism")

# Known Big Five adult intercorrelations (0-1 scale, approximate sign/magnitude).
# Signs are the invariant we care about; magnitudes shift across studies.
BF_KNOWN_CORR = {
    ("neuroticism", "conscientiousness"): -0.25,
    ("neuroticism", "extraversion"): -0.20,
    ("openness", "extraversion"): +0.15,
    ("conscientiousness", "agreeableness"): +0.20,
    ("extraversion", "agreeableness"): +0.15,
}

TARGET_STD_MIN = 0.14
TARGET_STD_TARGET = 0.17


def _moments(vals: list[float]) -> tuple[float, float, float, float]:
    """mean, std, skew, kurtosis (excess, biased estimator)."""
    n = len(vals)
    if n < 2:
        return (vals[0] if vals else 0.0, 0.0, 0.0, 0.0)
    m = statistics.mean(vals)
    s = statistics.stdev(vals)
    if s < 1e-9:
        return (m, 0.0, 0.0, 0.0)
    # skew
    skew = sum((v - m) ** 3 for v in vals) / (n * s ** 3)
    # excess kurtosis
    kurt = sum((v - m) ** 4 for v in vals) / (n * s ** 4) - 3.0
    return (m, s, skew, kurt)


def _ascii_histogram(vals: list[float], bins: int = 20, width: int = 30) -> str:
    lo, hi = 0.0, 1.0
    counts = [0] * bins
    for v in vals:
        idx = min(bins - 1, max(0, int((v - lo) / (hi - lo) * bins)))
        counts[idx] += 1
    m = max(counts) if counts else 1
    lines = []
    for i, c in enumerate(counts):
        edge = lo + i * (hi - lo) / bins
        bar = "#" * int(c / m * width) if m > 0 else ""
        lines.append(f"    [{edge:.2f}] {bar} ({c})")
    return "\n".join(lines)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-9 or dy < 1e-9:
        return 0.0
    return num / (dx * dy)


def _run_pipeline(
    n_agents: int, enable_calibration: bool, seed: int,
    adapter_type: str = "astrological",
) -> dict[str, list[float]]:
    """Return {trait: [value for each agent]}."""
    from realm.personality.adapters import get_input_adapter

    gen = WorldGenerator(master_seed=seed)
    profiles = gen.generate(n_agents)

    if enable_calibration:
        # Force calibrator on regardless of config; adapter-aware stats path.
        calibrator = TraitCalibrator(
            enabled=True,
            target_mean=0.50,
            target_std=0.17,
            adapter_type=adapter_type,
        )
    else:
        # Force calibrator off regardless of config
        calibrator = TraitCalibrator(enabled=False)

    adapter = get_input_adapter(adapter_type)
    factory = AgentFactory(calibrator=calibrator, adapter=adapter)
    agents = factory.build_batch(profiles)

    data: dict[str, list[float]] = {n: [] for n in TraitVector.trait_names()}
    for a in agents:
        for n in TraitVector.trait_names():
            data[n].append(getattr(a.traits, n))
    return data


def _format_section(
    label: str, data: dict[str, list[float]], bf_only: bool,
) -> list[str]:
    names = BIG_FIVE if bf_only else tuple(
        n for n in TraitVector.trait_names() if n not in BIG_FIVE
    )
    lines = []
    lines.append(f"\n### {label}")
    lines.append("")
    lines.append(
        "| trait | mean | std | skew | kurtosis | meets std target? |",
    )
    lines.append("|-------|------|-----|------|----------|-------------------|")
    for n in names:
        m, s, sk, kt = _moments(data[n])
        ok = "yes" if s >= TARGET_STD_MIN else "no"
        lines.append(
            f"| {n} | {m:.3f} | {s:.3f} | {sk:+.2f} | {kt:+.2f} | {ok} |",
        )
    return lines


def main(argv: list[str]) -> int:
    setup_logging(level="WARNING")
    # Parse args: first positional = N, optional --adapter=<type>
    n_agents = 10000
    adapter_type = "astrological"
    for arg in argv[1:]:
        if arg.startswith("--adapter="):
            adapter_type = arg.split("=", 1)[1].strip()
        elif arg.isdigit():
            n_agents = int(arg)

    print(f"Running trait-distribution validation at N={n_agents}, adapter={adapter_type}...")

    # Seed chosen deliberately different from calibration-stats builder (7 vs 42)
    # to avoid fitting calibration to its own reference distribution.
    t0 = time.perf_counter()
    pre_cal = _run_pipeline(
        n_agents, enable_calibration=False, seed=42, adapter_type=adapter_type,
    )
    t_pre = time.perf_counter() - t0
    print(f"Pre-calibration run: {t_pre:.1f}s")

    post_cal = _run_pipeline(
        n_agents, enable_calibration=True, seed=42, adapter_type=adapter_type,
    )
    t_post = time.perf_counter() - t0 - t_pre
    print(f"Post-calibration run: {t_post:.1f}s")

    # Section D: correlations
    def _corr_matrix(data: dict[str, list[float]]) -> dict:
        names = TraitVector.trait_names()
        return {
            (a, b): _pearson(data[a], data[b])
            for a in names for b in names
        }

    corr_pre = _corr_matrix(pre_cal)
    corr_post = _corr_matrix(post_cal)

    # Build report
    lines: list[str] = []
    lines.append(f"# REALM Trait Distribution Validation (N={n_agents})")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Target std: {TARGET_STD_TARGET} (Big Five adult norm on [0,1])")
    lines.append(
        f"Pass threshold for individual trait: std >= {TARGET_STD_MIN}",
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    for label, data in (("Pre-calibration", pre_cal),
                        ("Post-calibration", post_cal)):
        stds = [_moments(data[n])[1] for n in TraitVector.trait_names()]
        avg_std = statistics.mean(stds)
        pass_count = sum(1 for s in stds if s >= TARGET_STD_MIN)
        lines.append(
            f"- **{label}**: mean trait std = {avg_std:.3f}, "
            f"{pass_count}/24 traits >= {TARGET_STD_MIN}",
        )
    lines.append("")

    # Phase 3 decision gate eval
    stds_pre = [_moments(pre_cal[n])[1] for n in TraitVector.trait_names()]
    avg_pre = statistics.mean(stds_pre)
    stds_post = [_moments(post_cal[n])[1] for n in TraitVector.trait_names()]
    avg_post = statistics.mean(stds_post)
    lines.append("## Phase 3 decision gate")
    lines.append("")
    if avg_pre >= 0.15:
        decision = "**Defer Phase 3** â€” source fix reached target."
    elif avg_pre >= 0.10:
        decision = "**Proceed with Phase 3** â€” source fix got most of the way; calibration closes the gap."
    else:
        decision = "**Escalate** â€” source fix alone didn't reach 0.10; investigate."
    lines.append(f"Pre-calibration mean std = {avg_pre:.3f} -> {decision}")
    lines.append(f"Post-calibration mean std = {avg_post:.3f}")
    lines.append("")

    # Section A: Big Five vs literature
    lines.append("## Section A â€” Big Five (literature-validatable)")
    lines.append("")
    lines.append("Expected: mean~0.50, std in [0.15, 0.20] per Costa & McCrae norms.")
    lines.append("Means far from 0.50 indicate systematic bias in the raw astrology mapping.")
    lines.extend(_format_section("Pre-calibration", pre_cal, bf_only=True))
    lines.extend(_format_section("Post-calibration", post_cal, bf_only=True))

    # Section B: Domain traits (REALM design target only)
    lines.append("\n## Section B â€” Domain traits (no external ground truth)")
    lines.append("")
    lines.append(
        "These 19 traits have no population norm in the literature. "
        "Target std=0.17 is a REALM design choice, not an empirical benchmark. "
        "Interpret std alignment as 'model behaves as specified', not 'model matches reality'.",
    )
    lines.extend(_format_section("Pre-calibration", pre_cal, bf_only=False))
    lines.extend(_format_section("Post-calibration", post_cal, bf_only=False))

    # Section C: known correlation signs
    lines.append("\n## Section C â€” Big Five intercorrelation signs")
    lines.append("")
    lines.append(
        "Literature holds these pairs have specific signs. "
        "Wrong sign = mapping produces an implausible personality structure.",
    )
    lines.append("")
    lines.append("| pair | expected | pre-cal | post-cal | sign OK pre | sign OK post |")
    lines.append("|------|----------|---------|----------|-------------|--------------|")
    for (a, b), expected in BF_KNOWN_CORR.items():
        pre_r = corr_pre[(a, b)]
        post_r = corr_post[(a, b)]
        sign_exp = 1 if expected > 0 else -1
        ok_pre = (pre_r * sign_exp) > 0
        ok_post = (post_r * sign_exp) > 0
        lines.append(
            f"| {a}~{b} | {expected:+.2f} | {pre_r:+.3f} | {post_r:+.3f} | "
            f"{'yes' if ok_pre else 'NO'} | {'yes' if ok_post else 'NO'} |",
        )

    # Section D: histograms for selected traits
    lines.append("\n## Section D â€” Histograms (selected traits)")
    lines.append("")
    lines.append(
        "ASCII histograms, 20 bins across [0, 1]. Real personality "
        "distributions aren't strictly normal; skew/bimodality is "
        "expected, not a failure.",
    )
    for n in ("openness", "neuroticism", "risk_appetite", "empathy"):
        lines.append(f"\n### {n}")
        lines.append("```")
        lines.append("PRE-CALIBRATION")
        lines.append(_ascii_histogram(pre_cal[n]))
        lines.append("")
        lines.append("POST-CALIBRATION")
        lines.append(_ascii_histogram(post_cal[n]))
        lines.append("```")

    # Section E: clamp saturation comparison
    lines.append("\n## Section E â€” Clamp saturation")
    lines.append("")
    lines.append("Fraction of trait values hitting 0.0 or 1.0 exactly.")
    for label, data in (("Pre-calibration", pre_cal),
                        ("Post-calibration", post_cal)):
        total = 0
        hits = 0
        for n in TraitVector.trait_names():
            for v in data[n]:
                total += 1
                if v <= 0.001 or v >= 0.999:
                    hits += 1
        pct = 100 * hits / max(total, 1)
        lines.append(f"- {label}: {hits}/{total} ({pct:.1f}%)")

    # Write â€” separate file per adapter so measurements are preserved
    suffix = "" if adapter_type == "astrological" else f"_{adapter_type}"
    out_path = ROOT / "outputs" / f"trait_validation{suffix}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {out_path}")

    # Stdout summary
    print()
    print(f"Pre-cal  mean std: {avg_pre:.3f}  ({sum(1 for s in stds_pre if s >= TARGET_STD_MIN)}/24 >= {TARGET_STD_MIN})")
    print(f"Post-cal mean std: {avg_post:.3f}  ({sum(1 for s in stds_post if s >= TARGET_STD_MIN)}/24 >= {TARGET_STD_MIN})")
    print()
    print("Big Five correlation sign check (post-cal):")
    for (a, b), expected in BF_KNOWN_CORR.items():
        r = corr_post[(a, b)]
        ok = "OK" if (r * (1 if expected > 0 else -1)) > 0 else "WRONG"
        print(f"   {a}~{b}: expected {expected:+.2f}, got {r:+.3f}  [{ok}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
