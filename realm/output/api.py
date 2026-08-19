"""FastAPI app factory.

Builds a FastAPI instance wired to a DashboardService. Separated from the
service so tests and alternative transports (CLI, stdout) can reuse the
service directly.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from realm import __version__ as _realm_version
from realm.core.logging import get_logger
from realm.output.dashboard_service import DashboardService
from realm.output.predictor import PredictionEngine, QuestionParser

logger = get_logger(__name__)


# ---- Request/response schemas -------------------------------------------

class PredictRequest(BaseModel):
    question: str
    master_seed: int | None = None
    n_branches: int | None = None
    horizon_ticks: int | None = None
    n_agents: int | None = None


class PredictResponse(BaseModel):
    question: str
    metric: str
    probability: float
    mean_value: float
    stddev_value: float
    confidence: float
    branch_values: list[float]
    narrative: str


class ScenarioEventInput(BaseModel):
    headline: str
    topic: str = "news"
    sentiment: float = 0.0
    virality: float = 3.0
    geography: str | None = None


class PredictScenarioRequest(BaseModel):
    question: str
    events: list[ScenarioEventInput]
    master_seed: int | None = None
    n_branches: int | None = None
    horizon_ticks: int | None = None
    n_agents: int | None = None


class PredictScenarioResponse(BaseModel):
    question: str
    metric: str
    threshold: float
    baseline: PredictResponse
    scenario: PredictResponse
    delta_mean: float
    delta_probability: float
    delta_per_branch: list[float]
    verdict: str          # "strong_lift" | "lift" | "neutral" | "counter"
    verdict_text: str


# ---- App factory ---------------------------------------------------------

def create_app(service: DashboardService) -> FastAPI:
    """Construct a FastAPI app bound to `service`.

    The service is captured by closure — to swap data, build a new app. For a
    long-running simulation, the same service instance keeps working since it
    reads live state from the underlying SimulationEngine.
    """
    app = FastAPI(
        title="REALM Dashboard",
        description="Population-reaction simulation engine — API + live UI",
        version=_realm_version,
    )

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ---- UI ----------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def root() -> HTMLResponse:
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>REALM Dashboard</h1><p>index.html missing.</p>")
        return FileResponse(index_path)

    # ---- JSON endpoints --------------------------------------------

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        return service.stats()

    @app.get("/api/timeline")
    def timeline() -> list[dict[str, Any]]:
        return service.timeline()

    @app.get("/api/agents")
    def agents(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return service.agents_summary(limit=limit, offset=offset)

    @app.get("/api/agents/{agent_id}")
    def agent_detail(agent_id: str) -> dict[str, Any]:
        detail = service.agent_detail(agent_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"agent {agent_id!r} not found")
        return detail

    @app.get("/api/network")
    def network(sample: int | None = None) -> dict[str, Any]:
        return service.network_snapshot(sample_size=sample)

    @app.get("/api/climate")
    def climate() -> dict[str, Any]:
        return service.climate_snapshot()

    @app.get("/api/kg")
    def kg(top_n: int = 20) -> dict[str, Any]:
        return service.kg_snapshot(top_n=top_n)

    @app.get("/api/mood")
    def mood() -> dict[str, Any]:
        return service.mood()

    @app.get("/api/top_posts")
    def top_posts(n: int = 10) -> list[dict[str, Any]]:
        return service.top_posts(n=n)

    @app.post("/api/predict", response_model=PredictResponse)
    def predict(req: PredictRequest) -> PredictResponse:
        master_seed = req.master_seed or service.sim.clock.master_seed
        spec = _spec_from_question(req.question)
        spec = _apply_overrides(
            spec,
            n_branches=req.n_branches,
            horizon_ticks=req.horizon_ticks,
            n_agents=req.n_agents,
        )
        engine = PredictionEngine(master_seed=master_seed)
        outcome = engine.run(spec, question=req.question)
        return _predict_response_from_outcome(outcome)

    @app.post("/api/predict_scenario", response_model=PredictScenarioResponse)
    def predict_scenario(req: PredictScenarioRequest) -> PredictScenarioResponse:
        """Baseline vs. what-if scenario, side by side.

        Agents see the caller-supplied SeedEvents at tick 0 in the scenario
        branch; baseline runs empty. Same master seed + branch offsets keep
        every other variable identical — the delta is purely the news injection.
        """
        from datetime import datetime

        from realm.ingestion.interfaces import SeedEvent

        master_seed = req.master_seed or service.sim.clock.master_seed
        base_spec = _spec_from_question(req.question)
        base_spec = _apply_overrides(
            base_spec,
            n_branches=req.n_branches,
            horizon_ticks=req.horizon_ticks,
            n_agents=req.n_agents,
        )

        now = datetime.now(UTC)
        initial_events = tuple(
            SeedEvent(
                event_id=f"user-{i:03d}",
                source="dashboard:scenario",
                timestamp=now,
                headline=ev.headline,
                topic=ev.topic,
                sentiment=max(-1.0, min(1.0, ev.sentiment)),
                virality=max(1.0, min(5.0, ev.virality)),
                geography=ev.geography or None,
            )
            for i, ev in enumerate(req.events)
        )

        scenario_spec = _with(base_spec, initial_events=initial_events)

        engine = PredictionEngine(master_seed=master_seed)
        baseline_outcome = engine.run(base_spec, question=req.question)
        scenario_outcome = engine.run(scenario_spec, question=req.question)

        delta_per_branch = [
            s - b for b, s in zip(
                baseline_outcome.branch_values,
                scenario_outcome.branch_values,
                strict=True,
            )
        ]
        delta_mean = scenario_outcome.mean_value - baseline_outcome.mean_value
        delta_prob = scenario_outcome.probability - baseline_outcome.probability

        verdict, verdict_text = _classify_verdict(
            baseline_outcome, scenario_outcome, delta_mean, base_spec.threshold,
        )

        return PredictScenarioResponse(
            question=req.question,
            metric=base_spec.name,
            threshold=base_spec.threshold,
            baseline=_predict_response_from_outcome(baseline_outcome),
            scenario=_predict_response_from_outcome(scenario_outcome),
            delta_mean=delta_mean,
            delta_probability=delta_prob,
            delta_per_branch=delta_per_branch,
            verdict=verdict,
            verdict_text=verdict_text,
        )

    return app


def _spec_from_question(question: str):
    return QuestionParser().parse(question).spec


def _apply_overrides(spec, *, n_branches=None, horizon_ticks=None, n_agents=None):
    if n_branches:
        spec = _with(spec, n_branches=max(1, min(n_branches, 20)))
    if horizon_ticks:
        spec = _with(spec, horizon_ticks=max(1, min(horizon_ticks, 200)))
    if n_agents:
        spec = _with(spec, n_agents=max(30, min(n_agents, 1500)))
    return spec


def _predict_response_from_outcome(outcome) -> PredictResponse:
    return PredictResponse(
        question=outcome.question,
        metric=outcome.metric,
        probability=outcome.probability,
        mean_value=outcome.mean_value,
        stddev_value=outcome.stddev_value,
        confidence=outcome.confidence,
        branch_values=list(outcome.branch_values),
        narrative=outcome.narrative,
    )


def _classify_verdict(baseline, scenario, delta_mean: float, threshold: float):
    if abs(delta_mean) < 0.01:
        return "neutral", (
            f"No measurable propagation (|Δ|={abs(delta_mean):.3f} < 0.01)."
        )
    crossed = (
        (baseline.probability < 0.5 and scenario.probability >= 0.5)
        or (baseline.probability >= 0.5 and scenario.probability < 0.5)
    )
    direction = "lifted" if delta_mean > 0 else "suppressed"
    if crossed:
        return "strong_lift", (
            f"Scenario {direction} the outcome past the decision threshold — "
            f"answer flipped from {_yes_no(baseline.probability)} → "
            f"{_yes_no(scenario.probability)}."
        )
    if abs(delta_mean) >= 0.05:
        return "lift" if delta_mean > 0 else "counter", (
            f"Scenario {direction} the metric by {abs(delta_mean):.3f} "
            f"(relative {abs(delta_mean)/max(baseline.mean_value, 0.001):.0%}) — "
            "clear butterfly effect, threshold not crossed."
        )
    return "lift" if delta_mean > 0 else "counter", (
        f"Scenario {direction} the metric by {abs(delta_mean):.3f} — "
        "small but consistent."
    )


def _yes_no(prob: float) -> str:
    return "yes" if prob >= 0.5 else "no"


def _with(spec, **overrides):
    from dataclasses import replace
    return replace(spec, **overrides)
