"""Study B — forward-prediction diary (Sprint 22, design doc §4.2).

An append-only JSONL registry of predictions on upcoming events, written
BEFORE the events resolve and never edited afterwards; scoring only adds
a ``resolution`` block. Epistemically clean (leakage impossible), slow to
accumulate, nearly free to maintain.

CLI: ``scripts/diary.py`` (predict / list / score).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

DIARY_PATH = Path("outputs/prediction_diary/entries.jsonl")


@dataclass(frozen=True)
class DiaryEntry:
    entry_id: str
    created_utc: str
    question: str
    population: dict
    scenario_feed: str | None
    predicted_probability: float
    predicted_support: float
    predicted_oppose: float
    predicted_neutral: float
    predicted_shift_support_pp: float | None
    resolve_by: str
    resolution: dict | None


def append_entry(entry: DiaryEntry, path: Path = DIARY_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")


def load_entries(path: Path = DIARY_PATH) -> list[DiaryEntry]:
    path = Path(path)
    if not path.exists():
        return []
    entries: list[DiaryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(DiaryEntry(**json.loads(line)))
    return entries


def is_void(entry: DiaryEntry) -> bool:
    return bool(entry.resolution and entry.resolution.get("void"))


def score_entry(
    entry_id: str,
    *,
    observed_shift_pp: float,
    source: str,
    note: str | None = None,
    path: Path = DIARY_PATH,
) -> DiaryEntry:
    """Attach a resolution to one entry and rewrite the file.

    The prediction fields are never modified — scoring only adds the
    ``resolution`` block (observed shift, source, timestamp, directional
    hit vs ``predicted_shift_support_pp``; when the entry carried no
    shift prediction, the hit is judged against ``predicted_probability``
    vs 0.5 as the direction proxy). ``note`` records disclosures such as
    units (index points vs pp) or a noise-level shift.
    """

    def resolve(entry: DiaryEntry) -> dict:
        if entry.predicted_shift_support_pp is not None:
            predicted_direction = entry.predicted_shift_support_pp
        else:
            predicted_direction = entry.predicted_probability - 0.5
        hit = (
            predicted_direction != 0.0
            and observed_shift_pp != 0.0
            and (predicted_direction > 0) == (observed_shift_pp > 0)
        )
        resolution = {
            "observed_shift_pp": observed_shift_pp,
            "source": source,
            "scored_utc": datetime.now(UTC).isoformat(),
            "directional_hit": hit,
        }
        if note:
            resolution["note"] = note
        return resolution

    return _attach_resolution(entry_id, resolve, path=path)


def void_entry(entry_id: str, *, reason: str, path: Path = DIARY_PATH) -> DiaryEntry:
    """Close an entry WITHOUT scoring it — the question proved unresolvable
    (e.g. the named poll was discontinued). Void entries are excluded from
    the hit rate; the reason is kept so the exclusion stays auditable."""
    if not reason.strip():
        raise ValueError("voiding an entry requires a reason")
    return _attach_resolution(
        entry_id,
        lambda _entry: {
            "void": True,
            "reason": reason,
            "scored_utc": datetime.now(UTC).isoformat(),
        },
        path=path,
    )


def _attach_resolution(entry_id: str, make_resolution, *, path: Path) -> DiaryEntry:
    entries = load_entries(path=path)
    if entry_id not in [e.entry_id for e in entries]:
        raise ValueError(f"unknown diary entry_id {entry_id!r}")

    updated: list[DiaryEntry] = []
    resolved: DiaryEntry | None = None
    for entry in entries:
        if entry.entry_id != entry_id:
            updated.append(entry)
            continue
        if entry.resolution is not None:
            raise ValueError(f"entry {entry_id!r} is already scored")
        resolved = DiaryEntry(**{**asdict(entry), "resolution": make_resolution(entry)})
        updated.append(resolved)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for entry in updated:
            fh.write(json.dumps(asdict(entry)) + "\n")
    assert resolved is not None
    return resolved
