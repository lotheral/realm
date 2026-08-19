"""Sprint 21 — /api/predict population targeting + reaction distribution."""

import pytest
from fastapi.testclient import TestClient

from realm.api.predict import app

client = TestClient(app)

BASE = {
    "question": "Will inflation fall next quarter?",
    "n_agents": 30, "n_ticks": 5, "n_branches": 2,
    "use_llm": False, "enable_web_research": False,
    "master_seed": 42,
}


@pytest.fixture(scope="module")
def baseline_resp():
    r = client.post("/api/predict", json=BASE)
    assert r.status_code == 200
    return r.json()


class TestReactionField:
    def test_reaction_present_with_pooled_counts(self, baseline_resp):
        rx = baseline_resp["reaction"]
        assert rx is not None
        assert rx["n_agents"] == 30 * 2  # pooled across branches
        # fields are rounded to 4 decimals independently → sum may be off
        # by up to ~1.5e-4
        assert abs(rx["support"] + rx["oppose"] + rx["neutral"] - 1.0) < 1e-3
        assert rx["baseline"] is None and rx["shift"] is None

    def test_agents_fields_mirror_reaction(self, baseline_resp):
        rx = baseline_resp["reaction"]
        assert baseline_resp["agents_supporting"] == pytest.approx(rx["support"], abs=1e-4)
        assert baseline_resp["agents_opposing"] == pytest.approx(rx["oppose"], abs=1e-4)
        assert baseline_resp["agents_neutral"] == pytest.approx(rx["neutral"], abs=1e-4)

    def test_segments_have_known_dimensions(self, baseline_resp):
        dims = {s["dimension"] for s in baseline_resp["reaction"]["segments"]}
        assert dims <= {"country", "region", "age_band", "gender"}
        assert "gender" in dims  # 60 pooled samples guarantee gender segments

    def test_population_label_defaults_to_global(self, baseline_resp):
        assert baseline_resp["population_label"] == "global"


class TestScenarioShift:
    def test_scenario_reaction_carries_baseline_and_shift(self):
        r = client.post("/api/predict", json={
            **BASE,
            "scenario_feed": "Markets crash as panic selling accelerates and layoffs surge",
        })
        assert r.status_code == 200
        rx = r.json()["reaction"]
        assert rx["baseline"] is not None
        assert rx["shift"] is not None
        for key in ("support", "oppose", "neutral"):
            # each field rounds to 4 decimals independently → tolerance 2e-4
            assert rx["shift"][key] == pytest.approx(rx[key] - rx["baseline"][key], abs=2e-4)


class TestBlindingGate:
    def test_use_llm_false_never_touches_scenario_analyzer_or_narrator(self, monkeypatch):
        """Sprint 22 regression: use_llm=False must gate the scenario
        analyzer and the narrator too, not just the question analyzer.
        The Study A smoke run showed the LLM scenario analyzer running on
        a use_llm=False request — a blinding leak (the LLM knows the
        historical outcome of famous events)."""
        import realm.api.predict as predict_mod

        def _explode():
            raise AssertionError("LLM component constructed under use_llm=False")

        monkeypatch.setattr(predict_mod, "_get_scenario_analyzer", _explode)
        monkeypatch.setattr(predict_mod, "_get_narrator", _explode)
        r = client.post("/api/predict", json={
            **BASE,
            "scenario_feed": "Markets crash as panic selling accelerates",
        })
        assert r.status_code == 200
        body = r.json()
        # Heuristic scenario path still works and reports a perturbation.
        assert body["reaction"]["shift"] is not None
        assert body["headline"] is None

    def test_use_llm_false_never_touches_env_wired_category_router(self, monkeypatch):
        """Sprint 25 regression: the category router is LLM-FIRST when
        REALM_LLM_CATEGORY_BACKEND wires a backend (Sprint 17), and
        `_get_router()` reads only the environment — the per-request
        use_llm=False flag never reached it. Category choice drives
        drift weights / sigmoid sensitivity / asymmetry, so an LLM that
        recognizes a famous historical question could steer simulation
        mechanics inside a blinded Study A run. use_llm=False requests
        must route through a keyword-only router instead."""
        import realm.api.predict as predict_mod

        def _explode():
            raise AssertionError("env-wired category router used under use_llm=False")

        monkeypatch.setattr(predict_mod, "_get_router", _explode)
        r = client.post("/api/predict", json=BASE)
        assert r.status_code == 200
        # Keyword routing still classifies the economics question.
        assert r.json()["category_id"] == "economics"


class TestPopulationTargeting:
    def test_population_restricts_segments_to_spec(self):
        r = client.post("/api/predict", json={
            **BASE,
            "population": {"countries": ["TR"], "age_min": 18, "age_max": 29},
        })
        assert r.status_code == 200
        body = r.json()
        assert "TR" in body["population_label"]
        country_segments = {
            s["segment"] for s in body["reaction"]["segments"]
            if s["dimension"] == "country"
        }
        assert country_segments == {"TR"}
        age_segments = {
            s["segment"] for s in body["reaction"]["segments"]
            if s["dimension"] == "age_band"
        }
        assert age_segments == {"18-29"}

    def test_unknown_country_is_400(self):
        r = client.post("/api/predict", json={
            **BASE, "population": {"countries": ["XX"]},
        })
        assert r.status_code == 400
        assert "unknown country" in r.json()["detail"]

    def test_llm_only_path_has_no_reaction(self):
        r = client.post("/api/predict", json={**BASE, "use_sim": False})
        assert r.status_code == 200
        body = r.json()
        assert body["reaction"] is None
        assert body["population_label"] == "global"
