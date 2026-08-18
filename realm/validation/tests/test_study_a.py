"""Tests for the Study A event schema + validating loader (Sprint 22)."""

import json
from datetime import date
from pathlib import Path

import pytest

from realm.demographics.population_spec import PopulationSpec
from realm.validation.study_a import (
    CONFIDENCE_LEVELS,
    REGIMES,
    StudyAEvent,
    load_events,
)


def make_event(**overrides) -> dict:
    base = {
        "event_id": "fukushima_de_nuclear",
        "event_date": "2011-03-11",
        "event_summary": (
            "A magnitude-9.0 earthquake and tsunami strike Japan; explosions "
            "and meltdowns at the Fukushima Daiichi nuclear plant force mass "
            "evacuations as radiation leaks into air and sea."
        ),
        "question": "Will continued use of nuclear power be supported?",
        "population": {"countries": ["DE"]},
        "poll_source": "Forsa",
        "metric": "% supporting continued use of nuclear power",
        "before_value": 40.0,
        "after_value": 26.0,
        "before_date": "2011-02",
        "after_date": "2011-03",
        "observed_shift_pp": -14.0,
        "blinding_regime": "sim_delta_isolated",
        "confidence": "medium",
        "tags": ["policy_shift"],
    }
    base.update(overrides)
    return base


def write_dataset(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / "events.json"
    p.write_text(json.dumps({"version": 1, "events": events}), encoding="utf-8")
    return p


class TestLoader:
    def test_happy_path(self, tmp_path):
        events = load_events(write_dataset(tmp_path, [make_event()]))
        assert len(events) == 1
        ev = events[0]
        assert isinstance(ev, StudyAEvent)
        assert ev.event_date == date(2011, 3, 11)
        assert isinstance(ev.population, PopulationSpec)
        assert ev.population.countries == ("DE",)
        assert ev.verified is False
        assert ev.tags == ("policy_shift",)
        assert ev.blinding_regime in REGIMES
        assert ev.confidence in CONFIDENCE_LEVELS

    def test_unknown_regime_raises(self, tmp_path):
        path = write_dataset(tmp_path, [make_event(blinding_regime="wide_open")])
        with pytest.raises(ValueError, match="regime"):
            load_events(path)

    def test_unknown_confidence_raises(self, tmp_path):
        path = write_dataset(tmp_path, [make_event(confidence="certain")])
        with pytest.raises(ValueError, match="confidence"):
            load_events(path)

    def test_shift_mismatch_raises(self, tmp_path):
        path = write_dataset(tmp_path, [make_event(observed_shift_pp=-3.0)])
        with pytest.raises(ValueError, match="observed_shift_pp"):
            load_events(path)

    def test_post_cutoff_regime_needs_post_cutoff_date(self, tmp_path):
        path = write_dataset(
            tmp_path, [make_event(blinding_regime="post_cutoff_web_off")],
        )
        with pytest.raises(ValueError, match="post_cutoff"):
            load_events(path)

    def test_duplicate_ids_raise(self, tmp_path):
        path = write_dataset(tmp_path, [make_event(), make_event()])
        with pytest.raises(ValueError, match="duplicate"):
            load_events(path)

    def test_bad_population_raises(self, tmp_path):
        path = write_dataset(
            tmp_path, [make_event(population={"countries": ["XX"]})],
        )
        with pytest.raises(ValueError, match="unknown country"):
            load_events(path)

    def test_empty_summary_raises(self, tmp_path):
        path = write_dataset(tmp_path, [make_event(event_summary="  ")])
        with pytest.raises(ValueError, match="event_summary"):
            load_events(path)
