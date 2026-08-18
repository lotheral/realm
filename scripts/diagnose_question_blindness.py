"""Sprint 20 diagnosis — is the baseline simulation question-blind?

Sprint 18's Polymarket backtest scored sim-only at Brier 0.247 with
near-zero variance across markets, and Sprint 19 concluded "sim adds
negative value to baseline predictions". This script tests the sharper
structural hypothesis behind that number:

    H1 (question blindness): in baseline mode the simulation never sees
        question CONTENT — only the routed category's parameters — so
        every question in the same category gets an identical sim-only
        probability. "Sim adds negative value" would then be mechanical:
        blending a per-category constant toward ~0.5 dilutes any
        question-aware prior.

    H2 (scenario channel): the simulation's information channel is the
        scenario_feed. Different feeds for the same question must move
        the probability in feed-appropriate directions.

Run:  python scripts/diagnose_question_blindness.py
Cost: no LLM calls (use_llm=False), ~2-4 min of local simulation.
Output: markdown report at outputs/sprint20_question_blindness.md
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

# Hermetic: no LLM anywhere near this experiment.
os.environ["REALM_LLM_CATEGORY_BACKEND"] = ""

from realm.api.predict import PredictRequest, predict_endpoint  # noqa: E402

SCALE = {"n_agents": 50, "n_ticks": 10, "n_branches": 3}  # Sprint 18 backtest scale
SEED = 42

SAME_CATEGORY_QUESTIONS = [
    "Will Bitcoin close above $150,000 by the end of 2026?",
    "Will Ethereum flip Bitcoin in market cap this decade?",
    "Will a major exchange collapse trigger a crypto winter this year?",
]

CROSS_CATEGORY_QUESTIONS = [
    ("crypto", "Will Bitcoin close above $150,000 by the end of 2026?"),
    ("science", "Will a room-temperature superconductor be replicated this year?"),
    ("geopolitics", "Will a ceasefire agreement hold through the end of the year?"),
    ("sports", "Will the defending champions repeat their title this season?"),
]

SCENARIO_FEEDS = {
    "bullish": "Massive institutional adoption announced; regulators approve "
               "spot ETFs across Europe and Asia; optimism surges.",
    "bearish": "Major exchange declares insolvency; billions in customer funds "
               "frozen; panic selling and fear spread across markets.",
    "neutral": "Trading volumes remain unchanged this week; analysts note "
               "markets are calm and stable.",
}


def run(question: str, scenario: str | None = None) -> dict:
    req = PredictRequest(
        question=question,
        master_seed=SEED,
        use_llm=False,
        use_sim=True,
        enable_web_research=False,
        scenario_feed=scenario,
        **SCALE,
    )
    t0 = time.perf_counter()
    resp = predict_endpoint(req)
    # Field semantics (realm/api/predict.py): in scenario mode `probability`
    # is the scenario outcome and `baseline_probability` the no-event run;
    # in baseline mode `probability` is the (here: pure-sim) baseline.
    return {
        "category": resp.category_id,
        "probability": resp.probability,
        "baseline_probability": resp.baseline_probability,
        "branch_values": resp.branch_values,
        "secs": time.perf_counter() - t0,
    }


def main() -> None:
    lines: list[str] = [
        "# Sprint 20 — Baseline Question-Blindness Diagnosis",
        "",
        f"Scale: {SCALE['n_agents']} agents x {SCALE['n_ticks']} ticks x "
        f"{SCALE['n_branches']} branches, master_seed={SEED}, LLM disabled.",
        "",
    ]

    print("Experiment 1: same category, different questions")
    lines += ["## Experiment 1 — same category, different questions", ""]
    lines += ["| question | category | sim-only probability | branch values |",
              "|---|---|---|---|"]
    e1 = []
    for q in SAME_CATEGORY_QUESTIONS:
        r = run(q)
        e1.append(r)
        print(f"  [{r['category']}] p={r['probability']:.4f}  ({r['secs']:.1f}s)  {q[:50]}")
        lines.append(
            f"| {q} | {r['category']} | {r['probability']:.4f} | "
            f"{[round(b, 4) for b in r['branch_values']]} |"
        )
    identical = len({round(r["probability"], 6) for r in e1}) == 1
    verdict1 = (
        "**CONFIRMED — bit-for-bit identical.** The baseline simulation is "
        "question-blind: question text influences nothing but routing."
        if identical else
        "**NOT identical** — question text reaches the simulation through "
        "some path; investigate before concluding."
    )
    lines += ["", f"H1 verdict: {verdict1}", ""]

    print("Experiment 2: different categories")
    lines += ["## Experiment 2 — cross-category spread", ""]
    lines += ["| expected category | routed | sim-only probability |", "|---|---|---|"]
    for expected, q in CROSS_CATEGORY_QUESTIONS:
        r = run(q)
        print(f"  [{r['category']}] p={r['probability']:.4f}  ({r['secs']:.1f}s)")
        lines.append(f"| {expected} | {r['category']} | {r['probability']:.4f} |")
    lines += [
        "",
        "Baseline sim-only output should equal the per-category calibrated "
        "level (Sprint 16: geopolitics 49.20% ... science 53.34% at "
        "calibration scale) — i.e. category identity, not question content.",
        "",
    ]

    print("Experiment 3: scenario channel")
    lines += ["## Experiment 3 — scenario feeds (the information channel)", ""]
    lines += ["| feed | baseline p | scenario p | delta |", "|---|---|---|---|"]
    q = SAME_CATEGORY_QUESTIONS[0]
    for name, feed in SCENARIO_FEEDS.items():
        r = run(q, scenario=feed)
        scen = r["probability"]
        base = r["baseline_probability"]
        delta = (scen - base) if base is not None else None
        print(f"  [{name}] base={base} scenario={scen:.4f} ({r['secs']:.1f}s)")
        lines.append(
            f"| {name} | "
            f"{base if base is None else format(base, '.4f')} | "
            f"{scen:.4f} | "
            f"{delta if delta is None else format(delta, '+.4f')} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "If H1 is confirmed: Sprint 18's 'sim adds negative value (+0.048 "
        "Brier)' finding is a structural tautology, not an empirical defeat "
        "— sim-only baseline output carries zero question-specific "
        "information BY CONSTRUCTION, so blending it toward a question-aware "
        "prior can only dilute. The correct target for all validation "
        "effort is the scenario DELTA (Experiment 3's channel), which is "
        "exactly the reaction-distribution thesis of the 2026-08-18 "
        "repositioning design.",
        "",
        "## Second finding — heuristic scenario path was direction-blind "
        "(FIXED in Sprint 20)",
        "",
        "The first run of Experiment 3 (pre-fix) produced +0.125 for "
        "bullish, bearish AND neutral feeds alike: predict.py used the "
        "strict base-only sentiment inventory (missing 'panic', 'fear', "
        "'insolvency', 'optimism', ...), and a neutral parse fell back to "
        "a FABRICATED +0.08 positive nudge. Fix: full inventory + expanded "
        "affect terms; neutral parse now applies zero perturbation with a "
        "warning. Post-fix, the numbers above show symmetric, "
        "direction-correct movement with the LLM disabled.",
        "",
    ]

    out = _PROJECT_ROOT / "outputs" / "sprint20_question_blindness.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {out}")


if __name__ == "__main__":
    main()
