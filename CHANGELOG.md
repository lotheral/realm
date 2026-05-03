# REALM Changelog

All notable changes since the initial release. Per-sprint detail lives
in `REALM_CLAUDE.md` § 0 (CURRENT BUILD STATE) and
`outputs/realm_milestone_report.md` (full historical narrative).

## v0.19.2 — Delta decomposition hotfix (2026-05-04)

- **Fixed:** scenario delta now decomposed into `delta_blend_shift`
  (mechanical pull from baseline 0.90/0.10 → scenario 0.40/0.60 weight
  flip) and `delta_sim_movement` (actual simulation response to the
  perturbation). Prevents the dual-blend artifact where LLM prior < 0.5
  always reads as "scenario pushes UP" regardless of scenario content.
- Dashboard scenario panel now shows `of which: blend rebalancing
  +X.Xpp / simulation response ±Y.Ypp`.
- Tests: 881 → **887** (+6 decomposition math).

## v0.19.1 — Scenario perturbation transparency hotfix (2026-05-04)

- **Fixed:** scenario panel `WHAT THE SIM DRIFTED` showed ±0.001 even
  when probability moved 9pp because Sprint 13 trait_shifts excludes
  perturbation. New `scenario_perturbation` field surfaces LLM-derived
  per-trait deltas (or heuristic scalar) so users see what the
  scenario actually pushed.
- **Fixed:** hardcoded "drift events: financial_gain + leadership_act
  triggered" line replaced with real `scenario_event_summary` from
  the LLM scenario analyzer.
- **Fixed:** `Math.abs(v) < 0.0005 ? 0 : v` snap-to-zero in dashboard
  trait displays so `-0.000` and `0.000` aren't shown side-by-side.
- **Added:** Tavily auto-detect — when `TAVILY_API_KEY` is in `.env`
  but `REALM_WEB_SEARCH_PROVIDER` isn't, the provider is auto-set
  to `tavily`. Avoids the foot-gun where users add a key but forget
  the provider line.

## v0.19.0 — Repositioning + dual blend weights (2026-05-04)

- **REPOSITIONING:** REALM is now framed as a "collective sentiment
  simulation platform" with two distinct question types:
  - BASELINE: LLM-dominant (0.85-0.95). Sprint 18 backtest showed
    sim alone produces near-random Brier (0.247 ≈ 0.25).
  - SCENARIO: sim-dominant (0.40 LLM / 0.60 sim, science 0.50/0.50).
    Modeling agent perturbation, drift dynamics, trait clustering in
    response to injected events is REALM's unique capability.
- **Added:** `scenario_llm_blend_weight` per-category field; predict
  pipeline picks baseline vs scenario weight based on whether
  `scenario_feed` was provided.
- **Added:** `blend_category_parameters()` — Sprint 18's drift-only
  blending extended to sigmoid sensitivity, drift volatility, drift
  asymmetry, and baseline_probability_offset across multi-category
  routings (Hormuz-style cross-domain questions).
- About panel section 1 + 5 rewritten with honest backtest framing.
- Tests: 869 → 881 (+12).

## v0.18.0 — Polymarket validation, web research, multi-cat routing (2026-05-04)

- **Added:** `realm/validation/polymarket.py` — sync Gamma API client
  + `BrierResult` + `aggregate_brier`. `scripts/backtest_polymarket.py`
  runs each market through three modes (LLM+sim, LLM-only, sim-only)
  and produces a markdown report.
- **Added:** `use_llm` and `use_sim` toggles on `PredictRequest` for
  A/B comparison. `use_sim=False` short-circuits to LLM-only fast path.
- **First backtest result (5 markets, 50×10×3):** LLM-only Brier 0.117,
  LLM+sim 0.165, sim-only 0.247 → simulation ADDS NEGATIVE VALUE
  (+0.048 Brier). Honest report shipped at
  `outputs/polymarket_backtest_smoke.md`. This finding drove the
  Sprint 19 repositioning.
- **Added:** `realm/llm/web_researcher.py` — Tavily / Brave search
  backends, query generation prompt, integration into
  `QuestionAnalyzer`. Graceful fallback when no key configured.
- **Added:** multi-category routing (Sprint 18 WP3, drift-only blending).
- **Added:** root `conftest.py` resetting `REALM_LLM_CATEGORY_BACKEND=""`
  so the Sprint 17 module-level `.env` auto-load doesn't leak LLM into
  hermetic tests.
- Tests: 826 → 869 (+43).

## v0.17.0 — LLM-as-brain integration (2026-05-03)

- **LLM-first routing** in `CategoryRouter.route()` — LLM classifier
  consulted first (3-second timeout, in-process LRU cache); keyword
  matching falls back on timeout / low confidence / unknown id.
- **`QuestionAnalyzer`** (`realm/output/question_analyzer.py`) — LLM
  extracts subject, yes_means, no_means, key_factors, relevant_traits,
  llm_prior, prior_reasoning per question.
- **`ScenarioAnalyzer`** — semantic per-trait perturbation replaces
  Sprint 13's sentiment-word counting in `_make_perturbed_agent_builder`.
- **`PredictionNarrator`** — question-specific headline, key_drivers,
  dissent_view, confidence_note, caveat after the simulation completes.
- **Probability blending** — `final = (1-w) × sim + w × llm_prior`
  with per-category `llm_blend_weight`.
- **`PredictResponse`** extended additively with 12 new optional fields.
- **`scripts/calibrate_categories.py`** defensively pops
  `REALM_LLM_CATEGORY_BACKEND` so Sprint 16 calibration determinism
  is preserved.
- Politics keyword list expanded with legal terms (lawsuit, antitrust,
  court, judge, attorney, indictment, etc.). About panel gained
  "LLM Integration" section.
- Tests: 777 → 826 (+49).

## v0.16.0 — Geopolitics structural fix + Sprint 10 latent bug (2026-05-03)

- **HEADLINE FINDING:** discovered + fixed a Sprint 10 latent bug that
  silently no-op'd 9 of 15 drift events for 6 sprints. Root cause:
  `_EVENT_TRAIT_MAP` constant only held 6 Sprint 9 events; build_branch_sim
  passed no override. Fix: pass `event_map=drift_bridge.event_map`. Pre-
  Sprint-16 calibrations were running on only 6 events.
- **Added:** 3 new geopolitics-pool drift events (regime_consolidation,
  diplomatic_stalemate, sanctions_pressure) modeling status-quo
  dynamics absent from Sprint 9/10 pool.
- **Added:** `baseline_probability_offset` per-category fine-tuning
  knob (range [-0.05, +0.05], applied after sigmoid + clamp).
- **Calibration journey** (4 tiers): Tier 1 broken 49.98% → Tier 1
  corrected 49.92% → Tier 2 corrected 49.70% → Tier 3 final
  49.20% (geopolitics offset −0.005). All 8 acceptance gates pass.
- Tests: 742 → 777 (+35).

## v0.15.1 (2026-04-26) — geopolitics asymmetry retune

`_ASYMMETRY_RANGE` widened 0.5-1.5 → 0.3-1.7. Geopolitics retuned to
0.3/1.7 + negative-net drift weights + gated-rule-firing seed offsets.
Geopolitics 50.43% → 50.10%. Architectural limit documented (Sprint 16
fix). 742 tests.

## v0.15.0 (2026-04-26) — baseline differentiation

Per-category drift_volatility (0.5-2.0) + drift_asymmetry
(positive_multiplier / negative_multiplier 0.3-1.7) + sigmoid_sensitivity_multiplier
(0.5-2.0). Baseline spread 0.5pp → 4.04pp. `_BASE_DRIFT_COEFFICIENT`
0.01 → 0.025. 742 tests.

## v0.14.0 (2026-04-25) — Sprint 14 pre-release

Seven WPs shipped: category-conditioned drift event sampling, trait
seed offsets, V-Dem polarization integration, network panel category
coloring, RSS feed ingestion, validation report, Sprint 14 docs.
725 tests.

## v0.13.0 (2026-04-25) — Sprint 13 P0 fixes

Wired `ExperienceDriftEngine` into `build_branch_sim` (was permanently
off since Sprint 9), sigmoid-calibrated probability of weighted
population deviation (was saturating to 1.0), scenario_feed perturbation
on 70% of primary traits with ±0.08 floor. trait_shifts now drift-only.

## Earlier sprints

Sprints 1-12 covered phase 1-6 of the foundation: agents + astro +
personality, demographics + culture, simulation + network + transits,
ingestion + KG + news, LLM backends + Mode B/C embedders, FastAPI +
v1 dashboard + Q&A predictor, scenario panel, BlendedAdapter, BF
validity 8/8 PASS, astrological validity 4/4 PASS, FastAPI predict
endpoint v2, mock↔live toggle. See `outputs/realm_milestone_report.md`
sections 1-19 for full per-sprint detail.
