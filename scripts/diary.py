"""Study B forward-prediction diary CLI (Sprint 22, design doc §4.2).

Commands::

    python scripts/diary.py predict "Will X be supported?" \\
        [--scenario "..."] [--countries TR,DE] [--regions europe_west] \\
        [--age-min 18 --age-max 29] [--resolve-by 2026-12-31] \\
        [--n-agents 100] [--n-ticks 30] [--n-branches 5]
    python scripts/diary.py list
    python scripts/diary.py score ENTRY_ID --observed-shift-pp 4.5 \\
        --source "Poll name / URL"

Forward predictions run with the LLM + web research ENABLED — leakage is
impossible for events that have not happened yet, so the full pipeline is
the honest configuration here (unlike Study A's blinded retrodiction).
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realm.validation.diary import (  # noqa: E402
    DIARY_PATH,
    DiaryEntry,
    append_entry,
    load_entries,
    score_entry,
)


def _population_from_args(args) -> dict:
    pop: dict = {}
    if args.countries:
        pop["countries"] = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    if args.regions:
        pop["regions"] = [r.strip() for r in args.regions.split(",") if r.strip()]
    if args.age_min is not None:
        pop["age_min"] = args.age_min
    if args.age_max is not None:
        pop["age_max"] = args.age_max
    return pop


def cmd_predict(args) -> int:
    from realm.api.predict import PredictRequest, predict_endpoint

    population = _population_from_args(args)
    req_kwargs = {
        "question": args.question,
        "n_agents": args.n_agents,
        "n_ticks": args.n_ticks,
        "n_branches": args.n_branches,
    }
    if population:
        req_kwargs["population"] = population
    if args.scenario:
        req_kwargs["scenario_feed"] = args.scenario
    resp = predict_endpoint(PredictRequest(**req_kwargs))

    shift_pp = None
    if resp.reaction is not None and resp.reaction.shift is not None:
        shift_pp = round(resp.reaction.shift.support * 100.0, 2)
    entry = DiaryEntry(
        entry_id=f"diary_{datetime.now(UTC).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
        created_utc=datetime.now(UTC).isoformat(),
        question=args.question,
        population=population,
        scenario_feed=args.scenario,
        predicted_probability=resp.probability,
        predicted_support=(resp.reaction.support if resp.reaction else 0.0),
        predicted_oppose=(resp.reaction.oppose if resp.reaction else 0.0),
        predicted_neutral=(resp.reaction.neutral if resp.reaction else 1.0),
        predicted_shift_support_pp=shift_pp,
        resolve_by=args.resolve_by,
        resolution=None,
    )
    append_entry(entry)
    print(f"[diary] appended {entry.entry_id} -> {DIARY_PATH}")
    print(
        f"    P={entry.predicted_probability:.3f}  "
        f"support/oppose/neutral = {entry.predicted_support:.2f}/"
        f"{entry.predicted_oppose:.2f}/{entry.predicted_neutral:.2f}"
        + (f"  shift={shift_pp:+.2f}pp" if shift_pp is not None else "")
    )
    return 0


def cmd_list(_args) -> int:
    entries = load_entries()
    if not entries:
        print(f"[diary] no entries yet ({DIARY_PATH})")
        return 0
    for e in entries:
        status = "OPEN"
        if e.resolution is not None:
            status = "HIT" if e.resolution.get("directional_hit") else "MISS"
        print(f"{e.entry_id}  [{status}]  resolve_by={e.resolve_by}  {e.question}")
    scored = [e for e in entries if e.resolution is not None]
    if scored:
        hits = sum(1 for e in scored if e.resolution.get("directional_hit"))
        print(f"\n[diary] scored: {hits}/{len(scored)} directional hits; open: {len(entries) - len(scored)}")
    return 0


def cmd_score(args) -> int:
    entry = score_entry(
        args.entry_id,
        observed_shift_pp=args.observed_shift_pp,
        source=args.source,
    )
    print(
        f"[diary] scored {entry.entry_id}: "
        f"{'HIT' if entry.resolution['directional_hit'] else 'MISS'} "
        f"(observed {args.observed_shift_pp:+.2f}pp, source: {args.source})"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Study B prediction diary")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("predict", help="run the pipeline and append a diary entry")
    p.add_argument("question")
    p.add_argument("--scenario", default=None)
    p.add_argument("--countries", default="")
    p.add_argument("--regions", default="")
    p.add_argument("--age-min", type=int, default=None)
    p.add_argument("--age-max", type=int, default=None)
    p.add_argument("--resolve-by", default="")
    p.add_argument("--n-agents", type=int, default=100)
    p.add_argument("--n-ticks", type=int, default=30)
    p.add_argument("--n-branches", type=int, default=5)
    p.set_defaults(func=cmd_predict)

    sub.add_parser("list", help="list diary entries + score summary").set_defaults(func=cmd_list)

    s = sub.add_parser("score", help="attach a resolution to an entry")
    s.add_argument("entry_id")
    s.add_argument("--observed-shift-pp", type=float, required=True)
    s.add_argument("--source", required=True)
    s.set_defaults(func=cmd_score)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
