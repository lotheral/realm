"""Study A — historical retrodiction dataset schema + validating loader.

Sprint 22, design doc §4.1: 15-30 historical events with documented
before/after opinion measurements for a defined population. Each event
carries a blinding regime (design §4.1 hard requirement) and an honesty
envelope: authorship confidence (high/medium/low) and a ``verified`` flag
that is only set after the poll numbers were checked against a source.

Sign convention (locked in the Sprint 22 plan): each event's ``question``
is phrased so YES = the polled metric's subject; ``observed_shift_pp`` is
``after_value - before_value``; the harness compares its sign against the
sign of the predicted support-share shift.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from realm.demographics.population_spec import PopulationSpec

REGIMES = ("sim_delta_isolated", "post_cutoff_web_off")
CONFIDENCE_LEVELS = ("high", "medium", "low")

# Events dated on/before this may NOT use the LLM-on regime — the LLM's
# training data could contain the polled outcome (the Sprint 18 mistake).
LLM_CUTOFF_DATE = date(2026, 1, 31)

_SHIFT_TOLERANCE = 0.05


@dataclass(frozen=True)
class StudyAEvent:
    event_id: str
    event_date: date
    event_summary: str          # scenario-feed news copy; must not leak the poll outcome
    question: str               # phrased so YES = the metric's subject
    population: PopulationSpec
    poll_source: str
    metric: str
    before_value: float
    after_value: float
    before_date: str
    after_date: str
    observed_shift_pp: float    # after_value - before_value
    blinding_regime: str
    confidence: str             # authorship confidence: high | medium | low
    verified: bool
    verification_note: str
    tags: tuple[str, ...]
    notes: str


def _build_population(raw: dict) -> PopulationSpec:
    kwargs = {
        key: tuple(value) if isinstance(value, list) else value
        for key, value in raw.items()
    }
    spec = PopulationSpec(**kwargs)
    spec.validate()
    return spec


def load_events(path: str | Path) -> list[StudyAEvent]:
    """Load + validate the Study A dataset. Raises ValueError on any
    schema violation so a broken dataset can never silently reach the
    harness."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    events: list[StudyAEvent] = []
    seen_ids: set[str] = set()
    for raw in payload["events"]:
        event_id = str(raw["event_id"])
        if event_id in seen_ids:
            raise ValueError(f"duplicate event_id {event_id!r}")
        seen_ids.add(event_id)

        regime = str(raw["blinding_regime"])
        if regime not in REGIMES:
            raise ValueError(
                f"{event_id}: unknown blinding regime {regime!r} (valid: {REGIMES})"
            )
        confidence = str(raw["confidence"])
        if confidence not in CONFIDENCE_LEVELS:
            raise ValueError(
                f"{event_id}: unknown confidence {confidence!r} "
                f"(valid: {CONFIDENCE_LEVELS})"
            )

        event_date = date.fromisoformat(str(raw["event_date"]))
        if regime == "post_cutoff_web_off" and event_date <= LLM_CUTOFF_DATE:
            raise ValueError(
                f"{event_id}: regime post_cutoff_web_off requires an event "
                f"after the LLM cutoff {LLM_CUTOFF_DATE.isoformat()} "
                f"(got {event_date.isoformat()}) — pre-cutoff events must "
                "use sim_delta_isolated"
            )

        summary = str(raw["event_summary"]).strip()
        if not summary:
            raise ValueError(f"{event_id}: event_summary must be non-empty")
        question = str(raw["question"]).strip()
        if not question:
            raise ValueError(f"{event_id}: question must be non-empty")

        before = float(raw["before_value"])
        after = float(raw["after_value"])
        shift = float(raw["observed_shift_pp"])
        if abs(shift - (after - before)) > _SHIFT_TOLERANCE:
            raise ValueError(
                f"{event_id}: observed_shift_pp ({shift}) does not equal "
                f"after_value - before_value ({after - before:.2f})"
            )

        try:
            population = _build_population(dict(raw["population"]))
        except ValueError as exc:
            raise ValueError(f"{event_id}: {exc}") from exc

        events.append(StudyAEvent(
            event_id=event_id,
            event_date=event_date,
            event_summary=summary,
            question=question,
            population=population,
            poll_source=str(raw["poll_source"]),
            metric=str(raw["metric"]),
            before_value=before,
            after_value=after,
            before_date=str(raw["before_date"]),
            after_date=str(raw["after_date"]),
            observed_shift_pp=shift,
            blinding_regime=regime,
            confidence=confidence,
            verified=bool(raw.get("verified", False)),
            verification_note=str(raw.get("verification_note", "")),
            tags=tuple(raw.get("tags", ())),
            notes=str(raw.get("notes", "")),
        ))
    return events
