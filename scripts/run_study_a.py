"""Study A retrodiction harness (Sprint 22, design doc §4.1).

For each event in the dataset, runs the REALM prediction pipeline
in-process under the event's blinding regime and compares the predicted
support-share shift (``reaction.shift.support × 100``, the Sprint 21
first-class output) against the documented poll shift.

The OFFICIAL study run + write-up is Sprint 23 scope; this harness also
supports a cheap ``--limit`` smoke mode.

Usage::

    .venv/Scripts/python.exe scripts/run_study_a.py \\
        --events data/validation/study_a_events.json \\
        --n-agents 100 --n-ticks 30 --n-branches 5 --seed 42 \\
        --out outputs/study_a_results.md --json outputs/study_a_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realm.validation.retrodiction import (  # noqa: E402
    DirectionalResult,
    breakdown,
    directional_accuracy,
    spearman_rho,
)
from realm.validation.study_a import REGIMES, StudyAEvent, load_events  # noqa: E402

_REGIME_FLAGS = {
    "sim_delta_isolated": {"use_llm": False, "enable_web_research": False},
    "post_cutoff_web_off": {"use_llm": True, "enable_web_research": False},
}


def regime_flags(regime: str) -> dict:
    """LLM/web toggles enforcing the event's blinding regime."""
    try:
        return dict(_REGIME_FLAGS[regime])
    except KeyError:
        raise ValueError(
            f"unknown blinding regime {regime!r} (valid: {REGIMES})"
        ) from None


def event_to_request_kwargs(
    event: StudyAEvent, *, n_agents: int, n_ticks: int, n_branches: int, seed: int,
) -> dict:
    """Build the PredictRequest kwargs for one event (population included)."""
    spec = event.population
    population: dict = {}
    if spec.countries:
        population["countries"] = list(spec.countries)
    if spec.regions:
        population["regions"] = list(spec.regions)
    if spec.age_min is not None:
        population["age_min"] = spec.age_min
    if spec.age_max is not None:
        population["age_max"] = spec.age_max
    if spec.genders:
        population["genders"] = list(spec.genders)
    if spec.education_levels:
        population["education_levels"] = list(spec.education_levels)
    return {
        "question": event.question,
        "scenario_feed": event.event_summary,
        "population": population,
        "n_agents": n_agents,
        "n_ticks": n_ticks,
        "n_branches": n_branches,
        "master_seed": seed,
        **regime_flags(event.blinding_regime),
    }


def run_event(event: StudyAEvent, args) -> dict:
    from realm.api.predict import PredictRequest, predict_endpoint

    kwargs = event_to_request_kwargs(
        event,
        n_agents=args.n_agents, n_ticks=args.n_ticks,
        n_branches=args.n_branches, seed=args.seed,
    )
    started = time.perf_counter()
    resp = predict_endpoint(PredictRequest(**kwargs))
    elapsed = time.perf_counter() - started

    shift = resp.reaction.shift if resp.reaction is not None else None
    predicted_pp = (shift.support * 100.0) if shift is not None else 0.0
    return {
        "event_id": event.event_id,
        "regime": event.blinding_regime,
        "confidence": event.confidence,
        "verified": event.verified,
        "tags": list(event.tags),
        "population": event.population.describe(),
        "predicted_shift_pp": round(predicted_pp, 2),
        "observed_shift_pp": event.observed_shift_pp,
        "hit": (
            predicted_pp != 0.0
            and event.observed_shift_pp != 0.0
            and (predicted_pp > 0) == (event.observed_shift_pp > 0)
        ),
        "oppose_shift_pp": (
            round(shift.oppose * 100.0, 2) if shift is not None else None
        ),
        "probability_delta": resp.delta,
        "category_id": resp.category_id,
        "seconds": round(elapsed, 1),
    }


def _fmt_dir(result: DirectionalResult) -> str:
    return (
        f"{result.hits}/{result.n} ({result.accuracy:.0%}), "
        f"p={result.p_value_one_sided:.3f}, zero-preds={result.zero_predictions}"
    )


def render_report(rows: list[dict], events: list[StudyAEvent], args) -> str:
    predicted = [r["predicted_shift_pp"] for r in rows]
    observed = [r["observed_shift_pp"] for r in rows]
    overall = directional_accuracy(predicted, observed)
    rho_signed = spearman_rho(predicted, observed)
    rho_magnitude = spearman_rho(
        [abs(p) for p in predicted], [abs(o) for o in observed],
    )
    by_confidence = breakdown(events, predicted, observed)
    by_verified = breakdown(
        events, predicted, observed, key=lambda e: "verified" if e.verified else "unverified",
    )
    by_tag = breakdown(events, predicted, observed, key=lambda e: e.tags[0])

    counts = {"high": 0, "medium": 0, "low": 0}
    for ev in events:
        counts[ev.confidence] += 1

    lines: list[str] = []
    lines.append(f"# Study A Retrodiction — {args.label} run")
    lines.append("")
    lines.append(
        f"> {time.strftime('%Y-%m-%d %H:%M')} · n_agents={args.n_agents} "
        f"n_ticks={args.n_ticks} n_branches={args.n_branches} seed={args.seed} "
        f"· events={len(rows)}"
        + (f" (LIMITED subset of {len_all})" if (len_all := args.total_events) != len(rows) else "")
    )
    lines.append(">")
    lines.append(
        "> Predicted shift = `reaction.shift.support × 100` (Sprint 21 "
        "pooled stance output). All events ran under their logged blinding "
        "regime. A negative overall result is a valid study outcome."
    )
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- **Directional accuracy:** {_fmt_dir(overall)} (one-sided binomial vs 50%)")
    lines.append(f"- **Spearman ρ (signed shifts):** {rho_signed:.3f}")
    lines.append(f"- **Spearman ρ (magnitudes):** {rho_magnitude:.3f}")
    lines.append(
        f"- **Authorship-confidence ratio (first-class honesty metric):** "
        f"high {counts['high']} / medium {counts['medium']} / low {counts['low']}"
    )
    lines.append("")
    lines.append("## Breakdown — by authorship confidence")
    lines.append("")
    for name in ("high", "medium", "low"):
        if name in by_confidence:
            lines.append(f"- {name}: {_fmt_dir(by_confidence[name])}")
    lines.append("")
    lines.append("## Breakdown — by verification status")
    lines.append("")
    for name, result in sorted(by_verified.items()):
        lines.append(f"- {name}: {_fmt_dir(result)}")
    lines.append("")
    lines.append("## Breakdown — by mechanism tag")
    lines.append("")
    for name, result in sorted(by_tag.items()):
        lines.append(f"- {name}: {_fmt_dir(result)}")
    lines.append("")
    lines.append("## Per-event results")
    lines.append("")
    lines.append("| event | regime | conf | ver | tag | predicted pp | observed pp | hit |")
    lines.append("|---|---|---|---|---|---:|---:|---|")
    for r in rows:
        lines.append(
            f"| {r['event_id']} | {r['regime']} | {r['confidence']} | "
            f"{'Y' if r['verified'] else 'n'} | {r['tags'][0]} | "
            f"{r['predicted_shift_pp']:+.2f} | {r['observed_shift_pp']:+.1f} | "
            f"{'HIT' if r['hit'] else 'miss'} |"
        )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- Unverified events carry authored (training-data) poll numbers — "
        "candidates, not confirmed data; see the by-verification breakdown "
        "and `docs/study_a_dataset_notes.md`."
    )
    lines.append(
        "- `sim_delta_isolated` measures ONLY the sentiment-driven scenario "
        "channel (LLM off, web off). Rally-type events are included as "
        "deliberate hard cases for a sentiment-sign mechanism."
    )
    if args.label == "smoke":
        lines.append(
            "- SMOKE run (reduced parameters/subset) — NOT the official "
            "Study A result; the official run is Sprint 23 scope."
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Study A retrodiction harness")
    parser.add_argument("--events", default="data/validation/study_a_events.json")
    parser.add_argument("--n-agents", type=int, default=100)
    parser.add_argument("--n-ticks", type=int, default=30)
    parser.add_argument("--n-branches", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=0, help="0 = all events")
    parser.add_argument("--out", default="outputs/study_a_results.md")
    parser.add_argument("--json", dest="json_out", default="outputs/study_a_results.json")
    parser.add_argument("--label", default="official")
    args = parser.parse_args()

    events = load_events(args.events)
    args.total_events = len(events)
    if args.limit:
        events = events[: args.limit]

    rows: list[dict] = []
    for i, event in enumerate(events, 1):
        print(f"[{i}/{len(events)}] {event.event_id} ({event.blinding_regime}) ...", flush=True)
        row = run_event(event, args)
        print(
            f"    predicted {row['predicted_shift_pp']:+.2f}pp vs "
            f"observed {row['observed_shift_pp']:+.1f}pp -> "
            f"{'HIT' if row['hit'] else 'miss'} ({row['seconds']}s)",
            flush=True,
        )
        rows.append(row)

    report = render_report(rows, events, args)
    out_md = Path(args.out)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(report, encoding="utf-8")
    Path(args.json_out).write_text(
        json.dumps(
            {
                "label": args.label,
                "params": {
                    "n_agents": args.n_agents, "n_ticks": args.n_ticks,
                    "n_branches": args.n_branches, "seed": args.seed,
                },
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n[study_a] wrote {out_md} + {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
