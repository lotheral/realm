"""Tests for the pure helpers of scripts/run_study_a.py (Sprint 22)."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from realm.demographics.population_spec import PopulationSpec
from realm.validation.study_a import StudyAEvent

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "run_study_a.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_study_a", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_study_a"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_script_module()


def make_event(**overrides) -> StudyAEvent:
    base = {
        "event_id": "ev1",
        "event_date": date(2011, 3, 11),
        "event_summary": "Disaster strikes and markets panic.",
        "question": "Will X be supported?",
        "population": PopulationSpec(countries=("DE",), age_min=30, age_max=44),
        "poll_source": "src",
        "metric": "% supporting X",
        "before_value": 40.0,
        "after_value": 30.0,
        "before_date": "2011-02",
        "after_date": "2011-03",
        "observed_shift_pp": -10.0,
        "blinding_regime": "sim_delta_isolated",
        "confidence": "high",
        "verified": True,
        "verification_note": "",
        "tags": ("policy_shift",),
        "notes": "",
    }
    base.update(overrides)
    return StudyAEvent(**base)


class TestRegimeFlags:
    def test_sim_delta_isolated(self):
        assert mod.regime_flags("sim_delta_isolated") == {
            "use_llm": False, "enable_web_research": False,
        }

    def test_post_cutoff_web_off(self):
        assert mod.regime_flags("post_cutoff_web_off") == {
            "use_llm": True, "enable_web_research": False,
        }

    def test_unknown_regime_raises(self):
        with pytest.raises(ValueError):
            mod.regime_flags("wide_open")


class TestEventToRequestKwargs:
    def test_builds_blinded_request_kwargs(self):
        ev = make_event()
        kwargs = mod.event_to_request_kwargs(
            ev, n_agents=50, n_ticks=10, n_branches=3, seed=42,
        )
        assert kwargs["question"] == ev.question
        assert kwargs["scenario_feed"] == ev.event_summary
        assert kwargs["n_agents"] == 50
        assert kwargs["n_ticks"] == 10
        assert kwargs["n_branches"] == 3
        assert kwargs["master_seed"] == 42
        assert kwargs["use_llm"] is False
        assert kwargs["enable_web_research"] is False
        pop = kwargs["population"]
        assert pop["countries"] == ["DE"]
        assert pop["age_min"] == 30 and pop["age_max"] == 44
        assert "regions" not in pop and "genders" not in pop
