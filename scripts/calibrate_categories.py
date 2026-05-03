"""Sprint 15 WP5 — calibration tuning script.

Runs each non-balanced category N times with its representative question,
collects the mean baseline probability ± std per category, prints a table,
and reports the spread (max mean − min mean across categories). The
acceptance gate is **spread ≥ 3pp**; if below, the script suggests which
config knob to widen.

Usage:
    .venv/Scripts/python.exe scripts/calibrate_categories.py
    .venv/Scripts/python.exe scripts/calibrate_categories.py --runs 10 --agents 200 --ticks 30 --branches 5
    .venv/Scripts/python.exe scripts/calibrate_categories.py --output outputs/sprint15_calibration_log.md

Each run uses a different master_seed (seeded deterministically from the run
index) so the per-category std reflects population-level variability, not
RNG drift.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Sprint 17 WP6: protect calibration determinism. The Sprint 16 numbers
# (geopolitics 49.20%, spread 4.14pp, etc.) depend on the simulation
# mechanics alone — no LLM involvement. If a dev sets
# REALM_LLM_CATEGORY_BACKEND in their shell and runs this script, the
# LLM-first routing + question / scenario / narrative analyzers would
# fire, slow runs by 100×, and potentially shift baselines. We defensively
# clear the env var BEFORE any realm.* import so calibration is always
# LLM-free regardless of the caller's environment.
os.environ.pop("REALM_LLM_CATEGORY_BACKEND", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realm.api.predict import PredictRequest, predict_endpoint  # noqa: E402

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

SPREAD_TARGET = 0.03  # 3pp


def _run_one(question: str, *, n_agents: int, n_ticks: int, n_branches: int,
             master_seed: int) -> dict[str, float]:
    req = PredictRequest(
        question=question,
        n_agents=n_agents,
        n_ticks=n_ticks,
        n_branches=n_branches,
        master_seed=master_seed,
    )
    resp = predict_endpoint(req)
    return {
        "category_id": resp.category_id,
        "probability": resp.probability,
        "supporting": resp.agents_supporting,
        "opposing": resp.agents_opposing,
        "neutral": resp.agents_neutral,
    }


def _summary_line(cat: str, probs: list[float]) -> str:
    mean = statistics.mean(probs)
    std = statistics.pstdev(probs) if len(probs) > 1 else 0.0
    return (
        f"  {cat:>11s}  mean={mean*100:6.2f}%  std={std*100:5.2f}pp  "
        f"min={min(probs)*100:5.2f}%  max={max(probs)*100:5.2f}%  n={len(probs)}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=200)
    ap.add_argument("--ticks", type=int, default=30)
    ap.add_argument("--branches", type=int, default=5)
    ap.add_argument("--runs", type=int, default=5,
                    help="number of independent runs per category (different seeds)")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "outputs" / "sprint15_calibration_log.md")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    started = datetime.utcnow()
    if not args.quiet:
        print(f"Sprint 15 calibration @ {args.agents}×{args.ticks}×{args.branches}, "
              f"{args.runs} runs/category")

    per_cat: dict[str, list[dict[str, float]]] = {c: [] for c in CATEGORY_QUESTIONS}
    t0 = time.time()
    for run_i in range(args.runs):
        seed = 42 + 1009 * run_i
        for cat, question in CATEGORY_QUESTIONS.items():
            res = _run_one(question, n_agents=args.agents, n_ticks=args.ticks,
                           n_branches=args.branches, master_seed=seed)
            per_cat[cat].append(res)
            if not args.quiet:
                print(f"  run {run_i+1}/{args.runs} [{cat:>11s}] "
                      f"P={res['probability']*100:6.2f}%", flush=True)

    elapsed = time.time() - t0

    # Compute per-category stats.
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for cat, runs in per_cat.items():
        probs = [r["probability"] for r in runs]
        means[cat] = statistics.mean(probs)
        stds[cat] = statistics.pstdev(probs) if len(probs) > 1 else 0.0

    spread = max(means.values()) - min(means.values())
    spread_ok = spread >= SPREAD_TARGET

    # Per-category sanity rules from the prompt.
    sanity: list[str] = []
    if "crypto" in stds and "politics" in stds:
        if stds["crypto"] > stds["politics"]:
            sanity.append("✅ crypto std > politics std (volatility ordering)")
        else:
            sanity.append(
                f"❌ crypto std ({stds['crypto']*100:.2f}pp) "
                f"≤ politics std ({stds['politics']*100:.2f}pp)"
            )
    if "geopolitics" in means:
        if means["geopolitics"] < 0.50:
            sanity.append("✅ geopolitics mean < 50% (status quo bias)")
        else:
            sanity.append(
                f"⚠️ geopolitics mean {means['geopolitics']*100:.2f}% ≥ 50% — "
                f"asymmetry not biting"
            )
    if "science" in means:
        if means["science"] > 0.50:
            sanity.append("✅ science mean > 50% (progress bias)")
        else:
            sanity.append(
                f"⚠️ science mean {means['science']*100:.2f}% ≤ 50% — "
                f"asymmetry not biting"
            )

    # Render report.
    lines: list[str] = []
    lines.append(f"# Sprint 15 Calibration Log — {started.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append(f"Scale: {args.agents} agents × {args.ticks} ticks × "
                 f"{args.branches} branches × {args.runs} runs/category")
    lines.append(f"Wall-clock: {elapsed:.1f}s")
    lines.append("")
    lines.append("## Per-category baseline probability (mean / std / range)")
    lines.append("")
    lines.append("| category | mean | std | min | max | n |")
    lines.append("|----------|------|-----|-----|-----|---|")
    for cat, runs in per_cat.items():
        probs = [r["probability"] for r in runs]
        lines.append(
            f"| {cat} | {means[cat]*100:.2f}% | {stds[cat]*100:.2f}pp | "
            f"{min(probs)*100:.2f}% | {max(probs)*100:.2f}% | {len(probs)} |"
        )
    lines.append("")
    lines.append("## Acceptance gates")
    lines.append("")
    lines.append(f"- **Spread**: max(mean) − min(mean) = "
                 f"**{spread*100:.2f}pp** "
                 f"(target ≥ {SPREAD_TARGET*100:.0f}pp) "
                 f"{'✅' if spread_ok else '❌'}")
    if means:
        argmax = max(means, key=lambda k: means[k])
        argmin = min(means, key=lambda k: means[k])
        lines.append(f"  - widest baseline: **{argmax}** {means[argmax]*100:.2f}%")
        lines.append(f"  - narrowest baseline: **{argmin}** {means[argmin]*100:.2f}%")
    lines.append("")
    for s in sanity:
        lines.append(f"- {s}")
    lines.append("")

    if not spread_ok:
        lines.append("## Recommendation if spread < 3pp")
        lines.append("")
        lines.append("Iterate `config/prediction_categories.json` in this order:")
        lines.append("")
        lines.append("1. Increase the asymmetry magnitude on the extremes:")
        lines.append("   - geopolitics: pos→0.7, neg→1.3 (currently 0.8/1.2)")
        lines.append("   - science: pos→1.25, neg→0.75 (currently 1.15/0.85)")
        lines.append("   - politics: pos→0.75, neg→1.25 (currently 0.85/1.15)")
        lines.append("2. Push drift_volatility further apart:")
        lines.append("   - crypto: 1.6 instead of 1.4")
        lines.append("   - politics: 0.6 instead of 0.7")
        lines.append("3. Match sigmoid_sensitivity_multiplier to drift_volatility "
                     "(they are independent fields but should usually move together).")
        lines.append("4. If still under target, drop n_agents below 200 only as a "
                     "last resort; small populations amplify noise but don't carry "
                     "real differentiation signal.")
        lines.append("")

    lines.append("## Per-category bucket breakdown")
    lines.append("")
    lines.append("Average supporting / opposing / neutral % across runs:")
    lines.append("")
    lines.append("| category | sup% | opp% | neu% |")
    lines.append("|----------|------|------|------|")
    for cat, runs in per_cat.items():
        sup = statistics.mean(r["supporting"] for r in runs)
        opp = statistics.mean(r["opposing"] for r in runs)
        neu = statistics.mean(r["neutral"] for r in runs)
        lines.append(f"| {cat} | {sup*100:.1f} | {opp*100:.1f} | {neu*100:.1f} |")
    lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")

    if not args.quiet:
        print()
        print(_summary_line.__doc__ or "")
        for cat, runs in per_cat.items():
            print(_summary_line(cat, [r["probability"] for r in runs]))
        print()
        print(f"SPREAD = {spread*100:.2f}pp  "
              f"(target >= {SPREAD_TARGET*100:.0f}pp)  "
              f"{'PASS' if spread_ok else 'FAIL'}")
        print(f"Report: {args.output}")
    return 0 if spread_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
