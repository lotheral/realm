"""Sprint 14 WP6 — multi-category baseline + scenario validation.

Runs one prediction per category (8 baseline) plus positive/negative scenario
runs (16 scenario), then writes a Markdown report comparing baselines,
deltas, drift caps, and political_spectrum spread (Hofstede-only vs
Hofstede + V-Dem blend).

Default scale is `--n-agents 200 --n-ticks 30 --n-branches 5` so the script
can be exercised in roughly a minute. Pass `--scale full` to bump to
10K×50×5 (the article's headline configuration). Wall-clock at full scale
extrapolates from Sprint 10's 10K×30×5 measurement (20.4 min) to roughly
34 min × 24 runs ≈ 13.6 hours — run overnight, not interactively.

Usage:
    .venv/Scripts/python.exe scripts/validate_sprint14.py
    .venv/Scripts/python.exe scripts/validate_sprint14.py --scale full
    .venv/Scripts/python.exe scripts/validate_sprint14.py --n-agents 1000 --n-ticks 50

Output:
    outputs/sprint14_validation_report.md
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Make the repo importable when invoked as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realm.api.predict import (  # noqa: E402  (path bootstrap above)
    PredictRequest,
    predict_endpoint,
)
from realm.demographics.country_data import load_hofstede  # noqa: E402
from realm.personality.adapters.demographic import (  # noqa: E402
    _political_spectrum_from_hofstede,
)

# Sample question per category for baseline differentiation. Picked to match
# each category's keyword vocabulary so CategoryRouter routes correctly
# without ambiguity. balanced is intentionally excluded — it is the fallback,
# not a measurable category.
CATEGORY_QUESTIONS: dict[str, str] = {
    "politics": "Will the incumbent president win the 2028 election?",
    "economics": "Will the Fed cut interest rates in the next quarter?",
    "crypto": "Will Bitcoin reach 200K by end of 2026?",
    "sports": "Will the Lakers win the next NBA championship final?",
    "markets": "Will the S&P 500 hit a new all-time high this year?",
    "culture": "Will the next Oscar winner be a streaming-only movie?",
    "science": "Will a major AI breakthrough be announced this quarter?",
    "geopolitics": "Will the ceasefire in Ukraine hold through next year?",
}

# NOTE: scenarios use words from `_POSITIVE_WORDS_BASE` / `_NEGATIVE_WORDS_BASE`
# (the Sprint 13 inventory), which is the only one /api/predict consults.
# DOMAIN extensions (e.g., "rugpull", "scandal") live in the combined parser
# but predict.py keeps Sprint 13 strict mode for backward compatibility, so
# scenario feeds MUST stick to the base inventory to register direction.
POSITIVE_SCENARIOS: dict[str, str] = {
    "politics": "Incumbent wins endorsement support; passes reform; gains approval and growth",
    "economics": "Federal Reserve cuts rates, dovish stimulus, easing recovery and growth",
    "crypto": "Crypto rally and gain, breakthrough adoption, growth and recovery boom",
    "sports": "Win streak, gain rally support, breakthrough recovery, decisive success",
    "markets": "Stock rally and growth, breakthrough boom, gain support, recovery",
    "culture": "Viral support and growth, breakthrough success, rally approval",
    "science": "Major breakthrough discovery, approval passes, success and growth",
    "geopolitics": "Peace agreement, ceasefire holds, diplomatic settlement, easing tensions",
}

NEGATIVE_SCENARIOS: dict[str, str] = {
    "politics": "Incumbent loses, rejected and defeated; threat of crisis warns of collapse",
    "economics": "Hawkish Federal Reserve hikes rates, tightening accelerates, prolonged crisis",
    "crypto": "Crypto crash and decline, prolonged loss, threat warns of collapse",
    "sports": "Loses defeated, decline collapse; threat of strike, prolonged crisis",
    "markets": "Stock crash and decline, prolonged loss, sanction warns of collapse",
    "culture": "Rejected and defeated; threat of strike, prolonged crisis warns",
    "science": "Crisis warns of collapse, rejected paper, prolonged decline, threat",
    "geopolitics": "Conflict and war; missile attack, sanctions, threat warns of invasion",
}


def _run_one(question: str, *, n_agents: int, n_ticks: int, n_branches: int,
             scenario: str | None = None) -> dict:
    req = PredictRequest(
        question=question,
        n_agents=n_agents,
        n_ticks=n_ticks,
        n_branches=n_branches,
        scenario_feed=scenario,
    )
    t0 = time.time()
    resp = predict_endpoint(req)
    elapsed = time.time() - t0
    return {
        "category_id": resp.category_id,
        "probability": resp.probability,
        "baseline_probability": resp.baseline_probability,
        "delta": resp.delta,
        "supporting": resp.agents_supporting,
        "opposing": resp.agents_opposing,
        "neutral": resp.agents_neutral,
        "max_trait_shift": max(
            (abs(v) for v in resp.trait_shifts.values()),
            default=0.0,
        ),
        "elapsed_s": elapsed,
    }


def _political_spectrum_stats() -> dict[str, dict[str, float]]:
    countries = list(load_hofstede().keys())
    hof_only = [_political_spectrum_from_hofstede(c, use_vdem=False) for c in countries]
    blend = [_political_spectrum_from_hofstede(c, use_vdem=True) for c in countries]

    def stats(xs: list[float]) -> dict[str, float]:
        return {
            "min": round(min(xs), 4),
            "max": round(max(xs), 4),
            "mean": round(statistics.mean(xs), 4),
            "stdev": round(statistics.pstdev(xs), 4),
            "spread": round(max(xs) - min(xs), 4),
        }

    return {
        "hofstede_only": stats(hof_only),
        "hofstede_vdem_blend": stats(blend),
    }


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(num / (dx * dy), 4) if dx * dy else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-agents", type=int, default=200)
    ap.add_argument("--n-ticks", type=int, default=30)
    ap.add_argument("--n-branches", type=int, default=5)
    ap.add_argument("--scale", choices=("default", "full", "smoke"), default="default",
                    help="default=200×30×5 (~1 min), smoke=50×5×2 (instant), "
                         "full=10K×50×5 (~13 hours, run overnight)")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "outputs" / "sprint14_validation_report.md")
    args = ap.parse_args()

    if args.scale == "full":
        args.n_agents, args.n_ticks, args.n_branches = 10_000, 50, 5
    elif args.scale == "smoke":
        args.n_agents, args.n_ticks, args.n_branches = 50, 5, 2

    print(f"Sprint 14 validation @ {args.n_agents}x{args.n_ticks}x{args.n_branches}")
    print(f"  output -> {args.output}")

    started = datetime.utcnow()
    baseline_results: dict[str, dict] = {}
    scenario_results: dict[str, dict[str, dict]] = {}
    total_t0 = time.time()

    for cat, question in CATEGORY_QUESTIONS.items():
        print(f"  [{cat}] baseline: {question[:60]}...", flush=True)
        baseline_results[cat] = _run_one(
            question,
            n_agents=args.n_agents,
            n_ticks=args.n_ticks,
            n_branches=args.n_branches,
        )
        print(f"      P={baseline_results[cat]['probability']:.3f} "
              f"({baseline_results[cat]['elapsed_s']:.1f}s)")
        scenario_results[cat] = {}
        for label, feed_map in (("positive", POSITIVE_SCENARIOS),
                                ("negative", NEGATIVE_SCENARIOS)):
            print(f"  [{cat}] scenario {label}", flush=True)
            scenario_results[cat][label] = _run_one(
                question,
                n_agents=args.n_agents,
                n_ticks=args.n_ticks,
                n_branches=args.n_branches,
                scenario=feed_map[cat],
            )
            res = scenario_results[cat][label]
            print(f"      P={res['probability']:.3f} delta={res['delta']:+.3f} "
                  f"({res['elapsed_s']:.1f}s)")

    total_elapsed = time.time() - total_t0
    ps_stats = _political_spectrum_stats()

    # Compute headline metrics.
    baseline_probs = [r["probability"] for r in baseline_results.values()]
    baseline_spread = max(baseline_probs) - min(baseline_probs)
    max_drift_seen = max(r["max_trait_shift"] for r in baseline_results.values())
    for sm in scenario_results.values():
        for r in sm.values():
            max_drift_seen = max(max_drift_seen, r["max_trait_shift"])

    # Direction consistency: positive scenario should raise probability,
    # negative should lower it (vs baseline).
    direction_ok: list[str] = []
    direction_violations: list[str] = []
    for cat, sm in scenario_results.items():
        bp = baseline_results[cat]["probability"]
        if sm["positive"]["probability"] >= bp and sm["negative"]["probability"] <= bp:
            direction_ok.append(cat)
        else:
            direction_violations.append(
                f"{cat}: baseline={bp:.3f}, positive={sm['positive']['probability']:.3f}, "
                f"negative={sm['negative']['probability']:.3f}"
            )

    # Render report.
    lines: list[str] = []
    lines.append(f"# Sprint 14 Validation Report — {started.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("Generated by `scripts/validate_sprint14.py`.")
    lines.append(f"- Scale: **{args.n_agents} agents × {args.n_ticks} ticks × "
                 f"{args.n_branches} branches**")
    lines.append(f"- Wall-clock: **{total_elapsed:.1f} s** for "
                 f"{len(CATEGORY_QUESTIONS)} baseline + "
                 f"{len(CATEGORY_QUESTIONS) * 2} scenario = "
                 f"{len(CATEGORY_QUESTIONS) * 3} predictions")
    lines.append("")

    lines.append("## Acceptance gates")
    lines.append("")
    lines.append(f"- Baseline spread: **{baseline_spread:.3f}** "
                 f"(target ≥ 0.10) "
                 f"{'✅' if baseline_spread >= 0.10 else '⚠️ below target'}")
    lines.append(f"- Max trait_shift across all runs: **{max_drift_seen:.4f}** "
                 f"(cap 0.10) "
                 f"{'✅' if max_drift_seen <= 0.10 else '❌ exceeds cap'}")
    lines.append(f"- Scenario direction consistency: "
                 f"**{len(direction_ok)}/{len(CATEGORY_QUESTIONS)}** categories "
                 f"behaved as expected "
                 f"{'✅' if not direction_violations else '⚠️'}")
    lines.append(f"- political_spectrum spread (V-Dem blend): "
                 f"**{ps_stats['hofstede_vdem_blend']['spread']:.4f}** "
                 f"(Sprint 11 Hofstede-only baseline 0.41) "
                 f"{'✅' if ps_stats['hofstede_vdem_blend']['spread'] > 0.41 else '⚠️'}")
    if direction_violations:
        lines.append("")
        lines.append("Direction violations:")
        for v in direction_violations:
            lines.append(f"- {v}")
    lines.append("")

    lines.append("## Baseline differentiation across 8 categories")
    lines.append("")
    lines.append("| category | probability | sup% | opp% | neu% | max trait_shift |")
    lines.append("|----------|-------------|------|------|------|-----------------|")
    for cat, r in baseline_results.items():
        lines.append(
            f"| {cat} | {r['probability']:.4f} "
            f"| {r['supporting']*100:.1f} | {r['opposing']*100:.1f} "
            f"| {r['neutral']*100:.1f} | {r['max_trait_shift']:.4f} |"
        )
    lines.append("")

    lines.append("## Scenario deltas")
    lines.append("")
    lines.append("| category | baseline | positive P | pos delta | "
                 "negative P | neg delta |")
    lines.append("|----------|----------|------------|-----------|"
                 "------------|-----------|")
    for cat in CATEGORY_QUESTIONS:
        bp = baseline_results[cat]["probability"]
        pos = scenario_results[cat]["positive"]
        neg = scenario_results[cat]["negative"]
        lines.append(
            f"| {cat} | {bp:.4f} | {pos['probability']:.4f} | "
            f"{(pos['delta'] or 0.0):+.4f} | {neg['probability']:.4f} | "
            f"{(neg['delta'] or 0.0):+.4f} |"
        )
    lines.append("")

    lines.append("## political_spectrum: Hofstede-only vs Hofstede + V-Dem blend")
    lines.append("")
    lines.append("| metric | Hofstede-only | Hofstede + V-Dem |")
    lines.append("|--------|---------------|------------------|")
    for k in ("min", "max", "mean", "stdev", "spread"):
        h = ps_stats["hofstede_only"][k]
        b = ps_stats["hofstede_vdem_blend"][k]
        lines.append(f"| {k} | {h:.4f} | {b:.4f} |")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- The full-scale run (`--scale full`, 10K×50×5) extrapolates from "
                 "Sprint 10's 10K×30×5 wall-clock (20.4 min) to roughly **34 min × 24 "
                 "runs ≈ 13.6 hours**. Run overnight, not interactively.")
    lines.append("- Baseline spread under WP1+WP2 is the headline acceptance gate — "
                 "if < 0.05 at this scale, the drift_event_weights and "
                 "trait_seed_offsets in `config/prediction_categories.json` need "
                 "re-tuning before merge.")
    lines.append("- All `trait_shifts` are bounded by the `max_drift_ratio=0.10` cap "
                 "in `realm/simulation/drift.py` — a value >= 0.10 indicates a code "
                 "regression in the cumulative clamp, not a calibration issue.")
    lines.append("")
    lines.append("### Known calibration limitation")
    lines.append("")
    lines.append("At scales below 1000 agents, baseline differentiation between "
                 "categories is dominated by the `positive_social_fallback` / "
                 "`negative_social_fallback` rules in `config/drift_events.json`, "
                 "which fire on every agent post regardless of category. "
                 "WP1 weighting of these two events controls most of the signal, "
                 "and most categories currently use `pos:neg = 1:1` so the net "
                 "drift cancels. To widen the baseline spread without altering "
                 "the global drift physics, future calibration should:")
    lines.append("")
    lines.append("1. Skew the `positive_social` / `negative_social` weights per "
                 "category (e.g., culture should have pos > neg, geopolitics neg > pos). "
                 "The current Sprint 14 v0 weights are intentionally conservative.")
    lines.append("2. Add category-conditioned topic biasing in agent decisions so "
                 "the topic-specific rules (financial_gain_post, leadership_act, etc.) "
                 "fire more often, exposing the WP1 weighted-sample path.")
    lines.append("3. Re-run validation at scale 1000+ to let drift accumulate above "
                 "the noise floor (`max_drift_ratio=0.10` cap).")
    lines.append("")
    lines.append("Sprint 14 ships with the WP1 sampling MACHINERY and the schema; "
                 "calibration depth is deferred to a post-release tuning sprint "
                 "informed by full-scale 10K×50 runs and live A/B comparison "
                 "against Polymarket prediction markets.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
