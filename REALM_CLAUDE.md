# REALM — Population-Reaction Simulation Engine

## CLAUDE.md — Project Blueprint & Development Guide

> **Version:** 0.25.0
> **Created:** 2026-04-22
> **Last Updated:** 2026-08-20 (v0.25.0 — Sprint 26: post-roadmap queue — Sweden NATO baseline corrected (42, Demoskop; dataset 22/22 verified; signed ρ −0.506); magnitude de-quantization shipped (tanh map, measured: artifact gone, still no magnitude signal −0.066); Study B grown to 6 open entries (TR/US/GB). Follows Sprint 25's blinding fix + erratum (v0.24.1).)
> **Identity note (2026-08-18):** the founding intent is population-reaction
> simulation — detecting opinions/tendencies toward events in advance.
> Astrology is ONE of four pluggable temperament-diversification modes
> (astrological / big_five real-data / demographic / blended), never the
> project's focus. See
> `docs/superpowers/specs/2026-08-18-reaction-distribution-repositioning-design.md`.
> **Author:** Loth + Claude (Anthropic)
> **License:** MIT — Copyright © 2026 Suvar Ergun. See `LICENSE`.
> **Status:** Phase 1-6 + LLM + scenario panel + Sprints 1-26 complete (§5 roadmap DONE). **1026 tests passing**, entire repo ruff clean, CI active. Sprint 16 added 3 geopolitics-pool drift event types (regime_consolidation, diplomatic_stalemate, sanctions_pressure) and a per-category `baseline_probability_offset` fine-tuning knob, but the headline finding was a **latent engine bug since Sprint 10**: `ExperienceDriftEngine._EVENT_TRAIT_MAP` only ever held the 6 Sprint 9 events, and `build_branch_sim` never passed `bridge.event_map` into the engine — so all Sprint 10 events (leadership_act, group_conformity, group_dissent, financial_loss, financial_gain, cultural_experience) had been silently no-op'd by `engine.event_map.get(event_type)` returning None for 6 sprints. Two-line fix in `realm/output/predictor.py`: load bridge first, then pass `event_map=drift_bridge.event_map`. Sprint 14/15 baseline differentiation calibrations had been running on only 6 events; Sprint 16 is the first calibration where all 15 events actually contribute to drift accumulation.

---

## 0. CURRENT BUILD STATE (2026-08-19)

### Sprint 26 — Post-Roadmap Queue: Sweden Fix + De-Quantization + Study B Growth (2026-08-20)

- **Sweden NATO baseline corrected (queue item 4):** the authored 37
  was Demoskop's January 2022 AGAINST share; FOR was 42 (The Local
  2022-03-04). Event moved to the single-pollster Demoskop series
  Jan 42 → Mar 51 (+9pp, was mixed-pollster +14pp), now verified —
  **dataset 22/22 verified**. Sign unchanged → DA stays 4/22; signed
  ρ −0.497 → **−0.506**. Valence-postfix + relation-design artifacts
  regenerated.
- **Magnitude de-quantization (queue item 3):** measured first — the
  22 design summaries produce 15 distinct sentiment scores, but
  `clamp(|s|·2, 0.08, 0.15)` collapsed them to 6 magnitudes (7 at
  floor, 5 at cap). Replaced with `0.15·tanh(|s|·2/0.15)` (same slope
  at origin, asymptotic cap, no floor; strictly monotone — 14 distinct
  magnitudes). TDD: 3 new tests (monotonicity / no-plateau / asymptote).
  **Measured outcome (comparison runs `outputs/study_a_*_dequant.*`):
  DA 4/22 unchanged, magnitude ρ −0.124 → −0.066 — artifact removed,
  and the lexicon channel STILL has no magnitude signal.** Magnitude
  claims stay off; honest completion of the queue item.
- **Study B grown 3 → 6 open entries (queue item 1):** TR TÜİK consumer
  confidence Sept-vs-Aug (P=0.527, resolve 2026-09-25); US Gallup
  presidential approval Sept-vs-Aug, Aug=34% (P=0.446, resolve
  2026-10-10); UK YouGov government approval end-Sept vs last-Aug
  (P=0.410, resolve 2026-10-05). Full pipeline (LLM+web), no scenario
  feed, consistent with the first three entries.
- **Not attempted:** matrix v2 (queue item 2) — requires authoring a
  THIRD event set under the freeze-then-author protocol; deliberately
  left for a dedicated session.

### Sprint 25 — Third Blinding Leak Fixed + Study A Erratum (2026-08-20)

- **Fix (CRITICAL):** `CategoryRouter` is LLM-FIRST (Sprint 17) and
  `predict.py` resolved it via an env-only `@lru_cache` singleton —
  `use_llm=False` never gated category routing, and category choice
  drives drift weights / sigmoid sensitivity / asymmetry. With
  `REALM_LLM_CATEGORY_BACKEND=1` in `.env` (auto-loaded at import), the
  LLM classified every blinded Study A question and re-parameterized
  the simulation. Sprint 22 gated analyzers + narrator but missed this
  third gate. Fix: `_get_offline_router()` (keyword-only) for all
  `use_llm=False` requests; multi-cat blend reads the same router; TDD
  regression test (red confirmed first). Commit 5413d7f.
- **Erratum (clean re-runs, same seed/params):** design set
  **6/22 → 4/22 (18%)**, signed ρ −0.357 → **−0.497** *(−0.506 after
  the Sprint 26 Sweden data fix)*, confidence_index
  2/2 → **0/2** (Lehman/COVID hits were LLM-routing artifacts — keyword
  routing sends consumer-sentiment questions to `balanced`, ≈+0.6pp);
  held-out **3/8 → 2/8** (Kuwait hit was the same artifact). Rally 0/9,
  approval_drop 2/5, policy_shift 2/6 unchanged. Relation channel
  unaffected (analytic). **Fourth failure mode: category dependence.**
  Errata written into all published claims (analysis, article, README,
  dashboard About, 2×2). The negative result stands and strengthens.
- **Hygiene:** stale v0.20.0/0.16.0/963-test/"Astrological Swarm"
  strings synced across REALM_CLAUDE.md, api.py, dashboard v2, README
  citation, requirements.txt (commit 56f82ce).

### Sprint 24 — Relation Channel + Repositioning + Study B Live (2026-08-19)

Closes the design doc §5 roadmap. Plan:
`docs/superpowers/plans/2026-08-19-sprint24-relation-layer-repositioning.md`.

- **Relation channel (research-only):** `realm/validation/relation.py`
  — archetype rules + literature-prior polarity matrix, FROZEN at
  commit f2df2de BEFORE the held-out set existed (auditable in git
  history). Harness `--channel valence|relation`.
- **2×2 evaluation:** valence 6/22 design, 3/8 held-out (mostly
  ±0.2pp neutral-parse noise) — *corrected by Sprint 25 erratum to
  4/22 / 2/8 after the category-routing blinding fix*; relation 20/22 design (IN-SAMPLE at
  class level — not evidence), **held-out 4/8 (p=0.637) → pre-stated
  bar (>50%, p<0.1) NOT met → not wired into the API.** Secondary:
  4/5 when committed, 3 abstentions from missing archetypes (military
  success, incumbent-initiated conquest, personal scandal) + one
  compound-event mis-sign (Afghanistan). Matrix v2 would need a THIRD
  event set (`outputs/study_a_relation_analysis.md`).
- **Repositioning (§6 unlocked):** REALM name KEPT (astrology-neutral);
  observatory title → "Population-Reaction Observatory"; README
  identity + validation-status block; v2 About heuristic caveat;
  decision recorded in design doc §7.
- **Study B live:** three open forward entries (US House 2026 P=0.698;
  UMich Sept 2026 direction P=0.563; DeutschlandTrend direction
  P=0.392). Score them as polls resolve via
  `python scripts/diary.py score <id> --observed-shift-pp X --source "..."`.
- **Post-roadmap queue:** grow Study B; matrix v2 (victory/compound
  classes) on a third event set; magnitude de-quantization; verify the
  Sweden NATO baseline.

### Sprint 23 — Official Study A Run: Published Negative Result (2026-08-18)

The central research question got its first honest answer. Full
verification pass first (21/22 events confirmed; 5 authored values
corrected, 1 metric switched — authored numbers are candidates, never
data), then the official run (100 agents / 30 ticks / 5 branches /
seed 42, all `sim_delta_isolated`):

- **DA 6/22 (27%), signed Spearman −0.357, magnitude ρ −0.105.**
  rally 0/9 · approval_drop 2/5 · policy_shift 2/6 ·
  **confidence_index 2/2**. *(Sprint 25 erratum: run was contaminated
  by the category-routing leak — clean numbers are DA 4/22, ρ −0.497,
  confidence_index 0/2.)*
- **Three failure modes** (see `outputs/study_a_analysis.md`):
  (1) referent blindness — the channel propagates event valence, but
  reactions follow the event↔subject relation (rallies, NATO,
  Fukushima all inverted); (2) parse instability — Sandy Hook +42pp vs
  Parkland −0.2pp, Nixon pardon read positive; (3) magnitude
  quantization — outputs cluster at 0/±20-29/±42-46pp (floor/cap
  artifacts), no rank signal.
- **Falsified:** the lexicon (LLM-off) scenario channel as a general
  poll-shift predictor. **Unaffected:** population realism (8/8) and
  the reaction-distribution surface. **Untested by design:** the
  LLM-informed channel — retrodiction can never blind it; Study B
  (forward diary) is now the primary evidence channel.
- `REALM_ARTICLE_DRAFT.md` fully rewritten around the
  reaction-distribution thesis with the real numbers (title:
  "REALM: A Population-Reaction Simulation Engine"); all X.XXX
  placeholders gone. Milestone report §27 added.
- **Sprint 24 candidates:** referent-relation layer (event-type ×
  question-type polarity matrix for blinded use; LLM relation forward),
  free the perturbation magnitude regime, Study B entries begin;
  dashboard About should stop presenting heuristic scenario deltas as
  poll-shift predictions (product surface work remains gated on
  evidence per design §6 — and the evidence now says negative for the
  heuristic channel).

### Sprint 22 — Study A Instruments + Study B Diary (2026-08-18)

Implements design doc §4.1/§4.2/§5 row 22. The OFFICIAL study run +
article rewrite is Sprint 23 scope. Plan:
`docs/superpowers/plans/2026-08-18-sprint22-study-a-dataset-harness.md`.

- **Dataset:** `data/validation/study_a_events.json` — 22 events,
  7 countries, mechanism-tagged (9 rally / 5 approval_drop / 6
  policy_shift / 2 confidence_index), all `sim_delta_isolated`. 9/9
  high-confidence events web-verified (Finland NATO baseline corrected
  28→30); 13 medium/low remain candidates. Sourcing + caveats:
  `docs/study_a_dataset_notes.md`.
- **Schema/loader:** `realm/validation/study_a.py` (regime enum +
  LLM-cutoff guard; leakage rules tested — summaries may not mention
  polls). **Metrics:** `realm/validation/retrodiction.py` (exact
  binomial DA, Spearman with ties, breakdowns; no scipy).
- **Harness:** `scripts/run_study_a.py` — in-process, per-event blinding
  regime, predicted = `reaction.shift.support × 100`. Blinded smoke
  (6 events, reduced params): Fukushima HIT (−27.5 vs −14), all rally
  events structurally miss (sentiment-sign mechanism cannot produce a
  rally), Ford pardon miss (parser reads "grants/unconditional" as
  positive), Falklands neutral-parse 0.00. This is the honest baseline
  the official run will quantify.
- **CRITICAL FIX (blinding leak):** `use_llm=False` previously gated
  ONLY the question analyzer (Sprint 18) — the scenario analyzer and
  narrator still made LLM calls. First smoke predicted +62pp for 9/11
  because the LLM knows the rally happened. Both components are now
  hard-gated on `use_llm`; regression test in
  `realm/api/tests/test_reaction_endpoint.py::TestBlindingGate`.
- **Study B:** `realm/validation/diary.py` + `scripts/diary.py` +
  `outputs/prediction_diary/` — append-only, immutable predictions,
  scoring only adds a resolution block; full pipeline (LLM+web on) is
  the honest configuration for forward predictions.

### Sprint 21 — Reaction-Distribution Output Layer (2026-08-18)

Implements design doc §5 row 21. **963 tests green, repo-wide ruff
clean.** Plan + step detail:
`docs/superpowers/plans/2026-08-18-sprint21-reaction-distribution.md`.

- **`PopulationSpec`** (`realm/demographics/population_spec.py`) — the
  per-question target population of design decision #2: countries/regions
  (union), age band, gender, education. `WorldGenerator` enforces it via
  bounded rejection resampling (200-draw cap + deterministic fallback);
  an unrestricted spec is byte-identical to the legacy pipeline.
  `build_branch_sim(..., population_spec=)` forwards it to every branch
  AND the 0-tick calibration baseline AND the scenario-perturbed builder.
- **`realm/output/reaction.py`** — `compute_reaction_distribution` pools
  per-agent weighted deviations across ALL branch sims (the old API
  bucket read only the last branch) and emits `ReactionDistribution`:
  stance shares, one global bucket threshold, and segments along
  country / region / age-band / gender (min 5 pooled samples, top 6 per
  dimension). `category_weights` / `effective_traits` /
  `per_agent_deviations` / `bucket_three_way` moved here from
  `api/predict.py`.
- **API:** `/api/predict` request gains `population`
  (`PopulationSpecModel`; invalid → 400), response gains `reaction`
  (+`baseline` stances and `shift` on scenario runs) and
  `population_label`. `agents_supporting/opposing/neutral` now mirror
  the pooled reaction stances (semantics change — larger sample, same
  statistic). `use_sim=False` fast path: `reaction=None`.
- **Dashboard v2:** Region Focus select is now LIVE (was cosmetic since
  Sprint 12) via `REGION_MAP` → `population.regions`; new Countries
  (ISO2) + Age Band inputs; result card renders a REACTION DISTRIBUTION
  block (stance bars, shift-vs-baseline in pp, top segments) in live and
  mock modes.

### Sprint 20 — Revival + Repositioning Design + Question-Blindness Diagnosis (2026-08-18)

First session after a 106-day freeze. **918 tests green, repo-wide
ruff clean.** Full detail in milestone report §26; design in
`docs/superpowers/specs/2026-08-18-reaction-distribution-repositioning-design.md`.

**Scientific headline — the Sprint 18 finding reinterpreted.**
`scripts/diagnose_question_blindness.py` proved baseline sim output is
**question-blind by construction** (three crypto questions →
bit-for-bit identical 0.5024; categories differ only by calibrated
offset). So "sim adds negative value (+0.048 Brier)" was a structural
tautology — diluting a question-aware LLM prior toward a per-category
constant — NOT evidence about the scenario channel, which the backtest
never exercised. All validation effort now targets the scenario DELTA
(reaction distribution), matching the founding intent.

**Second finding, fixed:** the heuristic (LLM-off) scenario path was
direction-blind — strict sentiment inventory missed panic / fear /
insolvency / optimism, and neutral parses fabricated a +0.08 positive
nudge. Now: full inventory + expanded affect terms; neutral → zero
perturbation + warning. Post-fix (50×10×3, LLM off): bullish +21.3pp,
bearish −23.1pp, neutral 0.0pp.

**Critical fixes:** web-research result now travels inside
`QuestionAnalysis` (was a cross-request race-prone side channel);
`DriftEventBridge.build_engine()` + full state round-trip + unknown-
event warnings (kills the Sprint 10 bug class — `run_simulation.py`
had still been no-opping 9 of 15 events); one strict LLM gate
(`realm.llm.router.backend_for`) replaces five copy-pasted factories,
predict.py components now lazy with no import side effects.

**Ops:** `scripts/smoke_external.py` (run after any dormant period!);
OpenAI model switched gpt-5.4 → gpt-5.6-sol (403 after freeze);
Polymarket Gamma is ISP-blocked from this network (VPN/cloud needed);
CI workflow added (ruff + pytest); deps now match actual imports;
single version source via package metadata.

**Sprint 21+ (per the design):** reaction-distribution output layer
(PopulationSpec + stance shares + segment breakdown) → Study A
(polling retrodiction, 15-30 events, blinded) + Study B (forward
diary) → article rewrite → evidence-gated renaming.

### Sprint 19 — Repositioning + Calibration + Multi-cat Full Blend (2026-05-04)

Sprint 18 backtesting found that **simulation adds NEGATIVE value to
baseline predictions** (LLM+sim Brier 0.165 vs LLM-only 0.117). Sprint
19 acts on that finding by repositioning REALM and recalibrating the
blend math accordingly.

**WP1 — Dual baseline / scenario blend weights.** Each category now
carries TWO LLM-blend weights: `llm_blend_weight` (baseline,
sim-when-no-scenario-feed) and the new `scenario_llm_blend_weight`
(scenario, sim-when-scenario_feed-supplied). Recalibrated per-category
config in `config/prediction_categories.json`:

| category    | baseline LLM | scenario LLM |
|-------------|--------------|--------------|
| science     | 0.95         | 0.50         |
| politics    | 0.90         | 0.40         |
| economics   | 0.90         | 0.40         |
| geopolitics | 0.90         | 0.40         |
| balanced    | 0.90         | 0.40         |
| crypto      | 0.85         | 0.40         |
| sports      | 0.85         | 0.40         |
| markets     | 0.85         | 0.40         |
| culture     | 0.85         | 0.40         |

Wired in `realm/api/predict.py`: when `scenario_feed` is provided the
scenario weight applies to the scenario branch's blend; the baseline
branch always uses the baseline weight.

**WP3 — Multi-category FULL parameter blending.** Sprint 18 only
blended `drift_event_weights` across multi-cat categories. Sprint 19's
new `blend_category_parameters()` extends to:
- `sigmoid_sensitivity_multiplier`
- `drift_volatility`
- `drift_asymmetry_positive` / `drift_asymmetry_negative`
- `baseline_probability_offset`

predict_endpoint applies the blended view via `dataclasses.replace`
on the CategoryMatch so all downstream code (incl. `_calibrated_outcome`)
reads the blended scalars transparently.

**WP4 — Dashboard transparency.** `askQuestion()` typewriter now
shows: web research status (`web research ACTIVE — N sources`),
server-side category override (when LLM router differs from JS preview),
and the blend transparency block (`llm prior X%`, `simulation Y%`,
`blended Z%`) — letting the user see exactly how the final number
was computed.

**WP5 — About panel REFRAMING.** Section 1 rewritten to describe REALM
as a "collective sentiment simulation platform" with two distinct
question types (BASELINE = LLM-dominant, SCENARIO = sim-dominant)
rather than a "swarm prediction engine that beats markets." Honest
limitations section adds the Sprint 18 backtest numbers verbatim.

**WP2 — Polymarket Brier methodology note.** Documented in the
backtest report: Polymarket's score in the Sprint 18 results uses
settlement price (gives perfect 0.000 Brier). Sprint 20 backlog: fetch
CLOB prices-history endpoint for last pre-resolution trading price.
The actual large backtest re-run with new blend weights is also
Sprint 20 work (50 markets × 3 modes × ~20s each = ~50 min).

**WP6 — Tests.** 869 → **881** (+12). New files:
`realm/api/tests/test_blend_weights_dual.py` (6) and
`realm/output/tests/test_multi_cat_full_blend.py` (6). Existing
`test_per_category_weight_loaded_from_config` updated for new values.

**WP7 — Docs.** This block, milestone § 25, REALM_CLAUDE.md v0.19.0,
Sprint 19 memory observation. ~~README still pointing at Sprint 17/18
narrative~~ — the README was in fact realigned to v0.19.2 later the
same night (2026-05-04 02:53); this backlog note outlived the fix.

**Known follow-ups (Sprint 20+):**
- Larger backtest run (50+ markets) with the new blend weights to
  measure whether LLM+sim ≤ LLM-only Brier (the WP1 hypothesis).
- CLOB prices-history fetch for proper Polymarket Brier methodology.
- README full reframing (Sprint 19 positioning).
- Calibration curve / per-category Brier breakdown in the report.

### Sprint 18 — Validation, Web Research, Multi-Category Routing (2026-05-04)

Sprint 17 shipped LLM-as-brain. Live testing exposed three concrete
failures that Sprint 18 addresses:

1. **No external validation.** No way to measure whether REALM is
   actually accurate. Polymarket backtesting now provides Brier-score
   ground truth.
2. **LLM prior used historical base rates.** Strait of Hormuz question:
   REALM 58.1% vs Polymarket 32% because LLM didn't know transit had
   collapsed 90%+. Web research now grounds LLM prior in current data.
3. **Cross-domain questions collapsed to "balanced".** Hormuz spans
   geopolitics + economics + markets but routing forced single-category.
   Multi-category routing now blends drift event weights across the set.

**WP1 — Polymarket backtesting infrastructure.** New
`realm/validation/polymarket.py` (sync httpx Gamma client,
`ResolvedMarket` + `BrierResult` dataclasses, parsing of
JSON-encoded outcomePrices, filters for clean YES/NO resolutions
+ min volume), `scripts/backtest_polymarket.py` (3-way A/B:
LLM+sim blended vs LLM-only vs sim-only), markdown report
generator. New `use_llm` and `use_sim` toggles on `PredictRequest`
gate the entire LLM stack and simulation pipeline independently;
when `use_sim=False` the endpoint short-circuits to an LLM-only
fast path. **First backtest result (5 markets, scale 50×10×3):
LLM+sim Brier 0.165, LLM-only 0.117, sim-only 0.247 → simulation
ADDS NEGATIVE VALUE (+0.048 Brier).** Honest report; calibration
work belongs in a future sprint.

**WP2 — Web research prior enhancement.** New
`realm/llm/web_researcher.py` with pluggable search backends
(Tavily / Brave) + `prompts/web_researcher/generate_queries.yaml`.
Flow: LLM generates 2-3 targeted queries → search returns snippets
→ snippets concatenated into context → context injected into
`prompts/question/analyze.yaml` so the LLM prior reflects current
data, not just training-data base rates. Gated by
`REALM_WEB_SEARCH_PROVIDER` + matching API key in `.env`; silently
no-ops when unconfigured (graceful degrade everywhere). New
`enable_web_research` flag on `PredictRequest` (default True);
new `web_research_used` + `web_sources[]` on `PredictResponse`.

**WP3 — Multi-category routing.** `prompts/category/route.yaml`
extended to optionally return `{"categories": [{"id":..., "weight":...}, ...]}`
for cross-domain questions. New `CategoryMatch.secondary_categories`
field stores `(id, weight)` tuples for non-primary categories.
`blend_drift_event_weights()` helper produces a weighted-average
event-weight map across all active categories, used in
`predict_endpoint` to compute the simulation's drift_event_weights.
Single-category routing (the common case) is bit-for-bit unchanged.

**Cross-cutting protections.**
- New root `conftest.py` resets `REALM_LLM_CATEGORY_BACKEND=""` at
  pytest startup so the Sprint 17 module-level `load_dotenv` in
  `realm/api/predict.py` doesn't leak LLM into hermetic tests
  (calibration determinism + routing tests).
- `.env` auto-load now happens at `realm/api/predict.py` import
  time (Sprint 17 added this earlier this session). `realm_start.bat`
  picks up LLM credentials without any extra launcher.
- Polymarket client uses `httpx.MockTransport` for hermetic tests —
  20 unit tests run in 0.2 s without touching the live API.

**WP4 — Tests.** 826 → **869** (+43). New test files:
`realm/validation/tests/test_polymarket_client.py` (20),
`realm/llm/tests/test_web_researcher.py` (12),
`realm/output/tests/test_multi_category_routing.py` (11). Plus
the 4 Sprint 17 tests that broke after `.env` auto-load were
fixed via the new conftest hermeticity guard.

**WP5 — Docs.** This block, milestone § 24, README "LLM
Configuration" + "Web Research" + "Polymarket Validation" sections.

**Sprint 18 files: ruff-clean.** Calibration regression
(`test_geopolitics_baseline.py`) still passes — Sprint 16's 49.20%
geopolitics baseline preserved.

**Known follow-ups (Sprint 19+):**
- The "sim adds negative value" finding needs deeper investigation:
  is it sim noise drowning out LLM signal, or is sim actually
  capturing useful information that just happens to disagree with
  LLM on these 5 old markets?
- Multi-category trait-weight blending (Sprint 18 only blended
  drift event weights; primary_traits + sigmoid + asymmetry
  multipliers still pull from the primary category alone).
- Dashboard display for `web_research_used` + multi-category
  breakdown currently absent (only via API response).

### Sprint 17 — LLM-as-brain integration (2026-05-03)

Pre-Sprint-17, REALM had rich LLM infrastructure (Moonshot + OpenAI
backends, prompt loader, FallbackBackend wrapper, test mocks) but the
engine barely used it: keyword routing missed legal questions, scenario
parsing was sentiment-word counting, drivers were template strings,
and there was no factual prior. Sprint 17 inverts the priority — LLM
is the primary intelligence layer when configured; today's heuristic
path is the graceful-degrade fallback.

**WP1 — LLM-first category routing.** `CategoryRouter.route()` now
calls the LLM classifier first (3-second timeout, in-process LRU
cache, gated by `REALM_LLM_CATEGORY_BACKEND`). On success with
`confidence ≥ 0.5` the LLM choice wins; on timeout / error / low
confidence / unknown id the keyword path runs unchanged. New task
constant `TASK_CATEGORY` in `realm/llm/router.py`. Politics keyword
list also expanded with legal terms (lawsuit, antitrust, court, judge,
attorney, indictment, etc.) so even the keyword fallback now catches
the original motivating example: `"Will Musk win his case?"` → politics.

**WP2 — Question analyzer + probability blending.** New
`QuestionAnalyzer` (`realm/output/question_analyzer.py`) extracts
structured info per question — subject, yes_means, no_means,
key_factors, relevant_traits, time_horizon, and a calibrated
`llm_prior`. The prior is blended with the simulation probability via
`final = (1-w)*sim + w*llm_prior`, where `w` is per-category
(`science`/`economics`/`markets`/`geopolitics` 0.7, `politics`/`culture`
0.5, `sports` 0.4, `crypto` 0.3, `balanced` 0.5 — set in
`config/prediction_categories.json`). The `simulation_probability`
(pre-blend) and `blended_probability` (post-blend) both surface on
the API response so divergence is visible.

**WP3 — Scenario analyzer (semantic perturbation).** New
`ScenarioAnalyzer` (`realm/output/scenario_analyzer.py`) replaces
`_perturbation_for_feed()`'s sentiment-word counting with a semantic
LLM read of `scenario_feed`: `direction` ∈ {increases, decreases,
mixed}, `magnitude` ∈ {slight, moderate, strong}, per-trait
`trait_impacts` (clamped ±0.15), and `affected_population_pct`
(clamped [0.1, 0.95]). `_make_perturbed_agent_builder()` accepts the
analysis and applies per-trait deltas to the affected fraction. When
LLM is unavailable / fails the pre-Sprint-17 sentiment-word path runs
unchanged.

**WP4 — Prediction narrator.** New `PredictionNarrator`
(`realm/output/prediction_narrator.py`) produces a question-specific
narrative after the simulation completes — `headline` (with
probability), `key_drivers` (3-4 specific bullets, no generic
templates), `dissent_view`, `confidence_note`, `caveat`. The narrative
fields land on `PredictResponse` (additive — clients that only read
`.probability` work unchanged).

**WP5 — Dashboard LLM-aware display.** `askQuestion()` typewriter
in `realm_dashboard_v2.html` renders the LLM headline first, shows
both `simulation_probability` and `blended_probability` alongside the
final probability, prefers `narrative_drivers` over template
`drivers` when present, and renders the LLM `dissent_narrative` /
`confidence_note` / `caveat` when populated. About panel gained an
"LLM Integration" subsection.

**WP6 — Graceful degradation.** Every analyzer wraps `complete_json`
in try/except + schema validation; returns `None` on any failure path
so callers fall through to today's behavior. Startup log prints one
line: `"[REALM] LLM backend ACTIVE/INACTIVE — ..."`.
**`scripts/calibrate_categories.py` defensively clears
`REALM_LLM_CATEGORY_BACKEND`** from `os.environ` at startup so
calibration mechanics stay deterministic regardless of the dev's
shell — Sprint 16's geopolitics 49.20% is protected.

**WP7 — Tests.** 777 → **826** (+49). Five new test files:
`test_llm_category_routing.py` (10 tests), `test_question_analyzer.py`
(8 tests), `test_scenario_analyzer.py` (12 tests),
`test_prediction_narrator.py` (9 tests), `test_probability_blend.py`
(9 tests). All hermetic — every test injects a `_ScriptedBackend`
mock. The pre-existing Sprint 11 `test_category_router.py` LLM
fallback class was renamed `TestLLMFirst` and its assertions inverted
to match the new priority. Calibration regression tests
(`test_geopolitics_baseline.py`, `test_calibration_spread.py`)
unchanged and still produce the Sprint 16 numbers — proves the
keyword path is bit-for-bit preserved when no LLM is wired.

**WP8 — Documentation.** This block, milestone § 23, README LLM
configuration section.

**Sprint 17 files: ruff-clean.** Calibration regression at 200×30×5×10
verified within ±0.5pp of Sprint 16 baseline.

### Sprint 16 — Geopolitics structural fix + latent engine bug discovery (2026-05-03)

Sprint 15 v0.15.1 hotfix left geopolitics at 50.10% — under 50% but
above the prompt's `<49.5%` strict target. Sprint 16 attacked the root
cause and uncovered something much bigger along the way.

**WP1 — Three new drift event types** in `config/drift_events.json`:
`regime_consolidation`, `diplomatic_stalemate`, `sanctions_pressure`. All
three model status-quo / non-escalation geopolitical dynamics that the
Sprint 9/10 event pool lacked, with primary-net-negative effects on the
geopolitics primary trait set (authority_compliance / social_dominance /
contrarian_tendency / empathy / risk_appetite). Each event has `post`
and `engage` rules placed AFTER the legacy `positive_social_fallback_*`
rules so first-match-wins is preserved; weighted sampling picks them up
via per-category `drift_event_weights`.

**WP2 — `baseline_probability_offset`** per-category knob (range
`[-0.05, +0.05]`), validated in `CategoryRouter._validate_categories`,
extracted in `_build_match()`, applied in `realm/api/predict.py` AFTER
sigmoid + clamp, then re-clamped to `[0.05, 0.95]`. Defaults to 0.0 for
every category — the design intent is that drift mechanics carry the
load and offset is only the last-mile cleanup.

**WP3 — Calibration journey, root-cause-first.** Loth's correction to
the original plan: exhaust structural fixes (5× magnitude scaling) before
reaching for the cosmetic offset, and log every step. Four tiers at
200×30×5×10:

| tier | engine | new-event mag | offset | geopolitics | spread |
|------|--------|---------------|--------|-------------|--------|
| 1 (broken engine) | 6 events | spec 0.02–0.04 | 0.0 | 49.98% | 3.27pp |
| 2 (broken engine) | 6 events | 5× (0.10–0.20) | 0.0 | **49.98%** ← bit-identical → bug | 3.27pp |
| 1 corrected | 15 events | spec | 0.0 | 49.92% | 3.47pp |
| 2 corrected | 15 events | 5× | 0.0 | 49.70% | 3.64pp |
| 3 final | 15 events | 5× | −0.005 (geo only) | (calibration confirms) | (≥3.6pp) |

The bit-identical Tier 1/Tier 2 result with explicitly different
magnitudes was the diagnostic that surfaced the Sprint 10 bug. Without
the root-cause-first correction, I would have collapsed straight to
offset and missed the real fix entirely.

**ENGINE BUG DETAIL.** `realm/simulation/drift.py` defines
`_EVENT_TRAIT_MAP` as a constant holding only the 6 Sprint 9 events.
`ExperienceDriftEngine` defaults `event_map = _EVENT_TRAIT_MAP` if no
override is passed. `build_branch_sim()` in `realm/output/predictor.py`
constructed the engine WITHOUT passing `event_map`, so Sprint 10's
6 events (leadership_act / group_conformity / group_dissent /
financial_loss / financial_gain / cultural_experience) and Sprint 16's
3 events were silently no-op'd by `engine.event_map.get(event_type)`
returning `None` and the early-return `if not weights: return`.
**Sprint 14 weighted sampling and Sprint 15 baseline differentiation
were both running on only 6 events** — the Sprint 10 expansion never
reached the engine. The fix is two lines:

```python
# realm/output/predictor.py — build_branch_sim
drift_bridge = DriftEventBridge.default()  # MOVED before engine
if drift_event_weights:
    drift_bridge = drift_bridge.with_weights(drift_event_weights)
drift_engine = ExperienceDriftEngine(
    ...,
    event_map=drift_bridge.event_map,  # ← was missing
)
```

This is the root cause of why Sprint 14/15 couldn't get geopolitics
under 50% no matter how aggressively asymmetry was tuned: the most
geopolitics-relevant events (failed_risk weight=3.0, financial_loss
weight=3.0, group_conformity weight=3.0) were Sprint 10 additions and
were not actually firing.

**WP4 — Tests.** 742 → **777** (+35). New files:
`realm/simulation/tests/test_new_drift_events.py` (17 tests),
`realm/api/tests/test_baseline_probability_offset.py` (11 tests),
`tests/test_geopolitics_baseline.py` (2 tests). Five existing tests
adapted for the 15-event bridge (test_drift_bridge.py +
test_drift_event_weights.py).

**WP5 — Dashboard.** SAMPLE_PREDICTIONS geopolitics + scenario mocks
updated to reflect Sprint 16 baselines. About panel + boot screen +
stack info: "12 event types" → "15 event types" in 3 places.

**Sprint 16 files: ruff-clean.**



**Phases complete:**
- ✅ Phase 1 — core + astro + personality (rule-based) (143 tests)
- ✅ Phase 2 — demographics + culture + agents (65 tests)
- ✅ Phase 3 — simulation + network + transits + platforms + checkpoint (45 tests)
- ✅ Phase 4 — ingestion + KG + news channel + mood contagion (47 tests)
- ✅ Phase 4-LLM — Moonshot+OpenAI+Ollama backends, Mode B/C embedders, spotlight, prompts/ YAML (62 tests)
- ✅ Phase 5 — collective climate (outer planets, moon, eclipse, retrograde) (17 tests)
- ✅ Phase 6 — FastAPI + D3.js dashboard + Q&A predictor + report generator (38 tests)
- ✅ Phase 6b — scenario/what-if panel with baseline vs scenario side-by-side
- ✅ **Trait variance fix (2026-04-24)** — DAMPENING 0.12→0.40, opt-in soft-rescale calibration layer, Phase 1 diagnostic + Phase 4 validation (10K agents). Source σ 0.067 → post-cal 0.160, 23/24 traits at target. Jobs directional invariance preserved (Spearman ρ=0.999). `realm/personality/calibration.py` (7 tests), `scripts/diag_variance.py`, `scripts/validate_trait_distribution.py`.
- ✅ **InputAdapter layer (2026-04-24)** — pluggable trait sources above `IPersonalityEmbedder`. Three adapters: `AstrologicalAdapter` (wraps existing embedder, default), `BigFiveAdapter` (OCEAN scores → 24 traits via literature-sourced `data/personality/big_five_derivation.json` with DOI citations), `DemographicAdapter` (Hofstede+religion+region as primary signal, skips CulturalModifier to avoid double-counting). Config key: `realm.personality.adapter`. `realm/personality/adapters/` package, 37 new tests.
- ✅ **BF validity study synthetic (2026-04-24, Sprints 3-4)** — N=10K synthetic OCEAN population, 4 pipeline configs, 10-section report. Source-aware TraitCalibrator (`config/trait_calibration_{type}.json` per adapter). Synthetic: 7/7 criteria PASS under adapter-aware calibration.
- ✅ **BF validity study real (2026-04-24, Sprints 4-5)** — automoto/big-five-data N=10K stratified study; real 5/8 PASS → 6/8 under source-aware calibration. Calibrator-synth-bias + mean-drift documented as honest FAILs.
- ✅ **Sprint 5 (2026-04-24)** — `BlendedAdapter` (60% astro + 25% BF + 15% demographic, weight renormalisation on missing components, deterministic Gaussian noise per-agent-seed). Country coverage 30 → 66 (+53K real rows). Johnson IPIP-NEO-120 facet-derivation audit: 10 PASS / 3 WARN / 0 FAIL. 566 tests green.
- ✅ **Sprint 6 (2026-04-24)** — 3 WARNs → 13/13 PASS with explicit facet citations in `data/personality/big_five_derivation.json`. Facet-level BigFiveAdapter shipped (`use_facets` config toggle, backwards-compatible OCEAN path). Johnson real validity 8/8 under facet mode + contemporary online-sample tolerance (Criterion #8a vs 1992 Costa-McCrae intentionally left failing as sample-drift indicator). 575 tests green.
- ✅ **Sprint 7 (2026-04-24)** — First astrological validity benchmark. `data/validation/celebrity_profiles.json` (20 figures × 23 traits, 50.4% high / 40.0% medium / 9.6% low confidence). `scripts/generate_celebrity_astro_profiles.py` + `scripts/validate_astro_study.py`. All 4 criteria PASS: Directional Accuracy 0.682 / Pearson r 0.268 / Extreme-Trait Detection 0.766 / Confidence-Weighted DA 0.754. Best-mapped: `communication_assertiveness` (1.00), `persuasion_skill` (1.00). **Worst: `loss_aversion` (DA=0.05, non-fallback) — Sprint 8 backlog.** `outputs/astro_validity_study.md` (9 sections) + `outputs/astro_validity_metrics.json`. 598 tests green.
- ✅ **Sprint 8 (2026-04-24)** — Mapping fix + calibration methodology + observatory dashboard. **WP1:** added semantic counter-planet contributors to `loss_aversion` in `data/astro/planet_trait_map.json` — Mars −0.45, Jupiter −0.25, Uranus −0.30 (Saturn kept at +0.55 as the principled anchor); **loss_aversion DA 0.05 → 1.00** without any calibration. **WP2+WP3:** added three-mode `--calibration=` flag (`none` default, `variance`, `full`) to the generate script with an adaptive-boundary variance expander; grid search revealed that *any* calibration mode degrades celebrity-validation metrics because celebrities are a selection-biased subsample — **calibration is a simulation tool, not a validation tool**, decided and documented. **WP4a:** Sprint 7→8 lift — DA +0.040, Pearson +0.054, Extreme +0.036, CW-DA +0.035, non-fallback +0.051. **WP4b:** `outputs/realm_dashboard.html` — 47 KB single-file Neural Observatory dashboard. D3.js v7 force-directed Agent Synapse Network (8 hand-authored archetypes, bioluminescent signal particles along gradient edges), sticky scoreboard with glow badges, per-trait DA grid, per-person ranked bars, sprint-comparison strip, BF validity checklist — dark space theme + cyan/magenta/amber/violet accents, JetBrains Mono display + DM Sans body. 598 tests green.
- ⏳ Phase 7 — POLYLIQ/ARGUS stubs (deferred)

**Current test total: 1022 passing (+24 in Sprint 24, +35 in Sprint 22, +40 in Sprint 21, +36 in Sprint 20, +12 in Sprint 19, +43 in Sprint 18, +49 in Sprint 17, +35 in Sprint 16, +17 in Sprint 15, +37 in Sprint 14). Sprint 20: entire repo ruff clean (the ~8 pre-existing errors in `tests/test_core_smoke.py` were fixed for CI) and `ruff check .` + `pytest -q` now run on every push via `.github/workflows/ci.yml`.**

### v0.15.1 hotfix — Geopolitics asymmetry retune (2026-04-26)

Sprint 15 left geopolitics at 50.43% baseline (target was <50% for status-quo bias). Hotfix:

1. **`_ASYMMETRY_RANGE` widened 0.5–1.5 → 0.3–1.7** in `realm/output/category_router.py` so domains with strong status-quo bias have headroom to push asymmetry further.
2. **Geopolitics retuned** to vol 0.5 / asym 0.3/1.7 / sigmoid 0.5 + drift_event_weights biased toward negative-net rules (failed_risk 3.0, group_conformity 3.0, financial_loss 3.0; positive_social 0.3) + seed_offsets shifted to amplify gated rule firing (risk_appetite +0.04, loss_aversion +0.04, contrarian -0.04, empathy -0.04).
3. **Economics nudged** to asym 0.5/1.5 (slightly stronger institutional conservatism).

**Result @ 200×30×5, 5 runs/category:** geopolitics mean 50.43% → **50.10%** (0.33pp toward target; min run 49.81%). Spread maintained at **4.11pp ≥ 3pp** ✅, all sanity ordering preserved, 742 tests still green.

**Architectural finding (honest):** the stated `<49.5%` target is not reachable via the asymmetry mechanism alone. Most drift events in `config/drift_events.json` have positive net coefficients on geopolitics primary traits (∑pos=5.1 vs ∑neg=1.7 magnitude), and the dominant fallback rule (`positive_social_fallback_post`) always matches any post action regardless of trait state. Asymmetry can only DAMPEN positive drift toward zero, not reverse it. Real status-quo bias would require either:

- New drift event types with negative-net coefficients on the common geopolitics primaries (authority/dominance/contrarian/empathy/risk_appetite), OR
- A direct `baseline_probability_offset` field that shifts the post-sigmoid probability without going through drift accumulation, OR
- Restructuring the rule firing conditions so negative-net events fire as often as fallback positive_social.

Sprint 16+ backlog. Shipping v0.15.1 with the maximum push achievable inside the original scope.

### Sprint 15 — Baseline differentiation fix (2026-04-26)

Sprint 14's WP1+WP2 wired the machinery for category-conditioned drift but
the production weights shipped with `pos:neg = 1:1` and a single global
sigmoid sensitivity, so baseline probabilities clustered within ~1pp of
50% across categories. Sprint 15's single goal: hit the **≥3pp baseline
differentiation** acceptance gate with no scenario-flow regressions.

Three layered knobs added per category:

- **drift_volatility (0.5..2.0)** — scales BOTH the cumulative drift cap
  (`max_drift_ratio × volatility`) AND the per-event speed (a new
  `intensity_scale` field on `ExperienceDriftEngine`). Crypto ships at 1.6,
  politics at 0.5.
- **drift_asymmetry (positive_multiplier / negative_multiplier ∈ 0.5..1.5)**
  — applied PER-EVENT based on the event's net signed effect on the active
  category's primary traits. Events that push primaries up are scaled by
  `positive_multiplier`; events pushing primaries down by
  `negative_multiplier`. Plumbed via a new `primary_trait_set` field on
  `ExperienceDriftEngine`. Science ships at 1.5/0.5 (progress bias),
  politics 0.5/1.5 (incumbency drag), geopolitics 0.5/1.5 (status-quo).
- **sigmoid_sensitivity_multiplier (0.5..2.0)** — scales the predict.py
  sigmoid sensitivity (8.0 base) per category so volatile domains have
  steeper probability curves and stable domains keep deviations near 50%.

Plus one global physics tweak: `_BASE_DRIFT_COEFFICIENT` 0.01 → 0.025 so
asymmetry and volatility have enough per-tick headroom to bias the
population mean within the 30-tick horizon. The cumulative cap still
binds asymptotically (asymmetry can only push so far).

**Sprint 15 measured @ 200×30×5 (3 runs/category, calibration log):**

| category    | mean | std | volatility | asymmetry | sens |
|-------------|------|-----|------------|-----------|------|
| politics    | 50.20% | 0.12pp | 0.5 | 0.5/1.5 | 0.5 |
| economics   | 50.50% | 0.21pp | 0.7 | 0.6/1.4 | 0.7 |
| geopolitics | 50.43% | 0.16pp | 0.6 | 0.5/1.5 | 0.6 |
| crypto      | 51.16% | 0.42pp | 1.6 | 1.0/1.0 | 1.6 |
| culture     | 51.58% | 0.38pp | 1.3 | 1.4/0.6 | 1.3 |
| sports      | 51.95% | 0.66pp | 1.4 | 1.0/1.0 | 1.4 |
| markets     | 52.33% | 0.32pp | 1.4 | 1.3/0.7 | 1.4 |
| science     | 54.24% | 0.53pp | 1.0 | 1.5/0.5 | 1.5 |

**Spread = 4.04pp ≥ 3pp gate ✅**

Live A/B (server, real curl): 4 baseline questions span 50.28% (politics) → 54.86% (science) = **4.58pp spread**, all sanity ordering preserved (crypto std > politics std, geopolitics ≤ science, no probability exactly 0.5).

Scenario deltas now scale with category volatility (this is the design intent, not a regression):

| category    | scenario delta range |
|-------------|----------------------|
| politics    | ±7-8pp |
| economics   | ±10-11pp |
| crypto      | ±20-23pp |

The "10-20pp scenario delta" Sprint 14 acceptance window is now domain-relative — high-volatility crypto reaches the upper edge by design while low-volatility politics tightens to ±7pp. Direction consistency 8/8, max trait_shift bounded by `volatility × 0.10` cap as expected.

### Sprint 14 — Pre-release consolidation (2026-04-25)

Seven work packages, all shipped:

- **WP1 — Category-conditioned drift event sampling.** `DriftEventBridge` gained an optional `event_weights` constructor field; `event_for(decision, traits, rng)` collects all matching rules and samples one weighted by its event_type's category weight. Legacy first-match-wins preserved when `event_weights=None` (backward compatible). 8 chi-squared / regression tests pass.
- **WP2 — Category-aware initial trait seed offsets.** `AgentFactory(seed_offsets=...)` applies a small zero-sum (±0.02-0.05) trait nudge AFTER the political_spectrum override. Validation at config-load: zero-sum invariant `|sum| < 0.01`, per-trait magnitude ≤ 0.05, valid trait names. The 0-tick reference baseline now also applies offsets so `trait_shifts` reports drift only.
- **WP3 — V-Dem political polarization integration.** `data/external/vdem_scores.json` curated for 66 countries (V-Dem v13 directionally aligned values; raw CSV extraction TBD). DemographicAdapter blends 60% Hofstede (production 0.35/0.25 coefficients preserved) + 40% (1 - V-Dem libdem) — inversion makes the two signals stack rather than cancel. **political_spectrum spread: 0.41 → 0.55**, Pearson(Hofstede, blend) = 0.88, Scandinavian-vs-Gulf extremes preserved.
- **WP4 — Network panel category-aware coloring.** `outputs/realm_dashboard_v2.html`: `animateNetworkPrediction()` and `drawNetwork()` accept a `colorTrait`; the panel label `coloring by: <trait>` updates per category, plus a static legend below the canvas. Mock mode preserved.
- **WP5 — RSS feed integration.** `realm/ingestion/sentiment.py` extracts the BASE word lists (Sprint 13 contract preserved) plus DOMAIN extensions for crypto/politics/culture. `realm/ingestion/feed_parser.py` is a thin orchestration layer reusing the existing `RssFeedSource`. New endpoints: `POST /api/feed/parse` (text / RSS URL / multi-text), `GET /api/feeds`. Dashboard scenario panel gains 3-radio source selector. Optional LLM path via `prompts/feed_parser/analyze_feed.yaml`.
- **WP6 — 10K×50 validation.** `scripts/validate_sprint14.py` runs 8 baseline + 16 scenario predictions and writes `outputs/sprint14_validation_report.md`. Default scale 200×30×5 (~5 min). Full scale 10K×50×5 (~13.6 hr) is a flagged opt-in run.
- **WP7 — Documentation + release prep.** REALM_CLAUDE.md → v0.14.0, §20 milestone report, new `README.md` with showcase-only banner + License TBD placeholder, `.gitignore` updated, `pyproject.toml` adds explicit `feedparser>=6.0`, `requirements.txt` refreshed.

**Sprint 14 acceptance gates measured at 200×30×5 (full report in `outputs/sprint14_validation_report.md`):**

| gate | target | measured | status |
|------|--------|----------|--------|
| scenario direction consistency | ≥6/8 categories | **8/8** | ✅ |
| max trait_shift across 24 runs | ≤ 0.10 | 0.0237 | ✅ |
| political_spectrum spread (V-Dem blend) | > 0.41 | 0.5512 | ✅ |
| baseline differentiation spread | ≥ 0.10 | 0.009 | ⚠️ below at 200 agents |

The baseline-spread gate is the only one not met at 200×30×5. The honest reason: at small scale the `positive_social_fallback` / `negative_social_fallback` rules dominate event sampling, and most categories ship with `pos:neg = 1:1` weights so the per-tick drift cancels. The WP1 weighted-sample machinery is wired correctly (verified by the 8 chi-squared tests + the 12-15pp scenario deltas), but reaching ≥10pp baseline differentiation requires either calibration tuning of the fallback weights or more topic-conditioned agent decisions — both are post-release work, documented in §13 (Future Roadmap).

- ✅ **Sprint 9 (2026-04-24)** — Four work packages shipped.
  1. **WP1 Negative-Pearson mapping enrichment.** Added semantic counter-planets for empathy (Mars -0.35, Saturn -0.30), social_dominance (Moon -0.20, Neptune -0.25), analytical_depth (Moon -0.30). Per-trait wins: empathy r -0.302 → +0.023 (Δ+0.325), σ 0.02 → 0.092 (4.6× expansion, hits the >0.08 target). social_dominance r -0.335 → -0.179 (Δ+0.156). analytical_depth r -0.324 → -0.175 (Δ+0.149). Iteration rule discovered: persuasion_skill/comm_assertiveness/contrarian_tendency counters hurt overall Pearson on celebrity cohort; reverted — these traits' negative Pearson is a selection-bias artefact (famous figures truly cluster high), not a mapping gap.
  2. **WP2 Pre-1800 ephemeris + cohort restore.** Installed `seas_12.se1` to `.venv/Lib/site-packages/kerykeion/sweph/`. Napoleon Bonaparte (1769) and Leonardo da Vinci (1452) added to `data/validation/celebrity_profiles.json` with 23 biographically-sourced expected traits each. Substitute figures (Roosevelt/Edison/Mandela) retained to enable S7/S8 vs S9 comparison → cohort N=20 → N=22. Napoleon DA=0.773 r=+0.603 (top decile). Leonardo DA=0.636 r=+0.231 (median). Cleopatra (69 BC) still excluded — Python `datetime.MINYEAR=1`.
  3. **WP3 Experience drift engine.** `realm/simulation/drift.py` — `ExperienceDriftEngine` with 6 event types (positive_social, negative_social, successful_risk, failed_risk, knowledge_acquisition, stress_crisis), deterministic accumulative drift, ±max_drift_ratio clamp (default 0.10), JSON serialisable state (`to_state`/`from_state`), 22 unit tests. Wired opt-in into `SimulationEngine.drift_engine`. Original `Agent.traits` untouched (frozen dataclass preserved).
  4. **WP4 10K-agent full simulation.** `scripts/run_simulation.py` — 10K agents × N ticks with drift enabled, cProfile bottleneck analysis, per-tick timing, JSON checkpoints every 10 ticks, population + drift + country summary outputs. Calibrated against 1K × 50 run: 303s simulation, 68MB peak memory, 6s/tick. Bottleneck (94% of tick time): `transit_modulator.compute_modifiers` → `aspect_calculator.find_transit_aspects`. 10K × 30 ticks scaled accordingly to stay under 30-min budget.

- ✅ **Sprint 13 (2026-04-25)** — Three P0 prediction-engine bug fixes + startup script. Live API now produces calibrated, directionally consistent predictions instead of degenerate 100% saturations.
  1. **Bug 2 — Drift engine wired into the predictor pipeline.** `build_branch_sim()` was creating `SimulationEngine` instances with `drift_engine=None` (Sprint 9 made it opt-in), so the predictor pipeline NEVER actually moved agent traits. The API's `trait_shifts` field was reporting `population_mean - 0.5` (baseline distribution skew, mislabelled as drift) which produced spurious +0.34 shifts. Fix: `build_branch_sim` now wires `ExperienceDriftEngine(max_drift_ratio=0.10)` + `DriftEventBridge.default()` by default. Measured at 50 agents × 30 ticks: max per-agent per-trait drift = **0.0370** (well under the 0.10 cap); population-level shifts cluster ±0.005 due to natural cancellation across drift directions.
  2. **Bug 1 — Calibrated probability via sigmoid of weighted population deviation.** Sprint 11's `observe_category_consensus` returned raw weighted trait means (typically 0.55–0.85 for the AstrologicalAdapter baseline distribution); compared against a fixed 0.55 threshold, every branch voted "yes" and `probability` saturated to 1.0. Fix: the API endpoint now (a) runs a 0-tick reference sim to capture the **unperturbed tick-0 baseline** trait means, (b) computes per-branch weighted population deviation from that baseline, (c) maps the mean deviation through `sigmoid(8 × deviation)`, (d) clamps to `[0.05, 0.95]`. The 3-way `agents_supporting / opposing / neutral` bucket is derived from per-agent deviations with threshold = `0.5 × population_stdev(deviations)`. Confidence label now reflects distance from 50% (was: raw branch stdev, which mistook saturation for confidence). Measured: crypto baseline 50.4%, politics baseline 50.3% — both within 15-85%, both with non-zero 3-way splits, neither saturated.
  3. **Bug 3 — Scenario perturbation via category-aware agent_builder.** The Sprint 12 endpoint passed `scenario_feed` through a single neutral-sentiment `SeedEvent`, which propagated through the news channel + KG but produced ~zero trait delta. Fix: a new `_make_perturbed_agent_builder(feed, category)` parses sentiment from the feed (positive/negative word lists with a `_MIN_PERTURBATION = 0.08` floor so a supplied feed always moves the needle, capped at `±0.15`), then perturbs **70% of agents** (deterministic via seed) on the active category's primary traits. The remaining 30% are baked-in skeptics — they guarantee a visible 3-way split. Live measured: dovish Fed feed → economics probability 50.7% → **65.1% (delta +14.4%)**; hawkish Fed feed → **35.5% (delta -15.2%)**. Opposite directions, both meaningful magnitudes.

  Honest limitation: with the Sprint 12 production-default agent population, baseline category drift is small (±0.005 typical), so questions in different categories return probabilities that cluster within 1pp of 50%. The perturbed scenario branches produce the meaningful ±14pp deltas. Per-category baseline differentiation requires either more aggressive drift events (Sprint 14) or category-aware agent generation (Sprint 14+ backlog).

  **`realm_start.bat`** at the project root now starts FastAPI :8420 + an `http.server :8080` for the dashboard, opens the browser, and cleanly tasks-kills both windows on user keypress.

  **Live A-D smoke (acceptance):** Test A 50.4%, Test B 50.3%, Test C delta +14.4%, Test D delta -15.2%. All trait_shifts ≤ 0.0124 (within the 0.10 cap). All sup/opp/neu non-zero. 688 tests still green; ruff clean on `realm/api/predict.py` and `realm/output/predictor.py`.

- ✅ **Sprint 12 (2026-04-25)** — Four work packages shipped: responsive v2 dashboard + live FastAPI prediction endpoint + dashboard mock↔live toggle + production-pipeline political_spectrum override.
  1. **WP1 Responsive CSS.** `outputs/realm_dashboard_v2.html` previously broke below ~900 px. Added mobile-first breakpoints at ≤640 px (tabs wrap, config inputs full-width, About body uses `white-space: pre-wrap` so ASCII boxes re-flow without horizontal scroll, network canvas drops to 260 px, IBM Plex Mono font shrinks one step) and a tablet break at 641-1024 px (canvas 340 px, panel padding shrinks). `resizeCanvas()` now reads `window.innerWidth` and matches the CSS heights; a `window.resize` listener re-paints the network when the breakpoint flips. No JS dependency added; aesthetic preserved.
  2. **WP2 `realm/api/predict.py`.** New FastAPI app exposing `POST /api/predict` and `GET /api/health`. Wraps `default_router()` + `observe_category_consensus` and re-runs the last branch to capture agent trait stats — these synthesise the dashboard-shape fields the bare `PredictionOutcome` doesn't carry (drivers / dissent / agents_supporting / opposing / neutral / answer text / confidence string / per-primary-trait shifts). CORS is wide-open for local dev with a TODO for production lockdown. Pydantic validation enforces 10 ≤ n_agents ≤ 2000, 5 ≤ n_ticks ≤ 100, 1 ≤ n_branches ≤ 20, 1 ≤ question length ≤ 500. Scenario flow re-runs the engine with a `SeedEvent`-wrapped feed and returns both `baseline_probability` and `delta`. Run with `.venv/Scripts/python.exe -m uvicorn realm.api.predict:app --host 127.0.0.1 --port 8420 --reload`.
  3. **WP3 Dashboard mock↔live toggle.** Boot screen gains a `Prediction Mode` dropdown (`Demo (mock data)` / `Live (FastAPI backend)`); when live is chosen an `API Endpoint` input becomes visible, default `http://127.0.0.1:8420`. New `STATE.mode` / `STATE.apiUrl` / `STATE.apiHealthy` fields plus a topbar `mode: mock/live/live (error)` chip that updates after every API call. `askQuestion()` and `runScenario()` route through a shared `fetchPrediction({question, scenarioFeed})` helper that POSTs to `/api/predict`, falls back to the matching `SAMPLE_PREDICTIONS[...]` mock on any error, and emits a typewriter-line breadcrumb (`fallback: showing mock data for crypto`) so the user always sees what happened. Network errors never freeze the UI.
  4. **WP4 Production-pipeline `political_spectrum` override.** Sprint 11 WP4 added a Hofstede pdi+idv override to `DemographicAdapter`, but the production `AgentFactory` defaults to `AstrologicalAdapter` which leaves `political_spectrum` at the TraitVector default 0.5 — so the live API surfaced σ=0.00 across the population, masking the new variance. Moved the override into `AgentFactory.build()` immediately after the calibrator so it fires for ALL adapter paths (astrological / big_five / blended / demographic). Measured at production-default settings: `political_spectrum mean 0.602 σ 0.095 range 0.358-0.699 (25 unique values across 80 agents)`. The duplicate override was removed from `BlendedAdapter.build()` to keep one source of truth. All 688 tests still green; ruff clean on all Sprint 12 files.

  **End-to-end smoke** (uvicorn on 127.0.0.1:8420):
  - `GET /api/health` → 200, lists 9 categories.
  - `POST /api/predict` politics, n=80 → drivers cite `political_spectrum mean 0.59 σ=0.11 (elevated, moderate spread)` — proves the production override is live.
  - `POST /api/predict` economics + `scenario_feed=Fed announces emergency rate cut...` → category routes correctly, baseline + scenario both run, `delta` field populated. (At small N the threshold-crossing aggregator can saturate to 1.0 on both sides; per-agent supporting/opposing/neutral aggregation is Sprint 13 follow-up.)
  - `POST /api/predict` empty question → 422 validation rejection.

- ✅ **Sprint 11 (2026-04-25)** — Seven work packages shipped: prediction-category routing + per-category trait weighting + ABOUT panel + political_spectrum unblock.
  1. **WP1 `config/prediction_categories.json`.** Schema v1, 9 categories (politics / economics / crypto / sports / markets / culture / science / geopolitics + `balanced` fallback). Each carries `trait_weights.{primary,secondary,suppressed}` (validated against `TraitVector.trait_names()` at load — unknown trait names fail loud), `keywords` for routing, `subcategories` for finer detection, and `default_horizon_ticks`. `balanced` is required to be the last entry; the loader asserts this so the router fallback always finds it.
  2. **WP2 `realm/output/category_router.py`.** `CategoryRouter.route(question) → CategoryMatch` with deterministic-first routing. Word-boundary regex with trailing-`s?` defeats two false-positive classes (`un` inside `country`, `oscars` not matching `oscar`). LLM fallback is opt-in: `default_router()` only wires `LLMRouter().for_task(TASK_PARSER)` when env var `REALM_LLM_CATEGORY_BACKEND` is set AND `is_llm_configured()` returns True — keeps the test suite hermetic by default. When best ≥ 2 hits AND best ≥ 2× second-best, return directly; otherwise consult LLM (if available) or return `balanced`.
  3. **WP3 `observe_category_consensus(category)` + `Question.category` round-trip.** Critical semantic correction: scaling every agent's contribution to a single trait by 2× is mathematically inert (`Σ(2·xᵢ) / Σ(2) = Σxᵢ / N`), so weighting must happen *across* trait dimensions, not within one. The new observer in `realm/output/predictor.py` computes `agent_score = Σ(wₜ · agent.traits[t]) / Σ(wₜ)` over `primary ∪ secondary ∪ suppressed` with `wₜ = 2.0/1.0/0.25`. A politics question and a crypto question produce *different consensus numbers from the same population*. `PredictionEngine.run` accepts an optional `category=` kwarg; `predict()` gains `route_category=False` (additive, default behaviour preserved).
  4. **WP4 `political_spectrum` from Hofstede pdi+idv.** Was hard-coded 0.5 across all 66 countries (silently disabling politics-domain prediction differentiation). `realm/personality/adapters/demographic.py` now overrides per-country: `Δ = 0.35·(pdi/100 − 0.5) − 0.25·(idv/100 − 0.5)`, clamped to [0, 1]. **Measured spread across 66 countries: Denmark 0.328 → Malaysia 0.735 (0.41 spread, mean 0.541, stdev 0.121, 57 distinct values).** Framing is explicit: country-level dispersion proxy, not a left/right label and not a polarization measurement. Vendoring V-Dem / Pew remains Sprint 12 backlog.
  5. **WP5 v2 dashboard `04 About` tab + per-category typewriter.** `outputs/realm_dashboard_v2.html` (IBM Plex Mono terminal aesthetic preserved): new `04 About` nav tab triggers a one-shot typewriter render of six sections (What is REALM / Trait Diversification / How Prediction Works / Validation / Limitations & Honest Boundaries / Technical Summary) with explicit honesty about the political_spectrum proxy and the yes/no aggregator gap. Inline `PREDICTION_CATEGORIES` constant + `routeCategory(q)` JS port (no LLM in browser). `STATE.activeCategory` set in `askQuestion()` after routing; typewriter prepends `[category: politics · subcategory: elections]` and primary-traits line. `SAMPLE_PREDICTIONS` expanded from 2 entries to **18** (one baseline + one scenario per category + balanced pair). `runScenario()` reads `SAMPLE_PREDICTIONS[STATE.activeCategory + '_scenario']` so injecting a scenario after a politics question shows political deltas, not crypto deltas. Hardcoded `654 tests` boot KPI replaced with a JS `TEST_COUNT` constant + `<span id="boot-tests">` — no more stale numbers. Code comment in `animateNetworkPrediction()` flags category-aware node coloring as Sprint 12 backlog.
  6. **WP6 Tests.** 24 new tests in `realm/output/tests/test_category_router.py` (schema validation, all 8 categories' keyword routing, balanced fallback, subcategory detection, case-insensitivity, word-boundary guard, plural-form heuristic, LLM fallback paths via hermetic `_ScriptedBackend`). 9 in `realm/output/tests/test_predictor_weighted.py` (primary dominance, suppressed inertness, cross-category divergence on the same population, end-to-end `predict(route_category=True)` smoke). 3 new + 1 inverted in `realm/personality/adapters/tests/test_demographic.py` (`test_political_spectrum_varies_by_country`, `test_political_spectrum_within_bounds`, `test_political_spectrum_deterministic` — the legacy `test_political_spectrum_stays_neutral` is gone). **654 → 688 tests, full suite green in 24.78 s.**
  7. **WP7 Documentation.** This status block, `REALM_CLAUDE.md` bumped to v0.11.0, milestone §19 added with the WP-by-WP breakdown and Sprint 11 open items.

- ✅ **Sprint 10 (2026-04-24)** — Three work packages shipped.
  1. **WP1 aspect-calculator optimisation.** Sprint 9 cProfile isolated `find_transit_aspects` as 63% of total runtime (1421s of 2252s on 10K×30). Root cause was per-pair `PlanetPosition` re-allocation inside the `O(N_agents × bodies²)` inner loop (two fresh dataclass instances per pair, only to bypass `find_aspect`'s same-name rejection) plus repeated `ASPECT_ANGLES.items()` iteration and `orbs.get(...)` lookups (364M dict.get calls/run). Fix: a pre-compiled `_ASPECT_ITEMS` tuple, an enabled-orb tuple hoisted out of the per-pair loop, and a new `_is_applying_transit_natal` helper that inlines the `natal_speed=0` case without allocation. Output is bit-exact with the pre-optimisation path — all 22 aspect_calculator tests pass unchanged. **10K × 30 measured (seed=42): 2251.85s → 1172.92s (1.92× faster), per-tick 75.06s → 39.10s, total runtime 38.4 min → 20.4 min (−47%), `find_transit_aspects` cumulative 1421s (63%) → 288s (24%) — 4.9× faster in absolute terms. `dict.get` 364M → 62M. Drift summary and all activity counts byte-identical to Sprint 9.**
  2. **WP2 Functional dashboard rebuild.** `outputs/realm_dashboard.html` rewritten from scratch (47 KB Neural Observatory → 96 KB Simulation Observatory). Every panel answers one question: (1) What is REALM? — tech stack + KPIs. (2) How does the engine work? — Adapter pipeline SVG flowchart + sample-agent 23-trait radar fed from `celebrity_astro_profiles.json`. (3) Scientific basis? — BF 8/8 + Astro 4/4 scoreboard + per-trait DA ranked bars. (4) **What does the simulation produce?** — 4 KPI cards (posts, engagements, drift agents, events/agent), per-trait histogram comparing tick 0 vs tick 30 (dropdown), per-trait drift bar chart, interactive world choropleth with trait dropdown (D3 + world-atlas topojson from jsdelivr), action-mix donut, and a country cluster network (30-country force graph, edges = cosine similarity on 23 trait means). (5) Performance? — runtime / memory / aspect-calc share KPIs + sprint timeline. All data embedded inline via `scripts/build_dashboard.py`. Single file, no build step.
  3. **WP3 Decision→Event bridge expansion.** `config/drift_events.json` (schema v1) defines 12 event types and 14 ordered firing rules. Added 6 new event types on top of the Sprint 9 six: **leadership_act** (social_dominance↑, authority_compliance↓), **group_conformity** (herd_susceptibility↑, contrarian↓, individualism↓), **group_dissent** (contrarian↑, individualism↑), **financial_loss** (loss_aversion↑, financial_optimism↓), **financial_gain** (financial_optimism↑, risk_appetite↑), **cultural_experience** (spirituality↑, openness↑). Rules use decision predicates (action, topic, sentiment, virality, engagement_kind) + trait thresholds (gte/lt). `DriftEventBridge` class in `realm/simulation/drift.py` loads config and exposes `event_for(decision, traits) → (event_type, intensity) | None`. `SimulationEngine` accepts an optional `drift_bridge` field (additive — legacy `event_from_decision` path preserved when bridge is unset; all 22 Sprint 9 drift tests pass untouched). 34 new tests in `test_drift_bridge.py` covering per-event trait directions, rule matching, first-match-wins preemption, fallback chain, engine integration, and cumulative-ratio cap. Risk / knowledge / stress events now fire in the bridge config — full-scale 10K re-run with the bridge attached is Sprint 11 scope.

**Sprint 10 performance summary (10K × 30, seed=42):**

| Metric                                        | Sprint 9      | Sprint 10      | Δ                |
|-----------------------------------------------|--------------:|---------------:|------------------|
| Total runtime                                 | 38.4 min      | **20.4 min**   | **−47%**         |
| Simulation seconds                            | 2251.85       | 1172.92        | 1.92× faster     |
| Per-tick mean                                 | 75.06 s       | 39.10 s        | 1.92×            |
| Per-tick min                                  | 59.56 s       | 20.68 s        | 2.88×            |
| `find_transit_aspects` cumulative             | 1421 s (63%)  | **288 s (24%)**| 4.9× faster      |
| `dict.get` 30-tick sum                        | 364 M         | 62 M           | 5.8× fewer       |
| Peak memory                                   | 202.8 MB      | 202.8 MB       | identical        |
| Drift summary / activity totals               | baseline      | byte-identical | **bit-exact**    |
| Dashboard file size                           | 47 KB         | 97 KB          |                  |
| Drift event type count                        | 6             | 12             |                  |
| Bridge firing rules                           | hardcoded 4   | 14 (JSON)      |                  |
| Test count                                    | 620           | **654**        |                  |

**Sprint 9 metric summary (22-figure cohort):**

| Metric                              | S7     | S8     | S9     |
|-------------------------------------|-------:|-------:|-------:|
| Directional Accuracy (overall)      | 0.682  | 0.722  | 0.718  |
| Pearson r (overall)                 | 0.268  | 0.322  | 0.309  |
| Extreme-Trait Detection             | 0.766  | 0.802  | 0.799  |
| Confidence-Weighted DA              | 0.754  | 0.789  | 0.779  |
| empathy r                           | -0.302 | -0.302 | +0.023 |
| empathy σ                           | 0.02   | 0.02   | 0.092  |
| social_dominance r                  | -0.335 | -0.335 | -0.179 |
| analytical_depth r                  | -0.324 | -0.324 | -0.175 |


**Architectural evolutions since the original 25 decisions:**
- **Ephemeris backend**: Kerykeion active (Swiss Ephemeris); Skyfield remains as the MSVC-free fallback.
- **LLM backends**: Moonshot primary, OpenAI fallback (Loth's credential set; no Claude yet). OpenAI-compatible SDK reaches both via `base_url` swap. `LLMRouter` wraps in `FallbackBackend` for runtime resilience. Reasoning-model quirks (`temperature=1`-only, `max_completion_tokens` rename) handled by proactive regex + reactive 400-retry loop.
- **News topic → agent posting coupling** (added during butterfly demo): `decide._topic_for()` now counts news posts in the feed and boosts matching topic weight scaled by agent's `herd_susceptibility - contrarian_tendency`. This was the missing link between injected news and observable agent behaviour — without it news only nudged mood traits.
- **Observer window**: `observe_topic_share(topic, window=None)` defaults to all-ticks observation; was previously last-5 which missed the butterfly effect because news expired from NewsChannel (memory_ticks=5) before the measurement window began.
- **Dampening data-driven**: `RuleBasedEmbedder.dampening` now reads from `config/astrology.yaml:rule_based_embedder.dampening` (default 0.40, up from 0.12). Chosen via 2D `(dampening × weight_floor)` sweep; floor found inert and omitted.
- **Agent.natal_chart is optional**: `NatalChart | None` when non-astrological input adapter produced the traits. Null guards added in `simulation/engine.py` (skip TransitModulator) and `output/dashboard_service.py` (emit null payload).
- **political_spectrum scope boundary**: explicitly excluded from astrological mapping and Big-Five derivation via `_excluded_by_design` blocks in `data/astro/*.json` and `data/personality/big_five_derivation.json`. REALM models temperament, not ideological preference.

**Known limitations (see memory `feedback_realm_honest_concerns.md` + `project_realm_validity_study_prep.md` for the full list):**
- ~~Astrological mapping has no validation benchmark yet.~~ **Resolved Sprint 7:** N=20 directional-accuracy benchmark. **Sprint 8 upgraded to DA 0.722 / Pearson 0.322 / Extreme 0.802 / CW-DA 0.789.** See `outputs/astro_validity_study.md`.
- **AstrologicalAdapter is direction-rich, magnitude-poor on clustered traits.** Several traits (communication_assertiveness, persuasion_skill, social_dominance) still show negative Pearson despite DA near 1.00. Sprint 8 confirmed **calibration cannot fix this** for celebrity validation — the raw adapter lacks within-cluster individual differentiation that variance expansion could amplify. Mapping-table enrichment (more differentiating planetary contributors) is the path forward, not post-hoc calibration.
- ~~`loss_aversion` mapping systematically wrong (Sprint 7 DA=0.05).~~ **Resolved Sprint 8:** semantic counter-planet contributors (Mars/Jupiter/Uranus) added to `data/astro/planet_trait_map.json`; loss_aversion DA at 1.00.
- **Calibration ≠ validation (Sprint 8 methodological finding).** TraitCalibrator is designed to normalize general-population distributions toward BF-like means/stds. For validation against biographically-skewed reference populations (famous figures), normalization *removes* direction-correct signal. Use `--calibration=none` for celebrity validation, `--calibration=full` for 5K+ agent simulation.
- ~~**Pre-1800 ephemeris coverage missing** in the installed Kerykeion venv.~~ **Resolved Sprint 9:** `seas_12.se1` (1200-1800 CE) installed to `.venv/Lib/site-packages/kerykeion/sweph/`. Napoleon and Leonardo restored in the validation cohort (N=22). Pre-1 CE (BC dates) still blocked by Python `datetime.MINYEAR=1`; Cleopatra remains out of scope.
- **Per-trait Pearson r on celebrity cohort is ceiling-limited**, not a mapping bug. Traits with DA≈1.00 but negative per-trait r (persuasion_skill, communication_assertiveness, contrarian_tendency on S8 → S9) reflect selection-biased cohort composition: famous figures genuinely cluster high on those traits, so within-cohort differentiation cannot be recovered from mapping alone. Sprint 9 WP1 iteration confirmed counter-signals for these traits pulled celebrity means *away* from biographically-high targets. Fix belongs in population-scale calibration or a larger stratified cohort, not in the planet_trait_map.
- Big Five intercorrelations are near zero in REALM (|r|<0.1) vs literature ~0.20. Mapping treats traits as roughly independent; must be declared honestly, not hidden.
- 3 mapped traits (empathy, persuasion_skill, social_dominance) carry systematic positive bias (mean 0.85+ in raw pipeline) — calibration corrects but mapping rebalance is a future option.
- DemographicAdapter produces NARROWER variance than astrology (country→trait lookup), not wider as originally assumed. Sprint 5's `BlendedAdapter` addresses the combined-signal case but standalone demographic mode remains a weak parametric source.
- ~~BigFiveAdapter has 5 domain traits with no literature-derived coefficients~~ **Partially resolved Sprint 6:** facet-level coefficients drafted and injected into `data/personality/big_five_derivation.json`; 13/13 WARN→PASS under facet mode (`use_facets=true`). 5 fallback traits still default to 0.5 in OCEAN-only mode.
- #8a criterion vs Costa-McCrae 1992 clinical norm still fails (max Δmean=0.169) — this is a known online self-report drift, not a pipeline bug. Left failing intentionally as a sample-drift indicator.
- Butterfly coefficients (herd_factor) are tuning knobs, not empirically calibrated.
- Scalability ceiling: ~500 agents × 10 ticks per minute. 10K+ agents need architectural work.
- Experience drift (decision #6, ±10%) is documented but not implemented.
- Checkpoint uses pickle — fragile across Python/dataclass version changes.
- ~~Dashboard is functional but Loth flagged it as "demode" on 2026-04-23; redesign backlog lives in memory.~~ **Resolved Sprint 10 WP2:** rebuilt as a question-driven Simulation Observatory with live 10K-run data, world choropleth, histograms, and drift bars.
- **Aspect-calculator bottleneck**: ~~94% of 10K tick runtime~~ → **Sprint 10 WP1** brought this to ~38% via allocation-free pair evaluation. Further wins available via vectorization (numpy or Cython) if a 10K × 50 budget ever tightens.
- **Decision→Event bridge now covers 12 event types via `config/drift_events.json`** (Sprint 10 WP3). The 10K-run trait histograms in `outputs/sim_10k_run1/` are from the Sprint 9 bridge (6 event types, social-only); ~~a Sprint 11 full-scale re-run with the new bridge will show financial, knowledge, leadership drift signals~~ — Sprint 11 reprioritized toward prediction-category routing and the v2 dashboard ABOUT panel; the bridge × 10K re-run is now Sprint 12 backlog.
- ~~`political_spectrum` is hard-coded 0.5 across all 66 countries, silently disabling politics-domain prediction differentiation.~~ **Resolved Sprint 11 WP4 (DemographicAdapter) + Sprint 12 WP4 (production AgentFactory).** Hofstede pdi+idv proxy now produces a 0.41 spread at the country level (DK 0.328 → MY 0.735, 57 distinct values) and a population-level σ≈0.10 mean≈0.60 through the live API pipeline. This is a country-level *dispersion proxy*, not a left/right label and not a polarization measurement; vendoring V-Dem / Pew remains a future improvement.
- **Per-agent supporting/opposing/neutral aggregation does not exist yet.** `PredictionEngine` returns a yes/no probability over branches (`probability = n_yes / n_branches`). The dashboard's `agents_supporting / agents_opposing / agents_neutral` fields in `SAMPLE_PREDICTIONS` are mocked. Wiring a true per-agent decision aggregator is Sprint 12 work.
- ~~**v2 dashboard ASK panel still uses mocked `SAMPLE_PREDICTIONS`.**~~ **Resolved Sprint 12:** boot-screen `Prediction Mode` dropdown lets the user pick `Live (FastAPI backend)` and the ASK + SCENARIO panels then call `realm/api/predict.py` for real engine results. Live errors fall back to mock with a typewriter breadcrumb so the UI never freezes.

**How to resume:**
```bash
cd C:\Users\loth\desktop\realm
.venv\Scripts\activate
python scripts/smoke_external.py                            # Sprint 20: ALWAYS run first after a dormant period
python -m pytest -q                                         # expect 1022 passing (Sprint 24)
realm_start.bat                                             # v2 dashboard + FastAPI :8420 (production path)
python scripts/serve_dashboard.py 500                       # LEGACY v1 dashboard — pre-Sprint-13 algorithm, retire/merge pending
python scripts/demo_butterfly.py                            # offline butterfly proof
python scripts/diag_variance.py 2000                        # variance sweep diagnostic
python scripts/validate_trait_distribution.py 10000         # calibration report (astrological)
python scripts/validate_trait_distribution.py 5000 --adapter=demographic   # demographic variance sanity
python scripts/check_jobs_directional.py                    # Jobs chart invariance check (N=1)
# Big Five validity studies (Sprints 3-6):
python scripts/validate_bf_study.py 10000 --seed=42         # synthetic N=10K, 7/7 PASS report
python scripts/validate_bf_study_real.py                    # real automoto/big-five-data, 6/8 PASS
python scripts/validate_bf_johnson.py                       # Johnson IPIP-NEO-120 N=612K, 8/8 PASS facet mode
python scripts/validate_facet_derivation.py                 # Sprint 6 facet audit, 13/13 PASS
# Astrological validity study (Sprints 7-8):
python scripts/generate_celebrity_astro_profiles.py                            # compute 20 charts → outputs/celebrity_astro_profiles.json (default calibration=none — best for validation)
python scripts/generate_celebrity_astro_profiles.py --calibration=variance     # opt-in variance expansion mode (simulation use)
python scripts/generate_celebrity_astro_profiles.py --calibration=full         # opt-in full TraitCalibrator (simulation use)
python scripts/validate_astro_study.py                                         # DA/correlation/extreme report → outputs/astro_validity_study.md
# Sprint 9 drift + full simulation:
python -m pytest realm/simulation/tests/test_drift.py -v    # 22 Sprint 9 drift tests
python scripts/run_simulation.py --agents=10000 --ticks=30 --output=outputs/sim_10k_run1  # full sim
# Sprint 9 cohort restore (one-time):
python scripts/add_sprint9_cohort.py                        # Napoleon + Leonardo
# Sprint 10 event-bridge tests + dashboard:
python -m pytest realm/simulation/tests/test_drift_bridge.py -v               # 34 bridge tests
python scripts/build_dashboard.py                                              # rebuild outputs/realm_dashboard.html from sim/validation JSONs
start outputs/realm_dashboard.html                                             # open in browser (Windows); `open` on macOS, `xdg-open` on Linux
# Sprint 10 benchmark re-run (post-WP1 speedup):
python scripts/run_simulation.py --agents=10000 --ticks=30 --output=outputs/sim_10k_sprint10
```

---

## 1. PROJECT VISION

REALM, dünya ölçeğinde çoklu ajan simülasyonu ile tahmin üreten bir sürü zekası (swarm intelligence) motorudur. MiroFish'ten ilham alır ancak sıfırdan yazılmıştır. Temel farkı: **astrolojik natal harita ve transit hesaplamalarını kişilik embedding framework'ü olarak kullanması**, gerçekçi bir dünya nüfusu simüle etmesi ve kelebek etkisini modellemesidir.

### 1.1 Core Thesis
Her şey birbiriyle bağlıdır. Dünyanın bir yerindeki bir olay, başka bir yerde beklenmedik sonuçlar tetikler. REALM bunu, binlerce farklı kişiliğe sahip ajanın etkileşiminden ortaya çıkan kolektif davranışı gözlemleyerek modeller.

### 1.2 What REALM Is NOT
- Geleneksel bir istatistiksel tahmin modeli değildir
- Bir astroloji uygulaması değildir — astrolojiyi iki katmanda kullanır:
  - **Bireysel katman:** Natal harita → kişilik parametrelendirme aracı
  - **Kolektif katman:** Dönemin astrolojik iklimi (era transitleri, retro dönemleri, büyük geçişler) → simülasyon parametresi. Örn: Pluto Kova Burcu'na geçişi toplumsal dönüşüm eğilimini, Mars-Uranüs karesi kolektif volatiliteyi, Merkür retrosu iletişim kazalarını modelleyerek tahmin girdisi olarak kullanılır
- MiroFish fork'u değildir — bağımsız, özgün bir kod tabanıdır

---

## 2. CONVENTIONS

### 2.1 Code Language
- **Tüm kod İngilizce yazılır:** değişken adları, fonksiyon adları, class isimleri, dosya adları
- **Yorumlar Türkçe olabilir:** açıklayıcı comment'ler, docstring'lerin Türkçe versiyonları
- **Commit mesajları İngilizce**

```python
# Örnek:
class PersonalityEmbedder:
    """Natal harita verilerini davranış vektörüne dönüştürür."""

    def compute_risk_appetite(self, natal_chart: NatalChart) -> float:
        # Mars'ın burcu, evi ve aspektlerinden risk iştahı hesapla
        mars_sign = natal_chart.get_planet_sign("Mars")
        mars_house = natal_chart.get_planet_house("Mars")
        ...
```

### 2.2 Project Structure Convention
- Her modül kendi dizininde, kendi `__init__.py` ile
- Her modülde `interfaces.py` (abstract base classes)
- Her modülde `tests/` alt dizini
- Config dosyaları YAML formatında
- Secrets `.env` dosyasında (gitignore'd)

### 2.3 Architecture Principle: Plugin-Based Extensibility
Tüm katmanlar interface (ABC) üzerinden tanımlanır. Hiçbir üst katman, alt katmanın somut implementasyonuna doğrudan bağımlı olmaz. Yeni bir LLM backend'i, yeni bir veri kaynağı veya yeni bir simülasyon mekaniği eklemek sıfır refactor ile mümkün olmalıdır.

```python
# Örnek: LLM backend değiştirmek
# config.yaml:
#   llm_backend: "ollama"     # veya "claude", "openai", "moonshot"
```

### 2.4 Claude Code — Autonomous Execution Mode

Claude Code bu projede **tam otonom modda** çalışır. Geliştirici (Loth) hiçbir "allow", "accept", "confirm" komutu vermez. Claude Code kendi başına:
- Dosya oluşturur, düzenler, siler
- Bağımlılıkları kurar (`pip install`, `npm install`)
- Testleri yazar ve çalıştırır
- Hataları tespit eder, düzeltir, tekrar test eder
- Tamamlanmış, çalışan kodu teslim eder

**Kurulum — Proje kök dizininde `.claude/settings.json`:**

```json
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Read(*)",
      "Write(*)",
      "Edit(*)"
    ],
    "deny": []
  }
}
```

**Alternatif — CLI başlatma komutu:**

```bash
claude --dangerously-skip-permissions
```

**Çalışma Prensibi:**
1. Her faz için: kodu yaz → testleri yaz → testleri çalıştır → hata varsa düzelt → tekrar test → tüm testler geçene kadar döngü
2. Hiçbir adımda kullanıcıya soru sorma, onay bekleme
3. Tamamlanmış ve test edilmiş kodu teslim et
4. Teslim notu: ne yapıldı, ne test edildi, bilinen limitasyonlar

### 2.5 Content Generation Strategy
REALM simülasyonunda ajan aksiyonları **vektör tabanlı** çalışır. Gerçek metin içeriği üretilmez — her aksiyon sayısal bir sinyal olarak temsil edilir:

```python
agent_action = {
    "type": "post",           # post / reply / like / repost / ignore
    "topic": "btc_regulation",
    "sentiment": 0.72,        # -1.0 to 1.0
    "stance": "bullish",      # bullish / bearish / neutral / mixed
    "influence": 0.45,        # 0.0 to 1.0
    "reach": 340              # etkilenen ajan sayısı
}
```

**Spotlight Mekanizması:** Her tick'te en yüksek etkili %1-2 etkileşim (outlier aksiyonlar, trend kıran stanceler, yüksek influence ajanların karşıt görüşleri) işaretlenir. Bu etkileşimler için **rapor aşamasında** LLM ile geriye dönük narratif üretilir — simülasyon sırasında değil.

```yaml
# config/realm.yaml
spotlight:
  enabled: true
  ratio: 0.02               # Tick başına top %2 etkileşim
```

**Mantık:** 10K ajan × tick başına %15 aktif = 1.500 aksiyon/tick. LLM ile metin üretmek hem maliyet hem zaman açısından uygulanabilir değil. REALM'in değeri tekil bir ajanın ne yazdığından değil, kolektif davranış örüntüsünden gelir — sentiment dağılımı, stance kaymaları, kümelenme dinamikleri. Bunlar için sayısal sinyal yeterlidir.

---

## 3. ARCHITECTURE OVERVIEW

```
┌──────────────────────────────────────────────────────────────────┐
│                        REALM Engine                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │  AstroCore   │  │ PersonalityEngine │  │ DemographicEngine │  │
│  │  (Katman 1)  │──│    (Katman 2)     │──│    (Katman 3)     │  │
│  │  Kerykeion   │  │  Harita→Vektör    │  │  Dünya Nüfusu     │  │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬───────────┘  │
│         │                   │                      │              │
│  ┌──────▼───────────────────▼──────────────────────▼───────────┐  │
│  │              AgentFactory (Katman 4)                         │  │
│  │  Demographic + Natal + Culture + Profession → Agent JSON    │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │              SimulationEngine (Katman 5)                     │  │
│  │  Ajan etkileşim loop'u + Transit modülasyonu                │  │
│  │  SeedIngestion (API feed + manuel) → Simülasyon tetikler    │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │              OutputLayer (Katman 6)                          │  │
│  │  Dashboard + Q&A Prediction + Report + Visualization        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────────────────┐   │  │
│  │  │ Dashboard │ │  Report  │ │  Neural Synapse Graph     │   │  │
│  │  │ Mood/Sent │ │ PDF/MD   │ │  D3.js + NetworkX         │   │  │
│  │  └──────────┘ └──────────┘ └───────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              SignalInterface (Katman 7 — Future)             │  │
│  │  POLYLIQ / ARGUS entegrasyon sinyalleri                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Infrastructure                                  │  │
│  │  SQLite + JSON │ LLM Backend (pluggable) │ Config (YAML)    │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. DIRECTORY STRUCTURE

```
realm/
├── CLAUDE.md                          # Bu dosya
├── README.md                          # Proje açıklaması
├── pyproject.toml                     # Python proje konfigürasyonu
├── .env.example                       # Ortam değişkenleri şablonu
├── .gitignore
│
├── config/
│   ├── realm.yaml                     # Ana konfigürasyon
│   ├── demographics.yaml              # Nüfus dağılım parametreleri
│   ├── astrology.yaml                 # Astrolojik mapping kuralları
│   ├── cultural_dimensions.yaml       # Hofstede + bölgesel değerler
│   ├── expert_distribution.yaml       # Uzman dağılım modları (3 mod)
│   └── api_sources.yaml              # Seed data API kaynakları
│
├── realm/                             # Ana paket
│   ├── __init__.py
│   │
│   ├── core/                          # Paylaşılan temel bileşenler
│   │   ├── __init__.py
│   │   ├── interfaces.py             # Tüm abstract base class'lar
│   │   ├── config.py                 # YAML config loader
│   │   ├── database.py               # SQLite manager
│   │   ├── exceptions.py             # Özel exception sınıfları
│   │   ├── types.py                  # Type tanımları, dataclass'lar
│   │   ├── logging.py               # Loglama konfigürasyonu
│   │   └── monitoring.py            # Simülasyon sağlığı ve metrikler
│   │
│   ├── astro/                         # Katman 1: AstroCore
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IAstroEngine, ITransitCalculator
│   │   ├── natal_engine.py           # Kerykeion wrapper — natal harita
│   │   ├── transit_engine.py         # Transit hesaplama motoru
│   │   ├── aspect_calculator.py      # Aspekt hesaplama ve orb yönetimi
│   │   ├── dignity_analyzer.py       # Gezegen onur/düşüş/yükselme
│   │   ├── house_system.py           # Ev sistemi hesaplamaları
│   │   └── tests/
│   │       ├── test_natal.py
│   │       ├── test_transit.py
│   │       └── test_aspects.py
│   │
│   ├── personality/                   # Katman 2: PersonalityEngine
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IPersonalityEmbedder
│   │   ├── embedder.py               # Ana orchestrator
│   │   ├── rule_based.py             # Kural tabanlı mapping (Mod A)
│   │   ├── llm_based.py              # LLM destekli mapping (Mod B)
│   │   ├── hybrid.py                 # Hibrit yaklaşım (Mod C)
│   │   ├── trait_vector.py           # TraitVector dataclass & ops
│   │   ├── planet_traits.py          # Gezegen → trait mapping tabloları
│   │   ├── aspect_modifiers.py       # Aspekt etkisi katsayıları
│   │   └── tests/
│   │       ├── test_embedder.py
│   │       ├── test_traits.py
│   │       └── test_consistency.py
│   │
│   ├── demographics/                  # Katman 3: DemographicEngine
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IDemographicGenerator
│   │   ├── world_generator.py        # Dünya nüfusu üretici
│   │   ├── country_data.py           # Ülke nüfus/yaş/cinsiyet verileri
│   │   ├── profession_generator.py   # Meslek dağılımı
│   │   ├── name_generator.py         # Ülkeye uygun isim üretici
│   │   ├── socioeconomic.py          # Gelir/eğitim/marjinal profiller
│   │   └── tests/
│   │       └── test_demographics.py
│   │
│   ├── culture/                       # Katman 4: CulturalModifier
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ICulturalModifier
│   │   ├── hofstede.py               # Hofstede 6 boyut implementasyonu
│   │   ├── regional_values.py        # Bölgesel değer sistemleri
│   │   ├── religion_worldview.py     # Dini/seküler dünya görüşleri
│   │   └── tests/
│   │       └── test_culture.py
│   │
│   ├── agents/                        # AgentFactory + Agent Model
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IAgent, IAgentFactory
│   │   ├── factory.py                # Ajan üretim fabrikası
│   │   ├── agent.py                  # Agent sınıfı (state + behavior)
│   │   ├── memory.py                 # Ajan hafıza sistemi
│   │   ├── decision.py               # Karar mekanizması (kural + LLM)
│   │   └── tests/
│   │       └── test_agents.py
│   │
│   ├── simulation/                    # Katman 5: SimulationEngine
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ISimulationEngine, IPlatform
│   │   ├── engine.py                 # Ana simülasyon loop
│   │   ├── clock.py                  # Simülasyon saati, tick yönetimi
│   │   ├── platforms/                # Etkileşim platformları
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Platform ABC
│   │   │   ├── social_media.py       # Twitter/Reddit benzeri (Faz 1)
│   │   │   ├── news_channel.py       # Haber kanalı (Faz 2+)
│   │   │   ├── market.py             # Piyasa etkileşimi (Faz 2+)
│   │   │   └── parliament.py         # Meclis/forum (Faz 2+)
│   │   ├── transit_modulator.py      # Zaman bazlı davranış shift
│   │   ├── interaction_resolver.py   # Etkileşim çözümleyici
│   │   ├── event_bus.py              # Olay yayılımı (kelebek etkisi)
│   │   ├── network.py               # Ağ topolojisi (Small-world + Scale-free)
│   │   ├── checkpoint.py            # Checkpoint/fork/resume mekanizması
│   │   └── tests/
│   │       ├── test_engine.py
│   │       ├── test_modulator.py
│   │       └── test_network.py
│   │
│   ├── ingestion/                     # SeedIngestion
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IDataSource, ISeedProcessor
│   │   ├── manager.py                # Feed yönetim orchestrator
│   │   ├── sources/                  # Veri kaynağı adaptörleri
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # DataSource ABC
│   │   │   ├── rss_feed.py           # RSS/Atom feed (not: genişleme)
│   │   │   ├── news_api.py           # Haber API'leri
│   │   │   ├── crypto_api.py         # Kripto piyasa verisi
│   │   │   ├── social_trends.py      # Sosyal medya trend verisi
│   │   │   ├── economic_data.py      # Ekonomik göstergeler (FRED vb.)
│   │   │   └── manual_upload.py      # Manuel dosya yükleme
│   │   ├── entity_extractor.py       # Varlık ve ilişki çıkarma
│   │   ├── knowledge_graph.py        # Bilgi grafiği oluşturma
│   │   └── tests/
│   │       └── test_ingestion.py
│   │
│   ├── output/                        # Katman 6: OutputLayer
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IOutputRenderer, IDashboard
│   │   ├── dashboard.py              # Mood/sentiment dashboard
│   │   ├── predictor.py              # Q&A prediction + confidence
│   │   ├── report_generator.py       # Yapılandırılmış rapor (MD/PDF)
│   │   └── tests/
│   │       └── test_output.py
│   │
│   ├── visualization/                 # Nöral Synapse Görselleştirme
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IVisualizer
│   │   ├── graph_builder.py          # NetworkX graf oluşturma
│   │   ├── neural_renderer.py        # D3.js nöral synapse render
│   │   ├── templates/                # HTML/JS şablonları
│   │   │   ├── synapse_view.html     # Ana görselleştirme sayfası
│   │   │   └── dashboard.html        # Dashboard UI
│   │   ├── static/                   # CSS, JS assets
│   │   │   ├── synapse.js            # D3.js synapse animasyonu
│   │   │   ├── dashboard.js          # Dashboard interaktivite
│   │   │   └── styles.css
│   │   └── tests/
│   │       └── test_visualization.py
│   │
│   ├── llm/                           # LLM Backend (Pluggable)
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ILLMBackend
│   │   ├── ollama_backend.py         # Ollama (Qwen, Llama)
│   │   ├── claude_backend.py         # Anthropic Claude API
│   │   ├── openai_backend.py         # OpenAI API
│   │   ├── moonshot_backend.py       # Moonshot/Kimi API
│   │   ├── router.py                 # Hangi task → hangi backend
│   │   └── tests/
│   │       └── test_backends.py
│   │
│   ├── signal/                        # Katman 7: SignalInterface (Future)
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ISignalEmitter
│   │   ├── polyliq_bridge.py         # POLYLIQ sinyal çıktısı (stub)
│   │   └── argus_bridge.py           # ARGUS sinyal çıktısı (stub)
│   │
│   └── utils/                         # Yardımcı araçlar
│       ├── __init__.py
│       ├── time_utils.py             # Zaman dönüşümleri, Julian Day
│       ├── geo_utils.py              # Koordinat, timezone yönetimi
│       ├── cache.py                  # Genel cache mekanizması
│       └── validators.py             # Girdi doğrulama
│
├── prompts/                           # LLM prompt şablonları (versiyonlu YAML)
│   ├── personality/
│   │   ├── system.yaml                # System prompt (kişilik analisti rolü)
│   │   └── user_template.yaml         # Natal harita → trait prompt şablonu
│   ├── report/
│   │   ├── summary.yaml               # Simülasyon özet raporu
│   │   ├── prediction.yaml            # Tahmin açıklama şablonu
│   │   └── prediction_tr.yaml         # Türkçe rapor şablonu
│   ├── spotlight/
│   │   └── narrative.yaml             # Spotlight ajan narratif üretimi
│   └── question_parser/
│       └── parse_question.yaml        # Q&A soru parse prompt'u
│
├── data/                              # Statik veri dosyaları
│   ├── countries.json                 # Ülke listesi + nüfus + koordinat
│   ├── cities.json                    # Ülke bazlı şehir listesi (top 20/ülke)
│   ├── birth_hour_weights.json        # Saat bazlı doğum dağılımı ağırlıkları
│   ├── names/                         # Ülkeye göre isim havuzları (Faker fallback)
│   │   ├── tr.json                    # Türk isimleri (Faker locale varsa gereksiz)
│   │   ├── us.json                    # Amerikan isimleri
│   │   ├── cn.json                    # Çin isimleri
│   │   └── ...                        # Faker kapsamadığı ülkeler için
│   ├── professions.json               # Meslek kategorileri + dağılımları
│   ├── hofstede_scores.json           # Ülke bazlı Hofstede skorları
│   └── astro/
│       ├── planet_trait_map.json      # Gezegen → trait mapping tablosu
│       ├── sign_modifiers.json        # Burç modifikasyon katsayıları
│       ├── house_meanings.json        # Ev anlamları ve etki alanları
│       └── aspect_weights.json        # Aspekt güç katsayıları
│
├── db/                                # SQLite veritabanı dosyaları
│   ├── realm.db                       # Ana veritabanı
│   └── migrations/                    # Şema migration'ları
│       └── 001_initial.sql
│
├── scripts/                           # Yardımcı scriptler
│   ├── generate_population.py         # Nüfus üretim scripti
│   ├── run_simulation.py              # Simülasyon çalıştırma
│   ├── export_report.py               # Rapor dışa aktarma
│   └── benchmark.py                   # Performans benchmark
│
├── notebooks/                         # Jupyter notebook'lar (analiz)
│   └── exploration.ipynb
│
└── tests/                             # Entegrasyon testleri
    ├── test_integration.py
    └── test_end_to_end.py
```

---

## 5. MODULE SPECIFICATIONS

### 5.1 AstroCore (realm/astro/)

**Amaç:** Natal harita ve transit hesaplamalarının tek doğruluk kaynağı.

**Bağımlılık:** `kerykeion` (Swiss Ephemeris tabanlı)

**Temel Sınıflar:**

```python
# interfaces.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class PlanetPosition:
    """Bir gezegenin ekliptik pozisyonu."""
    name: str               # "Sun", "Moon", "Mars", ...
    longitude: float         # 0-360 derece
    latitude: float
    sign: str                # "Aries", "Taurus", ...
    sign_degree: float       # Burç içindeki derece (0-30)
    house: int               # 1-12
    is_retrograde: bool
    speed: float             # Derece/gün

@dataclass
class Aspect:
    """İki gezegen arası aspekt."""
    planet1: str
    planet2: str
    aspect_type: str         # "conjunction", "opposition", "trine", "square", "sextile"
    angle: float             # Gerçek açı
    orb: float               # Tam aspektten sapma
    is_applying: bool        # Yaklaşan mı, ayrılan mı

@dataclass
class NatalChart:
    """Tam natal harita verisi."""
    birth_datetime: datetime
    latitude: float
    longitude: float
    timezone: str
    planets: List[PlanetPosition]
    houses: List[float]      # 12 ev cusp derecesi
    aspects: List[Aspect]
    ascendant: float
    midheaven: float
    element_balance: Dict[str, float]   # fire, earth, air, water
    modality_balance: Dict[str, float]  # cardinal, fixed, mutable

@dataclass
class TransitSnapshot:
    """Belirli bir andaki transit durumu."""
    timestamp: datetime
    transiting_planets: List[PlanetPosition]
    active_transits: List[Aspect]        # Transit gezegen → natal gezegen
    moon_phase: str                       # "new", "waxing", "full", "waning"
    retrograde_planets: List[str]

class IAstroEngine(ABC):
    """Astroloji hesaplama motoru arayüzü."""

    @abstractmethod
    def calculate_natal_chart(
        self, birth_dt: datetime, lat: float, lon: float, tz: str
    ) -> NatalChart:
        ...

    @abstractmethod
    def calculate_transits(
        self, natal: NatalChart, target_dt: datetime
    ) -> TransitSnapshot:
        ...

    @abstractmethod
    def calculate_transit_range(
        self, natal: NatalChart, start_dt: datetime, end_dt: datetime,
        interval_hours: int = 24
    ) -> List[TransitSnapshot]:
        ...
```

**Kerykeion Entegrasyon Notları:**
- Kerykeion `AstrologicalSubject` nesnesi oluşturulur, sonuçlar bizim `NatalChart` dataclass'ına dönüştürülür
- Ev sistemi: Placidus (default, konfigüre edilebilir)
- Orb ayarları: konfigürasyondan okunur (astrology.yaml)
- Transit hesabında: simülasyon zamanında geçici bir `AstrologicalSubject` oluşturulur ve natal haritaya karşı aspektler hesaplanır

**Gök Cisimleri Konfigürasyonu:**

Varsayılan olarak 13 gök cismi hesaplanır: klasik 10 gezegen (Sun–Pluto) + North Node + South Node + Chiron. Genişleme config ile kontrol edilir:

```yaml
# config/astrology.yaml
celestial_bodies:
  core: true          # Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto
  nodes: true         # North Node (destiny/purpose), South Node (comfort zone/past)
  chiron: true        # Chiron (wound/healing axis)
  lilith: false       # Black Moon Lilith (Faz 2+)
  asteroids: false    # Ceres, Pallas, Juno, Vesta (Faz 2+)
```

Kerykeion tüm bu cisimleri destekler. Hesaplama maliyeti ihmal edilebilir düzeydedir — asıl maliyet trait mapping tablosunun genişlemesidir (YAML'dan okunduğu için yeni cisim eklemek konfigürasyon işidir).

### 5.2 PersonalityEngine (realm/personality/)

**Amaç:** Natal haritayı sayısal bir davranış vektörüne (TraitVector) dönüştürmek.

**TraitVector Tanımı:**

```python
@dataclass
class TraitVector:
    """Bir ajanın davranış parametreleri. Tüm değerler 0.0-1.0 arasında."""

    # --- Temel Kişilik (Big Five Benzeri) ---
    openness: float              # Yeniliğe açıklık
    conscientiousness: float     # Sorumluluk/düzen
    extraversion: float          # Dışa dönüklük
    agreeableness: float         # Uyumluluk
    neuroticism: float           # Duygusal kararsızlık

    # --- Karar Verme ---
    risk_appetite: float         # Risk iştahı (0=aşırı temkinli, 1=pervasız)
    analytical_depth: float      # Analitik derinlik vs sezgisel
    impulsivity: float           # Dürtüsellik
    patience: float              # Sabır, uzun vadeli düşünme

    # --- Sosyal Dinamik ---
    social_dominance: float      # Liderlik/baskınlık
    herd_susceptibility: float   # Sürü davranışına yatkınlık
    authority_compliance: float  # Otoriteye uyum
    contrarian_tendency: float   # Karşıtlık eğilimi
    empathy: float               # Empati kapasitesi

    # --- Finansal Davranış ---
    financial_optimism: float    # Mali iyimserlik
    loss_aversion: float         # Kayıptan kaçınma
    fomo_susceptibility: float   # FOMO (kaçırma korkusu)

    # --- İletişim ---
    communication_assertiveness: float  # İletişim kararlılığı
    persuasion_skill: float             # İkna yeteneği
    information_sharing: float          # Bilgi paylaşma eğilimi

    # --- Dünya Görüşü ---
    political_spectrum: float    # 0=sol, 0.5=merkez, 1=sağ
    tradition_vs_progress: float # 0=gelenekçi, 1=ilerici
    individualism: float         # 0=kolektivist, 1=bireyci
    spirituality: float          # Spiritüel/mistik eğilim

    def apply_modifier(self, modifiers: Dict[str, float]) -> 'TraitVector':
        """Transit veya kültürel modifikasyon uygula."""
        ...

    def to_dict(self) -> Dict[str, float]:
        ...

    def distance(self, other: 'TraitVector') -> float:
        """İki kişilik arası mesafe (benzerlik ölçümü)."""
        ...
```

**Mapping Yaklaşımı (3 Mod):**

| Mod | Açıklama | Kullanım |
|-----|----------|----------|
| A: Rule-based | Sabit tablolar: Mars Koç'ta → risk=0.85 | Default başlangıç |
| B: LLM-based | Natal harita JSON → LLM → trait vektörü | Yüksek kalite, yavaş |
| C: Hybrid | Kural tabanlı temel + LLM nüans katmanı | Önerilen production modu |

**Konfigürasyon:** `config/astrology.yaml` → `personality_mode: "rule_based" | "llm" | "hybrid"`

**Gezegen → Trait Mapping Özeti (Rule-Based Mod):**

| Gezegen | Birincil Trait'ler | İkincil |
|---------|-------------------|---------|
| Güneş | social_dominance, extraversion | individualism |
| Ay | neuroticism, empathy, herd_susceptibility | emotional reactivity |
| Merkür | analytical_depth, communication_assertiveness | information_sharing |
| Venüs | agreeableness, financial_optimism | empathy |
| Mars | risk_appetite, impulsivity | contrarian_tendency |
| Jüpiter | openness, financial_optimism | optimism |
| Satürn | conscientiousness, patience, authority_compliance | loss_aversion |
| Uranüs | contrarian_tendency, openness | tradition_vs_progress |
| Neptün | spirituality, empathy | herd_susceptibility |
| Pluto | social_dominance, risk_appetite | transformation |
| North Node | tradition_vs_progress, openness | life purpose direction |
| South Node | herd_susceptibility (inverse) | comfort zone patterns |
| Chiron | empathy, neuroticism | wound/healing axis |

Her gezegen etki gücü = f(burç, ev, aspektler, onur/düşüş durumu)

### 5.3 DemographicEngine (realm/demographics/)

**Amaç:** Gerçekçi dünya nüfusu üretmek.

**Veri Kaynakları:**
- UN World Population Prospects (ücretsiz, JSON)
- Dünya Bankası API (meslek/eğitim dağılımları)
- Hofstede Insights (kültürel boyutlar, açık veri)

**Nüfus Üretim Mantığı:**

```
1. Ülke havuzu oluştur (195 ülke, nüfusa orantılı ajan sayısı)
2. Her ülke için:
   a. Yaş dağılımı (piramide göre)
   b. Cinsiyet dağılımı
   c. Doğum tarihi + saati + lokasyonu üret
   d. Meslek ata (ülke ekonomisine göre)
   e. Eğitim seviyesi ata
   f. Sosyoekonomik katman ata
   g. Marjinal profil olasılığı (uyuşturucu bağımlısı, evsiz, suç geçmişi...)
3. İsim üret (ülke + cinsiyet + nesil bazlı)
```

**Ölçek Konfigürasyonu:**

```yaml
# config/demographics.yaml
population:
  total_agents: 10000       # Başlangıç (50000, 100000 olarak artırılabilir)
  distribution: "proportional"  # veya "enriched" veya "equal"
  mode: "static"             # "static" | "semi_dynamic" | "dynamic"
  experience_drift: true     # Deneyim birikimi ile hafif trait kayması
  max_drift_ratio: 0.10      # Base trait'ten max sapma: %10
  include_marginal: true
  marginal_ratio: 0.05      # Toplumun %5'i marjinal profil

birth_time:
  distribution: "realistic"  # "uniform" | "realistic"
  # Gerçekçi dağılım: sabah 08-12 pik, gece 02-05 düşük
  # Sezaryen/indüksiyon etkisi ile gündüz ağırlıklı (%60-65)

geography:
  granularity: "city"         # "city" | "country_center"
  cities_per_country: 20      # Ülke başına max şehir (data/cities.json)
  rural_offset_degrees: 1.0   # Kırsal nüfus: en yakın şehir çevresi ±N derece
  timezone_auto: true         # Koordinattan otomatik timezone (timezonefinder)
```

**Doğum Saati Dağılımı:**

Uniform dağılım yerine gerçek doğum istatistiklerine dayalı ağırlıklı dağılım kullanılır. Bu, Ascendant dağılımını gerçek topluma yaklaştırır:

```python
# Saat bazlı ağırlıklar (gerçek doğum istatistiklerinden)
hour_weights = [
    0.6, 0.5, 0.4, 0.4, 0.5, 0.6,   # 00-05 (gece, düşük)
    0.8, 1.0, 1.3, 1.4, 1.3, 1.2,   # 06-11 (sabah, yüksek — indüksiyon/sezaryen)
    1.1, 1.0, 1.0, 1.1, 1.0, 0.9,   # 12-17 (öğleden sonra)
    0.8, 0.7, 0.7, 0.7, 0.7, 0.6    # 18-23 (akşam, azalan)
]
birth_hour = rng.choice(24, p=normalize(hour_weights))
```

**Coğrafi Granülarite:** Her ülke için top 20 şehir (nüfusa orantılı dağılım, `data/cities.json`). Kalan nüfus → en yakın şehir çevresinde ±1 derece offset (kırsal nüfus şehirlerin etrafında yoğunlaşır). Timezone, `timezonefinder` kütüphanesi ile koordinattan otomatik çıkarılır.

**İsim Üretimi:** `Faker` kütüphanesi (50+ locale). Deterministik seed desteği ile reproducibility korunur. Faker'ın kapsamadığı ülkeler için bölgesel fallback:

```python
LOCALE_MAP = {"TR": "tr_TR", "US": "en_US", "CN": "zh_CN", "JP": "ja_JP", ...}
FALLBACK_MAP = {"AF": "fa_IR", "KZ": "ru_RU", ...}  # Locale yoksa bölgesel yakın
# Hiçbiri yoksa → "en_US" default
```

**Uzman Dağılımı (3 Mod):**

```yaml
# config/expert_distribution.yaml
expert_mode: "dynamic"  # "realistic" | "enriched" | "dynamic"

realistic:
  expert_ratio: 0.05        # %5 uzman
  # Kalan %95 genel halk

enriched:
  expert_ratio: 0.30        # %30 uzman (şişirilmiş)

dynamic:
  base_expert_ratio: 0.08   # Temel oran
  topic_boost_factor: 3.0   # Konuyla ilgili uzmanlar öne çıkar
  # Simülasyon konusu "kripto" ise → finans uzmanları 3x ağırlıklı
```

### 5.4 CulturalModifier (realm/culture/)

**Amaç:** Kültürel değer sistemlerini ajan davranışına entegre etmek.

**Hofstede 6 Boyut:**
1. Power Distance Index (PDI) — Güç mesafesi
2. Individualism vs Collectivism (IDV)
3. Masculinity vs Femininity (MAS)
4. Uncertainty Avoidance Index (UAI) — Belirsizlikten kaçınma
5. Long-Term Orientation (LTO)
6. Indulgence vs Restraint (IVR)

**Uygulama:**

```python
class CulturalModifier:
    def apply(self, trait_vector: TraitVector, country: str) -> TraitVector:
        """Ülke kültürel boyutlarını trait vektörüne uygula."""
        scores = self.get_hofstede_scores(country)

        # Örnek mapping:
        # Yüksek PDI → authority_compliance ↑, contrarian_tendency ↓
        # Yüksek IDV → individualism ↑, herd_susceptibility ↓
        # Yüksek UAI → risk_appetite ↓, conscientiousness ↑
        # Yüksek LTO → patience ↑, impulsivity ↓
        ...
```

### 5.5 SimulationEngine (realm/simulation/)

**Amaç:** Ajan etkileşim döngüsünü yönetmek.

**Tick Mekanizması:**

```
Her tick (default: 1 gün):
  1. Simülasyon saatini ilerlet
  2. TransitModulator: aktif transitleri hesapla, ajan trait'lerini modüle et
  3. SeedIngestion: yeni veri var mı kontrol et, varsa inject et
  4. Her platform için:
     a. Aktif ajanları seç (activity probability'e göre)
     b. Her aktif ajan için:
        - Mevcut konuları değerlendir (kişilik + kültür + transit filtresi)
        - Aksiyon seç: post / reply / like / repost / follow / ignore
        - Aksiyon uygula, sonuçları event_bus'a yayınla
  5. Global metrics güncelle (mood, sentiment, engagement)
  6. State snapshot'ı SQLite'a kaydet
```

**Catch-Up Mekanizması:**

```
Son çalıştırma: 2026-04-15
Şu an: 2026-04-22
→ 7 gün catch-up gerekiyor
→ Accelerated mode: normal simülasyonu 10x hızda çalıştır
→ Her tick'te tam transit hesaplanır (astrolojik doğruluk korunur)
→ Ajan etkileşimleri basitleştirilir (yalnız yüksek olasılıklı aksiyonlar)
→ Catch-up bitince normal hıza dön
```

**Kelebek Etkisi — EventBus:**

```python
class EventBus:
    """Olayların zincirleme yayılımını yönetir."""

    def emit(self, event: SimEvent):
        """
        Bir olay tetiklendiğinde:
        1. Doğrudan etkilenen ajanları belirle (aynı platform/konu)
        2. Dolaylı yayılım: ajan ağı üzerinden propagate et
        3. Cross-platform yayılım: haber → sosyal medya → piyasa
        4. İkincil etki: etkilenen ajanlar kendi aksiyonlarını tetikler
        5. Cross-platform yayılım kuralları:
           - social_media viral post → news_channel (threshold: influence > 0.8, reach > 1000)
           - news_channel breaking → social_media (otomatik, tüm ajanlar görebilir)
           - social_media/news sentiment shift → market sentiment (gecikme: 1-3 tick)
           - market büyük hareket → news_channel → social_media (cascade)
           - parliament/forum tartışması → news_channel (threshold: çok taraflı katılım + yüksek sentiment polarizasyonu) [Faz 2+]
        6. Propagation delay: platformlar arası gecikme (config ile ayarlanabilir)
        """
        ...

**Determinizm ve Seed Yönetimi:**

Tüm rastgelelik tek bir `master_seed` ile kontrol edilir. Aynı seed = aynı nüfus = aynı kararlar = aynı sonuç.

```yaml
# config/realm.yaml
simulation:
  master_seed: 42
```

```python
# Kullanım:
rng = np.random.default_rng(master_seed)
# Her alt-sistem kendi seed'ini master'dan türetir
agent_rng = np.random.default_rng(master_seed + agent_id_hash)
```

**Not:** LLM backend kullanıldığında (Mod B/C kişilik üretimi, rapor aşaması) LLM temperature > 0 ise deterministiklik kırılır. Çözüm: LLM ile üretilen sonuçlar cache'lenir — aynı seed = aynı cache = aynı sonuç. Simülasyon loop'u kendisi %100 deterministiktir (vektör tabanlı, LLM call yok).

**Checkpoint & Fork Mekanizması:**

Crash recovery ve simülasyon dallanması (branching) aynı altyapıyı paylaşır:

```python
class SimulationEngine:
    def checkpoint(self) -> str:
        """Tam state snapshot'ı SQLite'a kaydet. Checkpoint dosya yolunu döndür."""
        ...

    def fork(self, checkpoint_path: str, branch_seed_offset: int = 0) -> 'SimulationEngine':
        """Checkpoint'ten yeni bir simülasyon dalı başlat."""
        ...

    def resume(self, checkpoint_path: str):
        """Crash sonrası son checkpoint'ten devam et."""
        ...
```

```yaml
# config/realm.yaml
simulation:
  checkpoint_interval: 10     # Her 10 tick'te otomatik checkpoint
  max_checkpoints: 5          # Disk alanı yönetimi, eski checkpoint'lar silinir
  checkpoint_dir: "db/checkpoints/"
```

**Branching (Faz 3+):** Aynı state'ten farklı senaryoları paralel çalıştırma — "savaş çıkarsa" vs "çıkmazsa" karşılaştırması. Astrolojik kalibrasyon için de kullanılır: gerçek transit takvimi vs hayali transit senaryosu.

**Ajan Karar Algoritması:**

Her tick'te ajan davranışı trait vektörüne dayalı probabilistik kararlarla belirlenir:

```
1. Aktif ajan seçimi:
   activity_probability = f(extraversion, current_mood, transit_boost)
   → Yüksek extraversion + pozitif transit = daha aktif

2. Konu değerlendirme:
   relevance = f(profession, expertise, trait_vector, cultural_modifier)
   → Finans uzmanı kripto haberi = yüksek relevance

3. Aksiyon seçimi (probabilistik):
   - post olasılığı   ∝ extraversion × communication_assertiveness
   - reply olasılığı  ∝ agreeableness × empathy (veya contrarian_tendency)
   - like/repost      ∝ herd_susceptibility × topic_relevance
   - ignore           ∝ (1 - topic_relevance)

4. Sentiment belirleme:
   sentiment = base_trait + transit_modifier + cultural_modifier + recent_events_impact
```
```

### 5.6 TransitModulator (realm/simulation/transit_modulator.py)

**Amaç:** Simülasyon zamanına göre ajan davranışlarını astrolojik transitlerle modüle etmek. İki katmanlı çalışır: bireysel (natal'e transit) ve kolektif (dönemin astrolojik iklimi).

**Çalışma Prensibi:**

```
Simülasyon zamanı: t

=== KATMAN 1: KOLEKTİF ASTROLOJİK İKLİM (tüm ajanları etkiler) ===
  1. Era transitleri: yavaş gezegen burç geçişleri
     - Pluto Kova'da (2024-2044) → toplumsal dönüşüm, teknoloji devrimi,
       otorite yapılarının çözülmesi → tüm ajanlar: contrarian_tendency ↑,
       tradition_vs_progress ↑
     - Neptune Koç'a geçişi (2025-2039) → bireysel spiritüellik,
       kolektif illüzyon riski → spirituality ↑, herd_susceptibility ↑
  2. Orta vadeli geçişler:
     - Saturn burç geçişleri (~2.5 yıl) → sektörel disiplin/kısıtlama
     - Jupiter burç geçişleri (~1 yıl) → sektörel genişleme/iyimserlik
  3. Kısa vadeli kolektif etki:
     - Mars-Uranüs karesi → küresel volatilite spike
     - Venüs-Jüpiter kavuşumu → piyasa iyimserliği dalgası
     - Merkür retrosu → iletişim kazaları, geciken anlaşmalar
  4. Ay fazı: tüm ajanlar üzerinde hafif global modifier
     - Yeni Ay → yeni başlangıçlar, risk alma eğilimi ↑
     - Dolunay → duygusal yoğunluk, çatışma olasılığı ↑
  5. Tutulmalar: yüksek etkili kolektif olaylar, ilgili burç aksında
     amplifikasyon

=== KATMAN 2: BİREYSEL TRANSİTLER (ajan bazlı) ===
  Her ajan için:
  1. Natal haritaya göre aktif transitleri hesapla (AstroCore üzerinden)
  2. Her aktif transit için etki katsayılarını belirle:
     - Transit tipi (conjunction=güçlü, trine=yumuşak, square=gergin)
     - Transit gezegen hızı (yavaş=uzun etki, hızlı=kısa etki)
     - Orb (tam aspekte yakınlık)
  3. Katsayıları ilgili trait'lere uygula:
     - Mars transit natal Moon square → emotional_reactivity *= 1.4
     - Jupiter transit natal Sun conjunction → financial_optimism *= 1.3
     - Saturn transit natal Mars → impulsivity *= 0.7, patience *= 1.3
  4. Retro gezegenler: ilgili alanları yavaşlat/içselleştir

=== SONUÇ: Nihai trait vektörü ===
  final_trait = base_trait × cultural_mod × collective_astro_mod × individual_transit_mod
```

**Performans Optimizasyonu:**

Transit hesaplaması ayrıştırılmış mimaride çalışır — Kerykeion tick başına yalnızca 1 kez çağrılır:

```
Tick başı:
  1. Transit gezegen pozisyonları = calc_transit_once(sim_time)
     → 1 Kerykeion call, ~50ms (tüm ajanlar için aynı)

  Her ajan için:
  2. natal = agent.cached_natal         # İlk üretimde hesaplanmış, SQLite'ta cache
  3. aspects = fast_aspect_check(       # Saf matematik, ~0.1ms/ajan
       transit_positions, natal.planets
     )

  Toplam: ~50ms + 10K × 0.1ms ≈ 1.05 sn/tick
  vs naive (10K × Kerykeion call): ~500 sn/tick → 500x hızlanma
```

Node ve Chiron transit etkileri de bu pipeline'a dahildir. İleride mikro-optimizasyon olarak yavaş gezegen pozisyonları (Pluto ~0.01°/gün) birden fazla tick boyunca cache'lenebilir.

### 5.7 Visualization (realm/visualization/)

**Amaç:** Ajan ağını nöral synapse benzeri interaktif bir grafik olarak görselleştirmek.

**Tasarım:**

```
Nöronlar = Ajanlar
  - Boyut: etki gücü (influence score)
  - Renk: dominant element (ateş=kırmızı, toprak=yeşil, hava=mavi, su=mor)
  - Parlaklık: mevcut aktivite seviyesi
  - İç halka: meslek kategorisi

Synapse'lar = Etkileşimler
  - Kalınlık: etkileşim yoğunluğu
  - Renk: etkileşim türü (agree=yeşil, disagree=kırmızı, neutral=gri)
  - Animasyon: aktif etkileşim pulse efekti

Kümelenmeler:
  - Coğrafi (ülke/bölge bazlı cluster'lar)
  - Fikri (benzer görüşler birbirine yakın)
  - Mesleki (uzman grupları)

Ek Katmanlar (toggle):
  - Transit etkisi: aktif transiti olan ajanlar halo ile
  - Mood heatmap: bölgesel duygu durumu
  - Information flow: bilgi yayılım animasyonu
```

**Teknoloji:**
- NetworkX: graf hesaplama, layout, metrikler
- D3.js: interaktif web görselleştirme
- Force-directed layout: doğal kümelenme
- FastAPI: async web server + WebSocket (dashboard ile birleşik)

### 5.8 OutputLayer (realm/output/)

**Dashboard Bileşenleri:**

```
┌────────────────────────────────────────────────────────┐
│  REALM Dashboard                          [2026-04-22] │
├──────────────┬─────────────────────────────────────────┤
│ Global Mood  │  ████████░░  72% Optimistic             │
│ Fear Index   │  ██░░░░░░░░  18%                        │
│ Activity     │  ██████░░░░  61%                        │
├──────────────┴─────────────────────────────────────────┤
│  Sector Sentiment                                      │
│  Finance ███████░░░ 68%  │  Politics █████░░░░░ 52%   │
│  Tech    ████████░░ 78%  │  Social   ██████░░░░ 63%   │
├────────────────────────────────────────────────────────┤
│  Active Transits                                       │
│  Mars □ Uranus (exact: Apr 24) → Volatility warning   │
│  Mercury Rx (Apr 18 - May 11) → Communication noise   │
├────────────────────────────────────────────────────────┤
│  [Ask a Question]                                      │
│  "Will BTC rise in the next 7 days?"                  │
│  → Prediction: 62% YES │ Confidence: Medium           │
│  → Key drivers: Mars-Uranus square amplifying risk    │
│     appetite, but Mercury Rx creating hesitation       │
│  → Astro factors: Jupiter trine Sun (optimism wave)   │
│  → Cultural signal: Asian markets bullish, EU cautious│
└────────────────────────────────────────────────────────┘
```

**Q&A Prediction Çıktı Formatı:**

```python
@dataclass
class PredictionResult:
    question: str
    answer: str                     # "YES" / "NO" / "UNCERTAIN"
    probability: float              # 0.0 - 1.0
    confidence: str                 # "low" / "medium" / "high"
    key_drivers: List[str]          # Ana tetikleyiciler
    astro_factors: List[str]        # Astrolojik faktörler
    cultural_signals: List[str]     # Kültürel sinyaller
    dissenting_voices: List[str]    # Karşıt görüşler (önemli!)
    time_horizon: str               # "1 day", "7 days", "30 days"
    supporting_agent_ratio: float   # Bu sonucu destekleyen ajan oranı
    expert_consensus: float         # Uzmanlar arası uzlaşma
    simulation_ticks_used: int      # Kaç tick simüle edildi
```

### 5.9 NetworkTopology (realm/simulation/network.py)

**Amaç:** Ajanlar arası sosyal ağ topolojisini oluşturmak ve yönetmek.

**Model:** Hibrit (Small-world + Scale-free)

```
Katman 1 — Small-world temeli (intra-country):
  Watts-Strogatz modeli
  Her ajan k=10 yerel komşuya bağlı (ülke/meslek/sosyoekonomik kümeleme)
  p=0.1 rewiring ile cross-cluster köprüler
  → Yüksek clustering + kısa ortalama yol uzunluğu

Katman 2 — Scale-free hub'lar (inter-country):
  social_dominance + expert_status + influence skoru yüksek ajanlar
  → Preferential attachment ile ekstra bağlantı kazanır
  → Doğal hub/influencer yapısı oluşur (gazeteciler, iş insanları, akademisyenler)

Dinamik büyüme:
  Etkileşim → yeni bağ olasılığı (simülasyon sırasında ağ evrilir)
```

**Konfigürasyon:**

```yaml
# config/realm.yaml
network:
  topology: "hybrid"          # "small_world" | "scale_free" | "hybrid"
  local_k: 10                 # Ortalama yerel komşu sayısı
  rewire_p: 0.1               # Cross-cluster köprü olasılığı
  hub_boost_factor: 2.5       # Yüksek influence ajanların ekstra bağlantı çarpanı
  cross_country_ratio: 0.05   # Ülkeler arası bağlantı oranı
```

**Teknoloji:** NetworkX ile tek seferde kurulum (population generation sırasında). İki adım: `watts_strogatz_graph` → hub adaylarına preferential attachment ekleme.

### 5.10 PredictionEngine (realm/output/predictor.py)

**Amaç:** Q&A tahminlerini çok-branch simülasyonla üretmek.

**Algoritma:**

```python
def predict(question: str, horizon_days: int = 7, n_branches: int = 5) -> PredictionResult:
    """
    1. Soruyu parse et → topic, direction, horizon
    2. Mevcut state'ten N adet branch fork et:
       - Her branch farklı seed: master_seed + branch_seed_offset * branch_id
       - Aynı popülasyon, farklı rastgele etkileşim sırası
    3. Her branch'e topic focus inject et
    4. Her branch'i horizon kadar simüle et
    5. Her branch'ten ajan oylaması topla:
       - İlgili uzmanların stance dağılımı (expert_weight ile ağırlıklı)
       - Genel popülasyon sentiment trendi
       - Astrolojik iklim yönelimi
    6. Cross-branch aggregation:
       probability = branch'ler arası ortalama YES oranı
       confidence  = branch'ler arası varyans
         - Düşük varyans = yüksek confidence
         - 5/5 branch YES → probability≈0.95, confidence="high"
         - 3/5 branch YES → probability≈0.60, confidence="medium"
         - Yüksek varyans → confidence="low"
    7. Dissenting voices: azınlık görüşü neden farklı düşünüyor?
    """
    ...
```

**Trade-off:** `n_branches=1` ile hızlı kaba tahmin, `n_branches=20` ile yüksek güvenilirlikli derin analiz.

**Konfigürasyon:**

```yaml
# config/realm.yaml
prediction:
  default_branches: 5          # Q&A başına branch sayısı
  max_branches: 20             # Detaylı analiz için
  expert_weight: 3.0           # Uzman oylarının ağırlık çarpanı
  min_relevant_agents: 50      # Altında "insufficient data" döndür
  branch_seed_offset: 1000     # branch_seed = master_seed + offset * branch_id
```

### 5.11 Prompt Management (prompts/)

**Amaç:** LLM prompt'larını koddan ayırarak versiyon kontrolü, A/B test ve iterasyon hızı sağlamak.

**Yapı:**

```
prompts/
├── personality/
│   ├── system.yaml            # System prompt (kişilik analisti rolü)
│   └── user_template.yaml     # User prompt şablonu (natal harita → trait)
├── report/
│   ├── summary.yaml           # Simülasyon özet raporu
│   ├── prediction.yaml        # Tahmin açıklama şablonu
│   └── prediction_tr.yaml     # Türkçe rapor şablonu
├── spotlight/
│   └── narrative.yaml         # Spotlight ajan narratif üretimi
└── question_parser/
    └── parse_question.yaml    # Q&A soru parse prompt'u
```

**YAML Formatı:**

```yaml
version: "1.0"
role: "Astrolojik kişilik analisti"
task: "Natal haritadan trait vektörü üret"
output_format: "JSON TraitVector"
variables:
  - natal_chart_json
  - target_traits
template: |
  Aşağıdaki natal harita verisini analiz et:
  {natal_chart_json}
  
  Şu trait'ler için 0.0-1.0 arası değer üret:
  {target_traits}
```

Her prompt'ta `version` field'i zorunludur — hangi prompt versiyonuyla hangi sonucun üretildiği tracking edilebilir.

---

## 6. DATABASE SCHEMA

```sql
-- Ajan tablosu
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    birth_datetime TEXT NOT NULL,      -- ISO 8601
    birth_lat REAL NOT NULL,
    birth_lon REAL NOT NULL,
    birth_tz TEXT NOT NULL,
    gender TEXT,
    profession TEXT,
    education_level TEXT,
    socioeconomic_tier TEXT,           -- "lower", "middle", "upper", "marginal"
    is_expert INTEGER DEFAULT 0,
    expert_domains TEXT,               -- JSON array: ["finance", "tech"]
    natal_chart_json TEXT,             -- Tam natal harita (cache)
    trait_vector_json TEXT,            -- PersonalityEmbedder çıktısı (cache)
    cultural_modifier_json TEXT,       -- CulturalModifier çıktısı (cache)
    created_at TEXT DEFAULT (datetime('now'))
);

-- Simülasyon durumu
CREATE TABLE simulation_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    tick_number INTEGER NOT NULL,
    sim_datetime TEXT NOT NULL,         -- Simülasyon içi zaman
    global_mood REAL,
    global_fear_index REAL,
    global_activity REAL,
    sector_sentiments_json TEXT,        -- {"finance": 0.68, "tech": 0.78, ...}
    active_transits_json TEXT,
    snapshot_json TEXT,                 -- Tam state snapshot
    created_at TEXT DEFAULT (datetime('now'))
);

-- Ajan aksiyonları
CREATE TABLE agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    tick_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    platform TEXT NOT NULL,            -- "social_media", "market", ...
    action_type TEXT NOT NULL,         -- "post", "reply", "like", "repost"
    content TEXT,
    target_agent_id TEXT,              -- Reply/interaction hedefi
    sentiment REAL,                    -- -1.0 to 1.0
    influence_score REAL,
    transit_modifiers_json TEXT,       -- O anki aktif transit etkileri
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Seed data
CREATE TABLE seed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- "news_api", "crypto_api", "manual"
    title TEXT NOT NULL,
    content TEXT,
    category TEXT,                     -- "finance", "politics", "social", "tech"
    severity REAL,                     -- 0.0-1.0 etki büyüklüğü
    injected_at_tick INTEGER,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Tahmin sonuçları
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    question TEXT NOT NULL,
    result_json TEXT NOT NULL,          -- PredictionResult serialized
    actual_outcome TEXT,               -- Gerçekleşen sonuç (doğrulama için)
    accuracy_score REAL,               -- Tahmin doğruluk skoru (post-hoc)
    created_at TEXT DEFAULT (datetime('now'))
);

-- Ajan etkileşim ağı (graf kenarları)
CREATE TABLE agent_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id_1 TEXT NOT NULL,
    agent_id_2 TEXT NOT NULL,
    interaction_count INTEGER DEFAULT 0,
    affinity_score REAL DEFAULT 0.0,   -- -1.0 to 1.0
    last_interaction_tick INTEGER,
    FOREIGN KEY (agent_id_1) REFERENCES agents(id),
    FOREIGN KEY (agent_id_2) REFERENCES agents(id)
);
```

---

## 7. CONFIGURATION FILES

### 7.1 realm.yaml (Ana Konfigürasyon)

```yaml
realm:
  version: "0.1.0"
  name: "REALM"

  simulation:
    master_seed: 42              # Tam determinizm — aynı seed = aynı sonuç
    tick_interval: "1d"          # "1h", "4h", "1d"
    catchup_speed: 10            # Catch-up modunda hız çarpanı
    max_ticks_per_run: 365       # Tek seferde max tick
    seed_check_interval: 6       # Her 6 tick'te yeni seed kontrol
    checkpoint_interval: 10      # Her 10 tick'te otomatik checkpoint
    max_checkpoints: 5           # Disk alanı yönetimi
    checkpoint_dir: "db/checkpoints/"

  population:
    total_agents: 10000
    scale_target: 50000          # Gelecek hedef
    mode: "static"               # "static" | "semi_dynamic" | "dynamic"
    experience_drift: true       # Deneyim birikimi ile hafif trait kayması
    max_drift_ratio: 0.10        # Base trait'ten max sapma: %10

  personality:
    mode: "rule_based"           # "rule_based" | "llm" | "hybrid"
    cache_profiles: true         # Üretilen profilleri cache'le
    llm_batch_size: 50           # LLM modunda batch boyutu

  llm:
    default_backend: "ollama"    # "ollama" | "claude" | "openai" | "moonshot"
    personality_backend: "claude"  # Kişilik üretimi için ayrı backend
    report_backend: "claude"       # Rapor için ayrı backend
    simulation_backend: "ollama"   # Simülasyon etkileşimleri için

  database:
    path: "db/realm.db"
    backup_interval: 24          # Her 24 tick'te backup

  visualization:
    enabled: true
    web_port: 8888
    graph_layout: "force_directed"
    max_visible_nodes: 2000      # Performans için görsel limit
    update_interval: 5           # Her 5 tick'te görselleştirme güncelle

  birth_time:
    distribution: "realistic"   # "uniform" | "realistic"

  geography:
    granularity: "city"          # "city" | "country_center"
    cities_per_country: 20
    rural_offset_degrees: 1.0
    timezone_auto: true

  network:
    topology: "hybrid"           # "small_world" | "scale_free" | "hybrid"
    local_k: 10
    rewire_p: 0.1
    hub_boost_factor: 2.5
    cross_country_ratio: 0.05

  spotlight:
    enabled: true
    ratio: 0.02                  # Tick başına top %2 etkileşim

  prediction:
    default_branches: 5
    max_branches: 20
    expert_weight: 3.0
    min_relevant_agents: 50
    branch_seed_offset: 1000

  signal:                        # Future: entegrasyon
    polyliq_enabled: false
    argus_enabled: false
```

### 7.2 astrology.yaml

```yaml
astrology:
  system: "western_tropical"
  house_system: "placidus"

  celestial_bodies:
    core: true          # Sun–Pluto (10 gezegen)
    nodes: true         # North Node, South Node
    chiron: true        # Chiron
    lilith: false       # Black Moon Lilith (Faz 2+)
    asteroids: false    # Ceres, Pallas, Juno, Vesta (Faz 2+)

  orbs:
    conjunction: 8.0
    opposition: 8.0
    trine: 7.0
    square: 7.0
    sextile: 5.0
    quincunx: 3.0

  transit_orbs:
    # Transitlerde daha dar orb kullanılır
    conjunction: 3.0
    opposition: 3.0
    trine: 2.5
    square: 2.5
    sextile: 2.0

  transit_weights:
    # Yavaş gezegenler daha güçlü etki
    pluto: 1.0
    neptune: 0.95
    uranus: 0.90
    saturn: 0.85
    jupiter: 0.75
    mars: 0.60
    sun: 0.50
    venus: 0.45
    mercury: 0.40
    moon: 0.30      # Hızlı ama evrensel etki

  cultural_modifier:
    enabled: true
    blend_ratio: 0.3  # Kültürel modifier'ın trait vektöründeki ağırlığı
```

---

## 8. SEED DATA — FREE API SOURCES

**Reference:** github.com/public-apis/public-apis

### 8.1 News & Current Events
| API | Kullanım | Ücretsiz Limit |
|-----|----------|----------------|
| NewsAPI.org | Küresel haberler | 100 req/gün |
| GNews.io | Haber arama | 100 req/gün |
| MediaStack | Canlı haberler | 500 req/ay |
| Currents API | Güncel haberler | 600 req/gün |

### 8.2 Financial Data
| API | Kullanım | Ücretsiz Limit |
|-----|----------|----------------|
| CoinGecko | Kripto fiyatlar | 10-30 req/dk |
| Alpha Vantage | Hisse/forex | 25 req/gün |
| FRED API | ABD ekonomik veri | Sınırsız |
| Open Exchange Rates | Döviz kurları | 1000 req/ay |

### 8.3 Social & Demographic
| API | Kullanım | Ücretsiz Limit |
|-----|----------|----------------|
| REST Countries | Ülke verileri | Sınırsız |
| World Bank API | Kalkınma verileri | Sınırsız |
| UN Data API | Nüfus istatistikleri | Sınırsız |
| Random User API | İsim üretimi | Sınırsız |

### 8.4 Future Expansion (Not)
- RSS feed entegrasyonu (öncelikli genişleme)
- Son dakika haberleri (webhook/streaming)
- Sosyal medya trend API'leri
- Doğal afet / acil durum API'leri

---

## 9. IMPLEMENTATION PHASES

### Faz 1: AstroCore + PersonalityEmbedder (Temel Altyapı)
**Hedef:** Bir doğum verisi girişinden kişilik vektörü çıktısı alabilmek.
- [x] Kerykeion entegrasyonu ve NatalEngine
- [x] TraitVector dataclass
- [x] Rule-based PersonalityEmbedder (planet_traits.py)
- [x] Aspekt modifikasyon katsayıları
- [x] Unit test'ler
- [x] Bilinen natal haritalar ile doğrulama (örn: ünlü kişiler)

### Faz 2: DemographicGenerator + CulturalModifier
**Hedef:** 10.000 ajanlık gerçekçi dünya nüfusu üretmek.
- [x] Ülke verileri toplama (countries.json)
- [x] Nüfus dağılım algoritması
- [x] İsim üretici (ülke bazlı)
- [x] Meslek/eğitim/gelir dağılımı
- [x] Hofstede entegrasyonu
- [x] Marjinal profil üretici
- [x] 10K ajan üretimi ve doğrulama

### Faz 3: SimulationEngine
**Hedef:** Ajanların etkileşim kurabildiği bir simülasyon döngüsü.
- [x] Tick mekanizması ve simülasyon saati
- [x] Sosyal medya platformu (Faz 1 etkileşim alanı)
- [x] Ajan karar mekanizması (kural tabanlı)
- [x] EventBus (kelebek etkisi yayılımı)
- [x] State persistence (SQLite)
- [x] Catch-up mekanizması

### Faz 4: SeedIngestion
**Hedef:** Dış dünya verilerinin simülasyona otomatik beslenmesi.
- [x] API source adaptörleri (haber, finans, sosyal)
- [x] Entity extraction (varlık/ilişki çıkarma)
- [x] Knowledge graph oluşturma
- [x] Olay enjeksiyonu (seed → simülasyon olayı)
- [x] Manuel upload desteği

### Faz 5: TransitModulator
**Hedef:** Astrolojik transitlerin ajan davranışını zamana bağlı modüle etmesi. İki katmanlı: kolektif iklim + bireysel transit.
- [x] Kolektif astrolojik iklim hesaplama (era transitleri, yavaş gezegen geçişleri)
- [x] Kolektif modifier → tüm ajanlara global etki
- [x] Bireysel transit hesaplama pipeline (natal'e transit)
- [x] Transit → trait modifier mapping (bireysel)
- [x] Retro gezegen etkileri
- [x] Ay fazı + tutulma global modifier
- [x] Era/dönem bazlı büyük geçişler (Pluto burç değişimi vb.)
- [x] Nihai trait formülü: base × culture × collective × individual

### Faz 6: OutputLayer + Visualization
**Hedef:** Dashboard, tahmin Q&A, nöral synapse görselleştirme.
- [x] Dashboard backend (FastAPI + WebSocket)
- [x] Mood/sentiment metrikleri
- [x] Q&A prediction interface
- [x] Rapor üretici
- [x] NetworkX graf hesaplama
- [x] D3.js nöral synapse render
- [x] Interaktif web arayüzü

### Faz 7: Entegrasyon (Future)
- [ ] POLYLIQ sinyal bridge
- [ ] ARGUS sinyal bridge
- [ ] LLM backend genişlemesi

---

## 10. KEY DESIGN DECISIONS LOG

| # | Karar | Tarih | Gerekçe |
|---|-------|-------|---------|
| 1 | Sıfırdan yazım (fork değil) | 2026-04-22 | AGPL kısıtlamasından kaçınma, ticari esneklik |
| 2 | Kerykeion kütüphanesi | 2026-04-22 | Swiss Ephemeris tabanlı, JSON çıktı, LLM-uyumlu |
| 3 | Western tropical + kültürel modifier | 2026-04-22 | Tutarlı hesaplama + kültürel derinlik dengesi |
| 4 | SQLite + JSON | 2026-04-22 | Hafif, GMKtec uyumlu, POLYLIQ/ARGUS ile tutarlı |
| 5 | Plugin-based LLM backend | 2026-04-22 | Backend esnekliği, maliyet optimizasyonu |
| 6 | 10K başlangıç, ölçeklenebilir mimari | 2026-04-22 | Hızlı iterasyon, sonra büyütme |
| 7 | Hibrit kişilik üretimi (A→C yolu) | 2026-04-22 | Kural tabanlı başla, LLM'e geçiş yolu aç |
| 8 | Dinamik uzman dağılımı (3 mod) | 2026-04-22 | Karşılaştırmalı analiz imkanı |
| 9 | Nöral synapse görselleştirme | 2026-04-22 | Ajan ağının sezgisel görselleştirilmesi |
| 10 | Kelebek etkisi EventBus | 2026-04-22 | Her şey birbiriyle bağlantılı prensibi |
| 11 | Vektör tabanlı content + Spotlight | 2026-04-22 | Maliyet/performans optimizasyonu, kolektif sinyal yeterli |
| 12 | 13 gök cismi (10+Node+Chiron) | 2026-04-22 | Modern Batı astrolojisi standardı, config ile genişletilebilir |
| 13 | Tam deterministik (master_seed) | 2026-04-22 | A/B test, kalibrasyon, bilimsel geçerlilik |
| 14 | Hibrit ağ topolojisi | 2026-04-22 | Gerçek sosyal ağ yapısı: kümeleme + hub'lar |
| 15 | Ayrıştırılmış transit hesaplama | 2026-04-22 | 500x performans kazancı (1 sn vs 500 sn/tick) |
| 16 | Statik popülasyon + deneyim drift | 2026-04-22 | Basitlik + gerçekçilik dengesi |
| 17 | Şehir düzeyinde coğrafya | 2026-04-22 | Natal harita doğruluğu (enlem farkı ev pozisyonlarını etkiler) |
| 18 | Simülasyon branching (Faz 3+) | 2026-04-22 | Senaryo karşılaştırma, astrolojik kalibrasyon |
| 19 | Gerçekçi doğum saati dağılımı | 2026-04-22 | Uniform yapay eşitlik üretir, gerçek toplum yansıması |
| 20 | FastAPI (Flask değil) | 2026-04-22 | Async native, WebSocket, Pydantic entegrasyonu |
| 21 | Checkpoint + resume | 2026-04-22 | Branching ile birleşik mekanizma, crash recovery |
| 22 | Çok-branch prediction (varyans=confidence) | 2026-04-22 | Tek branch confidence ölçemez, Monte Carlo yaklaşımı |
| 23 | Faker isim üretimi | 2026-04-22 | 50+ locale, deterministik, statik JSON gereksiz |
| 24 | Versiyonlu YAML prompt yönetimi | 2026-04-22 | Kod-prompt ayrımı, A/B test, iterasyon hızı |
| 25 | Cross-platform propagation kuralları | 2026-04-22 | Parliament→news dahil, Faz 2+ genişleme |

---

## 11. DEPENDENCIES

### 11.1 Core
```
kerykeion>=5.12          # Astroloji hesaplama (Swiss Ephemeris)
pydantic>=2.0            # Veri doğrulama ve serialization
pyyaml>=6.0              # Konfigürasyon
python-dotenv>=1.0       # Environment variables
```

### 11.2 Database & Data
```
# SQLite built-in (Python stdlib)
requests>=2.31           # API calls
aiohttp>=3.9             # Async API calls
feedparser>=6.0          # RSS feed parsing (Future)
faker>=20.0              # Ülke bazlı isim üretimi (50+ locale)
timezonefinder>=6.0      # Koordinat → timezone dönüşümü
```

### 11.3 Simulation & Analysis
```
networkx>=3.2            # Graf hesaplama
numpy>=1.26              # Sayısal hesaplamalar
pandas>=2.1              # Veri analizi
```

### 11.4 Visualization & Web
```
fastapi>=0.110           # Web server (async, Pydantic entegre)
uvicorn>=0.27            # ASGI server
# D3.js (CDN, Python bağımlılığı yok)
# Chart.js (CDN, dashboard grafikleri)
```

### 11.5 LLM Backends (opsiyonel, kullanılana göre)
```
anthropic>=0.40          # Claude API
openai>=1.40             # OpenAI API
ollama>=0.4              # Ollama local
```

### 11.6 Development
```
pytest>=8.0              # Test
pytest-asyncio           # Async test
black                    # Formatter
ruff                     # Linter
```

---

## 12. HARDWARE & ENVIRONMENT

- **Machine:** GMKtec NucBox K8 Plus (Ryzen 7 8845HS, 32GB DDR5)
- **OS:** Windows + WSL2 (Ubuntu)
- **Python:** 3.11+
- **Concurrent processes:** POLYLIQ ve ARGUS aynı makinede çalışıyor
- **Dikkat:** RAM paylaşımı — 10K ajan in-memory yaklaşık 2-4 GB
- **Ollama:** Zaten kurulu (Hermes deneyiminden), Qwen 2.5 model mevcut

---

## 13. NOTES & FUTURE ROADMAP

### 13.1 Genişleme Alanları (Prioritized)
1. **RSS + Son dakika haberleri:** SeedIngestion'a real-time feed
2. **Çoklu platform etkileşimi:** Meclis, piyasa, akademi, sokak
3. **Vedik / Çin astroloji modülleri:** Region-native astroloji desteği
4. **3D görselleştirme:** Three.js ile immersive dünya modeli
5. **Distributed computing:** Birden fazla makine üzerinde büyük ölçekli simülasyon
6. **POLYLIQ entegrasyonu:** Polymarket trade sinyali olarak Realm prediction

### 13.2 Bilinen Riskler ve Limitasyonlar
- **LLM bias:** OASIS araştırmasında belirtildiği gibi, LLM ajanlar gerçek insanlardan daha hızlı polarize olabiliyor. Rule-based yaklaşımda bu risk daha düşük.
- **Astroloji doğruluğu:** Kişilik mapping'i deneysel — sürekli kalibrasyon gerekiyor. Gerçek dünya sonuçlarıyla karşılaştırılarak refine edilmeli.
- **API limitleri:** Ücretsiz API'lerin rate limit'leri simülasyon hızını kısıtlayabilir. Cache stratejisi kritik.
- **GMKtec kaynakları:** 32GB RAM ile 50K+ ajan zor olabilir. Disk-backed approach veya lazy loading gerekebilir.

### 13.3 MiroFish'ten Öğrenilen Dersler
- GraphRAG ile entity extraction güçlü bir pattern — SeedIngestion'da benzerini kullanacağız
- Dual-platform simülasyonu (Twitter + Reddit) iyi çalışıyor, biz de sosyal medya platformuyla başlıyoruz
- ReportAgent'ın simülasyon sonrası ortamda tool kullanarak analiz yapması güçlü — OutputLayer'da benzer yaklaşım

### 13.4 Kalibrasyon / Validasyon Stratejisi
- **Faz 1:** Bilinen natal haritalar ile trait vector doğrulama (ünlü kişiler: bilinen kişilik → beklenen trait vector)
- **Faz 3:** Geçmiş olaylar ile retrospektif simülasyon (bilinen sonuçla karşılaştırma — "2024 seçimleri" gibi)
- **Faz 5:** Transit etkisi kalibrasyonu (transit modifier katsayılarını gerçek dünya verileriyle tune etme)
- **Faz 6:** Prediction accuracy tracking (`predictions` tablosundaki `accuracy_score` — gerçekleşen sonuçlarla otomatik karşılaştırma)

### 13.5 Monitoring / Observability
Uzun çalışan simülasyonlarda sağlık takibi (`realm/core/monitoring.py`):
- Tick başına metrikler: süre, aktif ajan sayısı, aksiyon sayısı, bellek kullanımı
- Anomali tespiti: sentiment'in beklenmedik kayması, agent clustering bozulması
- Dashboard'a monitoring paneli (Faz 6)

---

## 14. GETTING STARTED (Faz 1 için)

```bash
# 1. Repo oluştur
mkdir realm && cd realm
git init

# 2. Python ortamı
python -m venv .venv
source .venv/bin/activate  # Linux/WSL
# .venv\Scripts\activate   # Windows

# 3. Temel bağımlılıkları kur
pip install kerykeion pydantic pyyaml python-dotenv pytest

# 4. Dizin yapısını oluştur (Faz 1 modülleri)
mkdir -p realm/{core,astro,personality}/{tests,}
mkdir -p config data/astro

# 5. İlk test: Kerykeion çalışıyor mu?
python -c "from kerykeion import AstrologicalSubject; print('OK')"
```

### 14.1 pyproject.toml Şablonu

```toml
[project]
name = "realm"
version = "0.1.0"
description = "Population-reaction simulation engine — pluggable trait diversification + scenario-delta reaction analysis"
requires-python = ">=3.11"
dependencies = [
    "kerykeion>=5.12",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "networkx>=3.2",
    "numpy>=1.26",
    "pandas>=2.1",
    "requests>=2.31",
    "aiohttp>=3.9",
    "faker>=20.0",
    "timezonefinder>=6.0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
]

[project.optional-dependencies]
llm = ["anthropic>=0.40", "openai>=1.40", "ollama>=0.4"]
dev = ["pytest>=8.0", "pytest-asyncio", "black", "ruff"]

[tool.pytest.ini_options]
testpaths = ["tests", "realm"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"
```

### 14.2 .gitignore

```
# Environment
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/

# Database
db/*.db
db/checkpoints/

# Build
dist/
*.egg-info/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

*Bu doküman, REALM projesinin yaşayan referansıdır. Her önemli karar ve değişiklik buraya kaydedilir.*
