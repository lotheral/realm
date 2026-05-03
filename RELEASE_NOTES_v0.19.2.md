# REALM v0.19.2

Cumulative release covering Sprints 7-19.2 — the entire post-Sprint-6 development arc, including the LLM-as-brain integration (Sprint 17), Polymarket backtest validation (Sprint 18), and the repositioning that followed (Sprint 19). The codebase is now stable and accompanied by an academic article draft.

📄 **Article:** [`REALM_ARTICLE_DRAFT.md`](./REALM_ARTICLE_DRAFT.md) — *REALM: Collective Sentiment Simulation Through Time-Seeded Trait Diversification*

📋 **Full per-sprint detail:** [`CHANGELOG.md`](./CHANGELOG.md), [`REALM_CLAUDE.md`](./REALM_CLAUDE.md) § 0, [`outputs/realm_milestone_report.md`](./outputs/realm_milestone_report.md)

---

## Headline shifts since v0.1 (Sprint 6)

### Repositioning (Sprint 19)
REALM is now framed as a **collective sentiment simulation platform**, not a market-beating point-prediction engine. Polymarket backtesting (Sprint 18) revealed that simulation alone produces near-random Brier scores (≈ 0.25). The simulation's value is in **scenario analysis**: modeling how agent populations shift under hypothetical events — a question prediction markets cannot answer.

Two distinct prediction modes:
- **Baseline** (`How likely is X?`) — LLM-dominant blend (85-95% LLM / 5-15% sim). LLM grounded in current data via optional Tavily/Brave web research.
- **Scenario** (`If Y happens, how does X change?`) — sim-dominant blend (40% LLM / 60% sim). Modeling agent perturbation, drift dynamics, and trait clustering.

### LLM-as-brain (Sprint 17)
- LLM-first category routing (3-second timeout, in-process LRU cache; keyword fallback on timeout / low confidence / unknown id)
- `QuestionAnalyzer` extracts subject / yes_means / no_means / relevant_traits / `llm_prior` / prior_reasoning per question
- `ScenarioAnalyzer` produces semantic per-trait perturbation (replaces sentiment-word counting)
- `PredictionNarrator` generates question-specific headline / drivers / dissent / caveat
- Per-category `llm_blend_weight` + `scenario_llm_blend_weight`
- Graceful degrade everywhere — no LLM env, no LLM calls

### Web research grounding (Sprint 18)
- `WebResearcher` with Tavily + Brave backends
- LLM generates 2-3 targeted queries → search → context injected into question-analysis prompt
- Auto-detect from `TAVILY_API_KEY` / `BRAVE_API_KEY` presence (no `REALM_WEB_SEARCH_PROVIDER` required)
- Surfaced on the API as `web_research_used: true`, `web_sources[]`

### Honest validation (Sprint 18)
- `realm/validation/polymarket.py` — Gamma API client + `BrierResult` + 3-way A/B (LLM-only vs sim-only vs blended)
- `scripts/backtest_polymarket.py` produces a markdown report
- 5-market smoke run shipped at `outputs/polymarket_backtest_smoke.md`. **Larger 50-market backtest with Sprint 19 weights is Sprint 20 backlog.**

### Sprint 16 — Geopolitics structural fix + 6-sprint latent bug
- Discovered + fixed Sprint 10 latent bug: `_EVENT_TRAIT_MAP` constant only held 6 of 15 events; `build_branch_sim` passed no override. Sprint 10's 6 events + Sprint 16's 3 new events were **silently no-op'd for 6 sprints**. Fix: pass `event_map=drift_bridge.event_map`. Pre-Sprint-16 calibrations were running on only 6 events.
- Three new geopolitics-pool drift events (regime_consolidation, diplomatic_stalemate, sanctions_pressure)
- New `baseline_probability_offset` per-category fine-tuning knob
- 4-tier calibration journey: 49.98% → 49.92% → 49.70% → **49.20%** (under the strict 49.5% target)

### Sprint 19.1 + 19.2 hotfixes
- Scenario perturbation transparency: `WHAT THE SCENARIO PUSHED` (LLM-derived per-trait deltas) shown separately from `WHAT THE SIM DRIFTED` (post-perturbation drift over N ticks)
- Hardcoded "drift events: financial_gain + leadership_act triggered" line replaced with real `scenario_event_summary`
- Tavily auto-detect from key presence
- Snap sub-thousandth trait values to `+0` (no more `-0.000` next to `0.000` IEEE 754 quirk)
- **Delta decomposition** (`delta_blend_shift` + `delta_sim_movement`) prevents the dual-blend artifact where LLM prior < 0.5 always read as "scenario pushes UP" regardless of scenario content

---

## Numbers

| metric | value |
|--------|-------|
| Tests | 533 → **887** (+354) |
| Drift event types | 6 → 15 |
| Categories | 9 |
| Countries | 66 |
| Traits per agent | 24 |
| Big Five validity | 8/8 PASS |
| Astrological validity | 4/4 PASS |
| Geopolitics calibration | 49.20% (target <49.5%) |
| Spread (8 categories) | 4.14pp |

---

## Known follow-ups (Sprint 20+)
- 50-market backtest with Sprint 19 recalibrated weights (5-market smoke is suggestive, not conclusive)
- CLOB prices-history fetch for proper Polymarket Brier methodology (current report uses settlement price → unrealistic 0.000)
- Trait-weight + LLM-blend-weight blending in multi-cat (Sprint 19 only blended drift event weights and scalar params)
- Per-category Brier + calibration curves
- Statistical-significance test (paired t-test / Wilcoxon) once N ≥ 30
- Vedic / Chinese astrology modules

---

## Quick start

```bash
realm_start.bat
```

Opens FastAPI on `:8420` + dashboard on `:8080/realm_dashboard_v2.html`. Detailed configuration (LLM keys, Tavily, etc.) in [`README.md`](./README.md).

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
