"""Tests for the Study B forward-prediction diary (Sprint 22)."""

import pytest

from realm.validation.diary import (
    DiaryEntry,
    append_entry,
    load_entries,
    score_entry,
)


def make_entry(entry_id: str = "e1", **overrides) -> DiaryEntry:
    base = {
        "entry_id": entry_id,
        "created_utc": "2026-08-18T20:00:00+00:00",
        "question": "Will X be supported?",
        "population": {"countries": ["TR"]},
        "scenario_feed": None,
        "predicted_probability": 0.6,
        "predicted_support": 0.5,
        "predicted_oppose": 0.3,
        "predicted_neutral": 0.2,
        "predicted_shift_support_pp": None,
        "resolve_by": "2026-12-31",
        "resolution": None,
    }
    base.update(overrides)
    return DiaryEntry(**base)


class TestDiary:
    def test_append_and_load_round_trip(self, tmp_path):
        path = tmp_path / "diary" / "entries.jsonl"
        append_entry(make_entry("e1"), path=path)
        append_entry(make_entry("e2", predicted_shift_support_pp=4.2), path=path)
        entries = load_entries(path=path)
        assert [e.entry_id for e in entries] == ["e1", "e2"]
        assert entries[1].predicted_shift_support_pp == 4.2
        assert entries[0].resolution is None

    def test_score_sets_resolution_and_hit(self, tmp_path):
        path = tmp_path / "entries.jsonl"
        append_entry(make_entry("e1", predicted_shift_support_pp=5.0), path=path)
        scored = score_entry(
            "e1", observed_shift_pp=3.0, source="Some Poll", path=path,
        )
        assert scored.resolution is not None
        assert scored.resolution["observed_shift_pp"] == 3.0
        assert scored.resolution["source"] == "Some Poll"
        assert scored.resolution["directional_hit"] is True
        # Persisted, not just returned:
        reloaded = load_entries(path=path)[0]
        assert reloaded.resolution["directional_hit"] is True

    def test_score_miss_direction(self, tmp_path):
        path = tmp_path / "entries.jsonl"
        append_entry(make_entry("e1", predicted_shift_support_pp=-5.0), path=path)
        scored = score_entry("e1", observed_shift_pp=3.0, source="s", path=path)
        assert scored.resolution["directional_hit"] is False

    def test_double_score_raises(self, tmp_path):
        path = tmp_path / "entries.jsonl"
        append_entry(make_entry("e1", predicted_shift_support_pp=1.0), path=path)
        score_entry("e1", observed_shift_pp=1.0, source="s", path=path)
        with pytest.raises(ValueError, match="already scored"):
            score_entry("e1", observed_shift_pp=2.0, source="s", path=path)

    def test_unknown_id_raises(self, tmp_path):
        path = tmp_path / "entries.jsonl"
        append_entry(make_entry("e1"), path=path)
        with pytest.raises(ValueError, match="unknown"):
            score_entry("nope", observed_shift_pp=1.0, source="s", path=path)

    def test_load_missing_file_returns_empty(self, tmp_path):
        assert load_entries(path=tmp_path / "absent.jsonl") == []
