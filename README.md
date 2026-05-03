# REALM — Collective Sentiment Simulation Platform

> **Status:** v0.19.2 (Sprint 19.2 — delta decomposition hotfix) · **Tests:** 887 passing
> · **Article:** [`REALM_ARTICLE_DRAFT.md`](./REALM_ARTICLE_DRAFT.md) — *REALM: Collective Sentiment Simulation Through Time-Seeded Trait Diversification*
>
> **License:** MIT — Copyright © 2026 Suvar Ergun. See [`LICENSE`](./LICENSE).

---

## Showcase only

REALM is published as a research artifact accompanying the
forthcoming article above. The codebase reflects the state at
article publication and is **not actively maintained for external
contributions**. Issues / PRs are disabled at the repo level. Fork
freely; please cite `REALM v0.19.2, Loth (2026)` if you reference
the work.

---

## What is REALM?

REALM is a **collective sentiment simulation platform** that models
how diverse populations react to events, news, and scenarios. It
combines LLM-powered contextual analysis with agent-based swarm
simulation to answer two distinct types of questions:

1. **Baseline:** *"How likely is X?"* — answered primarily by LLM
   analysis grounded in current data (via optional web research),
   with swarm sentiment as a secondary signal (baseline blend:
   85-95% LLM / 5-15% sim).
2. **Scenario:** *"If Y happens, how does the likelihood of X
   change?"* — answered primarily by swarm simulation (scenario
   blend: 40% LLM / 60% sim). Modeling how agent populations with
   diverse personality traits shift their positions in response to
   injected events. **This is REALM's unique capability.**

**Honest framing:** REALM is **not** a market-beating point-prediction
engine. Polymarket backtesting (Sprint 18) showed the simulation
alone produces near-random Brier scores (≈ 0.25). The simulation's
value lies in scenario response modeling, population sentiment
breakdowns, and counterfactual analysis — not standalone prediction.
Prediction markets like Polymarket tell you the **current odds**;
REALM tells you **how the odds would change** under hypothetical
scenarios, *and* breaks the population down by trait cluster so you
can see *which* segments shift and *why*.

The four levers behind a REALM prediction:

1. **Time-seeded trait diversification.** Every agent starts with a
   24-trait personality vector derived from a real natal chart (via
   Skyfield or Kerykeion) blended 60/25/15 with Big Five mapping
   and Hofstede cultural dimensions. **No causal claim about
   astrology** — the ephemeris is used as a deterministic, reproducible
   diversification hash that produces psychometrically valid
   distributions (Big Five 8/8 PASS against Johnson IPIP-NEO-120,
   N=612,711).
2. **Category-conditioned event physics.** Each of the 9 prediction
   categories declares relative weights for 15 drift event types
   (financial_gain, leadership_act, group_conformity,
   regime_consolidation, sanctions_pressure, …) so a crypto question
   accumulates more financial events while a geopolitics question
   accumulates more authority / dominance / diplomatic-stalemate events.
3. **Scenario perturbation.** When the user injects a news feed, the
   LLM (when active) reads it semantically and produces per-trait
   deltas + an affected-population-fraction. Without LLM, a
   sentiment-word heuristic is the fallback. The dashboard surfaces
   `WHAT THE SCENARIO PUSHED` (LLM-derived per-trait deltas)
   separately from `WHAT THE SIM DRIFTED` (post-perturbation drift
   over N ticks).
4. **LLM-as-partner intelligence layer.** When configured, the LLM
   classifies the question (LLM-first routing), extracts a structured
   analysis (subject / yes_means / no_means / relevant_traits /
   factual prior), generates a question-specific narrative
   (headline / drivers / dissent / caveat), and the simulation result
   is blended with the LLM prior using per-category weights. The
   simulation models how a population REACTS; the LLM provides
   factual context. Together they're stronger than either alone.

---

## Quick start

```bash
# Windows
realm_start.bat
```

This opens two terminal windows, starts the FastAPI prediction server
on `http://127.0.0.1:8420`, serves the dashboard on
`http://127.0.0.1:8080/realm_dashboard_v2.html`, and opens the
dashboard in your default browser. Press any key in the original
window to shut both servers down.

Manual setup if you prefer:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -e .[web,sim,kerykeion]

# Run server (auto-loads .env at module import)
.venv\Scripts\python.exe -m uvicorn realm.api.predict:app --host 127.0.0.1 --port 8420 --reload

# Run dashboard (separate terminal)
.venv\Scripts\python.exe -m http.server 8080 --directory outputs

# Open in browser
http://127.0.0.1:8080/realm_dashboard_v2.html
```

---

## LLM configuration

REALM works with or without an LLM. When LLM access is configured,
the engine becomes the *brain* of the prediction loop: question
routing, question understanding, scenario semantics, and result
narration all go through the LLM. When unconfigured, the existing
keyword + sentiment + template path runs unchanged.

In `.env`:

```bash
# Master gate — when unset, REALM stays in sim-only mode regardless
# of whether API keys are present.
REALM_LLM_CATEGORY_BACKEND=1

# At least one provider key:
OPENAI_API_KEY=sk-proj-...                  # GPT-5.x via OpenAI
# OR
MOONSHOT_API_KEY=sk-...                     # Kimi k2.x via Moonshot

# Optional: web research grounding (Sprint 18).
# When set, the LLM generates 2-3 search queries per question and
# folds the results into the prior. Provider auto-detected from key
# presence (Tavily preferred over Brave when both are set).
TAVILY_API_KEY=tvly-...
# OR
BRAVE_API_KEY=...

# Optional: Kerykeion needs a free GeoNames username to skip the
# default-shared-quota warning. Only used by the natal-chart layer.
KERYKEION_GEONAMES_USERNAME=your_handle
```

When the FastAPI server starts you'll see one of:

```
[REALM] LLM backend ACTIVE — LLM-first routing + question / scenario / narrative analysis enabled
[REALM] LLM backend INACTIVE (REALM_LLM_CATEGORY_BACKEND not set) — running in simulation-only mode; ...
```

### What changes when the LLM is active

| component | LLM active | LLM inactive |
|-----------|-----------|--------------|
| Category routing | LLM classifier (3s timeout, in-process cache); keyword fallback on timeout / low confidence / unknown id | Keyword matching only |
| Question analysis | Full `QuestionAnalysis` (subject, yes_means, no_means, relevant_traits, llm_prior, prior_reasoning) | None |
| Probability blending | `probability = (1-w)·sim + w·llm_prior`, w from `category.llm_blend_weight` (baseline 0.85-0.95) or `scenario_llm_blend_weight` (scenario 0.40-0.50) | `probability = sim` |
| Scenario perturbation | Semantic per-trait `trait_impacts` + LLM-derived `affected_population_pct` | Scalar sentiment-word count applied uniformly to primary traits |
| Result narrative | Question-specific `headline`, `narrative_drivers`, `dissent_narrative`, `confidence_note`, `caveat` | Template `drivers` + `dissent` |
| Web research | LLM generates 2-3 queries → search → context injected into question prompt → `web_research_used: true`, `web_sources[]` | Skipped |

### Calibration is LLM-free by design

`scripts/calibrate_categories.py` defensively clears
`REALM_LLM_CATEGORY_BACKEND` from its environment at startup so
calibration runs stay deterministic regardless of the dev's shell.
The Sprint 16 calibration numbers (geopolitics 49.20%, spread
4.14pp) are protected from LLM-induced drift.

---

## Architecture

| module | purpose |
|--------|---------|
| `realm/agents/` | `AgentFactory` builds an `Agent` from a `DemographicProfile`, threading natal chart → adapter → cultural modifier → calibrator → political_spectrum override → seed offsets. |
| `realm/astro/` | Pure-Python ephemeris (Skyfield) + optional Kerykeion backend. Computes natal charts, transits, aspects (allocation-free hot path; Sprint 10 1.99s/tick at 10K agents). |
| `realm/personality/` | 24-trait `TraitVector` (frozen dataclass), input adapters (Astrological, Big Five, Demographic, Blended), calibrators, validation suite. |
| `realm/demographics/` | World-population sampler (66 countries, Hofstede 6D, V-Dem 4 indices, professions, names). |
| `realm/simulation/` | `SimulationEngine` ticks agents through decisions (post / engage / lurk), `DriftEventBridge` resolves decisions to drift events, `ExperienceDriftEngine` accumulates per-agent trait drift bounded by `max_drift_ratio`. |
| `realm/output/` | `CategoryRouter` (LLM-first + keyword fallback), `QuestionAnalyzer` / `ScenarioAnalyzer` / `PredictionNarrator`, `BranchSpec` + `build_branch_sim()` for multi-branch prediction. |
| `realm/api/` | `realm.api.predict:app` — FastAPI endpoints. Sigmoid-calibrated probability, dual baseline/scenario blend weights, delta decomposition. |
| `realm/llm/` | Multi-backend LLM router (Moonshot, OpenAI, Ollama), prompt loader, `WebResearcher` (Tavily / Brave). |
| `realm/validation/` | Polymarket Gamma API client + `BrierResult` + backtesting infrastructure (Sprint 18). |
| `outputs/realm_dashboard_v2.html` | Single-file HTML dashboard with 4 panels: Ask · Scenario · Network · About. Mock + Live modes, IBM Plex Mono terminal aesthetic, responsive. |

### Configuration map

| file | purpose |
|------|---------|
| `config/realm.yaml` | Root config: simulation seed, LLM backend choices, calibration knobs. |
| `config/prediction_categories.json` | 9 categories × {trait_weights, drift_event_weights, trait_seed_offsets, keywords, subcategories, drift_volatility, drift_asymmetry, sigmoid_sensitivity_multiplier, baseline_probability_offset, llm_blend_weight, scenario_llm_blend_weight}. |
| `config/drift_events.json` | 15 drift event types + 20 rules (Sprint 16 added regime_consolidation, diplomatic_stalemate, sanctions_pressure to model status-quo geopolitical dynamics). |
| `config/feed_sources.json` | Pre-configured RSS sources surfaced by the dashboard. |
| `config/trait_calibration_*.json` | Per-adapter calibration data (astrological / big_five_real / blended). |
| `data/hofstede_scores.json` | 66-country Hofstede 6D values. |
| `data/external/vdem_scores.json` | 66-country V-Dem 4-index values (curated). |
| `prompts/` | LLM prompt templates: `personality/`, `question_parser/`, `report/`, `spotlight/`, `feed_parser/`, `category/route.yaml`, `question/analyze.yaml`, `scenario/parse.yaml`, `narrative/generate.yaml`, `web_researcher/generate_queries.yaml`. |
| `.env` | Local-only secrets (LLM API keys, search API keys). **Never committed.** |

---

## API quick reference

### `POST /api/predict`

```json
{
  "question": "Will the Strait of Hormuz reopen by end of May?",
  "n_agents": 100,
  "n_ticks": 30,
  "n_branches": 5,
  "scenario_feed": "Iranian Kurdish armed groups deployed with US air support...",
  "use_llm": true,
  "use_sim": true,
  "enable_web_research": true,
  "master_seed": 42
}
```

Returns the standard `PredictResponse` plus the LLM-active fields:
- `probability`, `confidence`, `answer`, `drivers[]`, `dissent`,
  `agents_supporting/opposing/neutral`, `trait_shifts{}`,
  `branch_values[]`
- LLM analysis: `subject`, `yes_means`, `no_means`, `llm_prior`,
  `prior_reasoning`
- Probability diagnostics: `simulation_probability` (pre-blend) and
  `blended_probability` (post-blend)
- Narrative: `headline`, `narrative_drivers[]`, `dissent_narrative`,
  `confidence_note`, `caveat`
- Web research: `web_research_used`, `web_sources[]`
- Scenario fields (when `scenario_feed` provided):
  `baseline_probability`, `delta`, `scenario_perturbation{}`,
  `scenario_event_summary`, `delta_blend_shift`, `delta_sim_movement`,
  `delta_total`

### `POST /api/predict` toggles

- `use_llm: false` — bypass the entire LLM stack (no analyzer / no
  prior / no narrative). Used by the Polymarket backtest sim-only path.
- `use_sim: false` — skip the simulation entirely; return the LLM
  prior as the probability. Used by the LLM-only path.
- `enable_web_research: false` — bypass the web research step even
  when a search provider is configured.

### Other endpoints

- `POST /api/feed/parse` — accepts `{text}`, `{rss_url}`, or
  `{texts: [...]}`; returns `ParsedFeed` items with `sentiment_score`,
  `keywords`, `detected_category`.
- `GET /api/feeds` — pre-configured RSS feed sources.
- `GET /api/health` — active prediction-category list.

---

## Validation

### Big Five psychometric validity (Sprint 6)

8/8 criteria PASS against Johnson IPIP-NEO-120 (N=612,711) under
facet mode + contemporary online-sample tolerance. See
`outputs/realm_milestone_report.md` § 13.

### Astrological mapping validity (Sprint 7-8)

4/4 criteria PASS on a 22-figure celebrity cohort: Directional
Accuracy 0.718, Pearson r 0.309, Extreme-Trait Detection 0.766,
Confidence-Weighted DA 0.789. **Not a causation claim** — used as a
diversification mechanism, not a predictive astrology system.

### Polymarket backtesting (Sprint 18)

5 resolved markets at 50×10×3 scale (smoke run; 50-market run is
Sprint 20 backlog):

| Method          | Brier |
|-----------------|-------|
| Polymarket\*    | 0.000 |
| LLM only        | 0.117 |
| LLM+sim blend   | 0.165 |
| Sim only        | 0.247 |

\* Polymarket Brier uses settlement price; pre-resolution last
trading price would be more honest (Sprint 20 backlog: CLOB
prices-history fetch).

**Headline finding:** simulation alone produces near-random Brier
(0.247 ≈ 0.25). The Sprint 18 → Sprint 19 reframing was driven
directly by this number: REALM is positioned around scenario
analysis (where the simulation's value emerges), not standalone
baseline prediction.

### Calibration (Sprint 15-16)

Per-category baseline differentiation across 9 categories: spread
4.14pp, geopolitics 49.20%, science 53.34%, all 8 sanity gates
pass. 200 agents × 30 ticks × 5 branches × 10 runs/category. See
`outputs/sprint16_tier3_final_log.md`.

---

## Limitations & roadmap

**Honest limitations:**
- **Simulation alone is near-random for baseline prediction**
  (Brier ≈ 0.25). Baseline accuracy depends on LLM prior quality
  and optional web research grounding.
- **Backtest sample size is small** (5 markets). Larger-scale
  validation with the recalibrated Sprint 19 weights is Sprint 20+
  work.
- **Polymarket Brier methodology** in the current report uses
  settlement price (perfect 0.000); should use pre-resolution last
  trading price (Sprint 20 backlog).
- **Multi-category routing** blends drift event weights + sigmoid +
  asymmetry across categories but does NOT yet blend the per-trait
  observation weights or the LLM blend weight. Single-category
  routing is the bit-for-bit unchanged path.
- **CORS lockdown.** `realm/api/predict.py` ships with
  `allow_origins=["*"]` for local dev — production deployment must
  restrict to the served dashboard origin.

**Roadmap (Sprint 20+):**
- Larger Polymarket backtest (50+ markets) with Sprint 19 weights
- CLOB prices-history endpoint integration
- Per-category Brier breakdown + calibration curves
- Statistical-significance test (paired t-test / Wilcoxon) once
  N ≥ 30
- Vedic / Chinese astrology modules (regional ephemeris)
- Distributed compute for 100K+ agent simulations

---

## Citation

If you reference REALM in academic work:

```
Loth (2026). REALM v0.19.2: Collective Sentiment Simulation
Through Time-Seeded Trait Diversification.
https://github.com/lotheral/realm
```

Full article draft: [`REALM_ARTICLE_DRAFT.md`](./REALM_ARTICLE_DRAFT.md).

Per-sprint development narrative:
[`outputs/realm_milestone_report.md`](./outputs/realm_milestone_report.md).

Cumulative changelog: [`CHANGELOG.md`](./CHANGELOG.md).
