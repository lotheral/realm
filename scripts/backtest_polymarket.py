"""Sprint 18 WP1 — Polymarket backtesting script.

Fetches resolved Polymarket markets, runs each through three REALM
prediction modes (LLM+sim blended, LLM-only, sim-only), records Brier
scores against the actual outcome, and writes a markdown report.

Critical question: does the simulation add value over LLM-only?
The report's "Comparison" table answers it explicitly.

Usage::

    .venv/Scripts/python.exe scripts/backtest_polymarket.py \\
        --markets 20 --agents 100 --ticks 30 --branches 5

Loads .env automatically (Sprint 17 module-level load_dotenv) so the
LLM backend is wired without extra setup.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env early so REALM_LLM_CATEGORY_BACKEND + API keys are visible
# to the LLMRouter constructed during predict_endpoint import.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from realm.api.predict import PredictRequest, predict_endpoint  # noqa: E402
from realm.validation.polymarket import (  # noqa: E402
    BrierResult,
    PolymarketClient,
    aggregate_brier,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backtest")


def _run_one(
    question: str,
    *,
    n_agents: int,
    n_ticks: int,
    n_branches: int,
    master_seed: int,
    use_llm: bool,
    use_sim: bool,
) -> float:
    """Run predict_endpoint with the requested mode and return the
    final probability (already 4-decimal rounded by the API)."""
    req = PredictRequest(
        question=question,
        n_agents=n_agents,
        n_ticks=n_ticks,
        n_branches=n_branches,
        master_seed=master_seed,
        use_llm=use_llm,
        use_sim=use_sim,
    )
    return float(predict_endpoint(req).probability)


def run_backtest(
    n_markets: int,
    n_agents: int,
    n_ticks: int,
    n_branches: int,
    min_volume: float,
    master_seed: int,
) -> list[BrierResult]:
    client = PolymarketClient()
    logger.info("Fetching up to %d resolved markets (min_volume=$%s)",
                n_markets, f"{min_volume:,.0f}")
    markets = client.fetch_resolved_markets(
        limit=n_markets, min_volume=min_volume,
    )
    client.close()
    logger.info("Got %d clean resolved markets", len(markets))
    if not markets:
        return []

    results: list[BrierResult] = []
    for i, market in enumerate(markets, 1):
        outcome_label = "YES" if market.outcome else "NO"
        question_short = market.question[:80]
        logger.info("[%d/%d] (%s) %s", i, len(markets), outcome_label, question_short)
        t0 = time.time()
        try:
            realm_prob = _run_one(
                market.question,
                n_agents=n_agents, n_ticks=n_ticks, n_branches=n_branches,
                master_seed=master_seed,
                use_llm=True, use_sim=True,
            )
            llm_prob = _run_one(
                market.question,
                n_agents=n_agents, n_ticks=n_ticks, n_branches=n_branches,
                master_seed=master_seed,
                use_llm=True, use_sim=False,
            )
            sim_prob = _run_one(
                market.question,
                n_agents=n_agents, n_ticks=n_ticks, n_branches=n_branches,
                master_seed=master_seed,
                use_llm=False, use_sim=True,
            )
        except Exception as e:
            logger.warning("  prediction failed: %s — skipping market", e)
            continue
        elapsed = time.time() - t0
        results.append(BrierResult(
            question=market.question,
            condition_id=market.condition_id,
            actual_outcome=market.outcome,
            polymarket_price=market.final_price_yes,
            realm_probability=realm_prob,
            llm_only_probability=llm_prob,
            sim_only_probability=sim_prob,
            realm_brier=BrierResult.brier(realm_prob, market.outcome),
            llm_only_brier=BrierResult.brier(llm_prob, market.outcome),
            sim_only_brier=BrierResult.brier(sim_prob, market.outcome),
            polymarket_brier=BrierResult.brier(market.final_price_yes, market.outcome),
        ))
        logger.info(
            "  realm=%.3f  llm=%.3f  sim=%.3f  poly=%.3f  briers=%.3f/%.3f/%.3f/%.3f  (%.1fs)",
            realm_prob, llm_prob, sim_prob, market.final_price_yes,
            results[-1].realm_brier, results[-1].llm_only_brier,
            results[-1].sim_only_brier, results[-1].polymarket_brier,
            elapsed,
        )
    return results


def render_report(
    results: list[BrierResult],
    *,
    n_agents: int, n_ticks: int, n_branches: int,
    started: datetime, elapsed_sec: float,
) -> str:
    if not results:
        return "# REALM Polymarket Backtest Report\n\nNo markets fetched.\n"

    agg = aggregate_brier(results)
    lines: list[str] = []
    lines.append(
        f"# REALM Polymarket Backtest Report — {started.strftime('%Y-%m-%d %H:%M UTC')}",
    )
    lines.append("")
    lines.append(
        f"Markets evaluated: **{len(results)}**  ·  "
        f"Scale: {n_agents} agents × {n_ticks} ticks × {n_branches} branches  ·  "
        f"Wall-clock: {elapsed_sec:.1f}s ({elapsed_sec/max(1,len(results)):.1f}s/market)",
    )
    lines.append("")

    lines.append("## Brier scores (lower is better; perfect = 0, worst = 1)")
    lines.append("")
    lines.append(
        "> **Methodology caveat (Sprint 19):** Polymarket's Brier score is "
        "computed using the settlement price (the resolution outcome), "
        "not the last pre-resolution trading price. This understates "
        "Polymarket's true prediction error and gives it an unrealistic "
        "advantage in the table below. Sprint 20 backlog: fetch the "
        "CLOB prices-history endpoint to use the last pre-resolution "
        "trading price instead.",
    )
    lines.append("")
    lines.append("| Method          | Mean   | Median | Std    | n  |")
    lines.append("|-----------------|--------|--------|--------|----|")
    for label, key in (
        ("Polymarket",      "polymarket"),
        ("REALM (LLM+sim)", "realm"),
        ("LLM only",        "llm_only"),
        ("Sim only",        "sim_only"),
    ):
        a = agg[key]
        lines.append(
            f"| {label:<15s} | {a['mean']:.4f} | {a['median']:.4f} | "
            f"{a['std']:.4f} | {a['n']:>2d} |",
        )
    lines.append("")

    # Critical comparison: does sim add value?
    realm_brier = agg["realm"]["mean"]
    llm_brier = agg["llm_only"]["mean"]
    diff = realm_brier - llm_brier  # positive = sim hurts; negative = sim helps
    if diff < -0.005:
        verdict = "✅ Simulation ADDS VALUE — blended is meaningfully better than LLM-only."
    elif diff > 0.005:
        verdict = "❌ Simulation HURTS — LLM-only would be more accurate."
    else:
        verdict = "⚠️  Simulation is INDISTINGUISHABLE from noise — adds no measurable signal."

    lines.append("## Does the simulation add value?")
    lines.append("")
    lines.append(f"**Brier(LLM+sim) − Brier(LLM-only) = {diff:+.4f}**")
    lines.append("")
    lines.append(verdict)
    lines.append("")

    # Sample worst predictions for each method
    lines.append("## Worst REALM predictions (highest Brier)")
    lines.append("")
    worst = sorted(results, key=lambda r: r.realm_brier, reverse=True)[:5]
    for r in worst:
        lines.append(
            f"- ({'YES' if r.actual_outcome else 'NO'}) realm={r.realm_probability:.2f} "
            f"poly={r.polymarket_price:.2f}  brier={r.realm_brier:.3f}  "
            f"\"{r.question[:100]}\"",
        )
    lines.append("")

    lines.append("## Best REALM predictions (lowest Brier)")
    lines.append("")
    best = sorted(results, key=lambda r: r.realm_brier)[:5]
    for r in best:
        lines.append(
            f"- ({'YES' if r.actual_outcome else 'NO'}) realm={r.realm_probability:.2f} "
            f"poly={r.polymarket_price:.2f}  brier={r.realm_brier:.3f}  "
            f"\"{r.question[:100]}\"",
        )
    lines.append("")

    # Per-market raw table for auditing
    lines.append("## Per-market detail")
    lines.append("")
    lines.append("| outcome | realm | llm | sim | poly | question |")
    lines.append("|--------|-------|-----|-----|------|----------|")
    for r in results:
        oc = "YES" if r.actual_outcome else "NO"
        q = r.question.replace("|", "\\|")[:80]
        lines.append(
            f"| {oc} | {r.realm_probability:.2f} | {r.llm_only_probability:.2f} | "
            f"{r.sim_only_probability:.2f} | {r.polymarket_price:.2f} | {q} |",
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="REALM Polymarket backtest")
    ap.add_argument("--markets", type=int, default=20, help="number of resolved markets")
    ap.add_argument("--agents", type=int, default=100)
    ap.add_argument("--ticks", type=int, default=30)
    ap.add_argument("--branches", type=int, default=5)
    ap.add_argument("--min-volume", type=float, default=10000.0)
    ap.add_argument("--master-seed", type=int, default=42)
    ap.add_argument(
        "--output", type=Path,
        default=ROOT / "outputs" / "polymarket_backtest_report.md",
    )
    args = ap.parse_args()

    if not os.environ.get("REALM_LLM_CATEGORY_BACKEND"):
        logger.warning(
            "REALM_LLM_CATEGORY_BACKEND is not set; LLM analyzers will "
            "return None. The 'LLM only' column will degrade to 0.5 for "
            "every market — backtest results will not be meaningful.",
        )

    started = datetime.now(UTC)
    t0 = time.time()
    results = run_backtest(
        n_markets=args.markets,
        n_agents=args.agents,
        n_ticks=args.ticks,
        n_branches=args.branches,
        min_volume=args.min_volume,
        master_seed=args.master_seed,
    )
    elapsed = time.time() - t0
    report = render_report(
        results,
        n_agents=args.agents, n_ticks=args.ticks, n_branches=args.branches,
        started=started, elapsed_sec=elapsed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    logger.info("Report written: %s", args.output)
    if results:
        agg = aggregate_brier(results)
        logger.info(
            "Mean Brier: poly=%.4f  realm=%.4f  llm=%.4f  sim=%.4f",
            agg["polymarket"]["mean"], agg["realm"]["mean"],
            agg["llm_only"]["mean"], agg["sim_only"]["mean"],
        )
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
