# Sprint 24 — Referent-Relation Channel + Held-Out Evaluation + Repositioning Surface + Study B Entries

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox steps.

**Goal:** Act on Study A's failure-mode analysis with clean methodology: implement a literature-prior *referent-relation* direction channel, evaluate it against the valence channel on BOTH the 22-event design set and a NEW verified held-out set; unlock the §6 repositioning surface (README identity, dashboard remnants, About caveat); write the first real Study B forward predictions. Completes the design doc §5 roadmap.

**Architecture:** The relation channel is an OFFLINE mechanism candidate evaluated in the harness only — NOT wired into the production API until it earns it (proof-first). `realm/validation/relation.py` classifies (event_summary, question) into archetype pairs by deterministic rules and returns a direction from a polarity matrix whose entries cite literature priors (rally-round-the-flag: Mueller 1970; threat→alliance support; hazard→hazard-limiting-policy support), not fitted coefficients. `scripts/run_study_a.py` gains `--channel valence|relation` and `--events` already allows the held-out file.

**Epistemics (load-bearing):** The 22-event set was seen during failure-mode analysis → any relation-channel result on it is in-sample AT THE CLASS LEVEL and must be labeled so. The held-out set (`study_a_holdout_events.json`, authored AFTER the matrix is frozen, from different events) is the honest test. Matrix polarities must be frozen (committed) BEFORE the held-out set is authored. Both results are published either way.

## Global Constraints

- `.venv/Scripts/python.exe`; suite stays green (998 base); ruff clean; version → `0.24.0` at the end.
- Relation matrix entries carry a `rationale` string citing the prior (literature/mechanism), never a Study-A event id.
- Held-out events: same schema, `sim_delta_isolated`, verified before the run (no unverified numbers in a decisive test), populations within the 66-country set.
- Commit per task; Bash for git; standard trailer.

---

### Task 1: Relation channel module (frozen matrix first)

**Files:** Create `realm/validation/relation.py`; Test `realm/validation/tests/test_relation.py`.

**Interfaces:**
- `classify_question(question: str) -> str` → one of `incumbent_standing | protective_policy | hazard_policy | rights_policy | confidence_index | unknown` (deterministic keyword rules; e.g. "approve/approval/satisfied/vote ... party" → incumbent_standing; "joining ... alliance/NATO/defense" → protective_policy; "stricter laws/phase-out/ban" → hazard_policy; "abortion/right" → rights_policy; "confident ... economy" → confidence_index).
- `classify_event(event_summary: str) -> str` → `external_attack | external_threat | self_inflicted | disaster | economic_shock | rights_threat | unknown` (keyword rules; "invade/attack/bomb/hijack/gunmen/coup" → external_attack; "war on the doorstep/invasion of <other country>" → external_threat; "pardon/budget/tax cuts/opens borders/orders" by the incumbent → self_inflicted; "earthquake/meltdown/hurricane/levees" → disaster; "bankruptcy/crash/markets/pandemic ... economy" → economic_shock; "overturn ... right/leak ... court" → rights_threat).
- `POLARITY_MATRIX: dict[tuple[str, str], tuple[int, str]]` — (event, question) → (+1|-1|0, rationale). Core priors: (external_attack, incumbent_standing) → **+1** "rally-round-the-flag (Mueller 1970)"; (external_threat, protective_policy) → **+1**; (disaster, hazard_policy) → **+1** "hazard salience raises support for hazard-limiting policy"; (disaster, incumbent_standing) → **−1** "blame attribution for response"; (self_inflicted, incumbent_standing) → **−1**; (economic_shock, confidence_index) → **−1**; (economic_shock, incumbent_standing) → **−1**; (rights_threat, rights_policy) → **+1** "threat-to-status-quo mobilization"; (external_attack, hazard_policy) → **+1** (mass shooting → stricter-law support); unknown pairs → 0.
- `relation_direction(event_summary, question) -> tuple[int, str, str, str]` → (polarity, event_type, question_type, rationale).

Steps: failing tests (classification of representative NEW sentences — not copied from dataset entries — plus matrix lookups and unknown→0) → implement → pass → ruff → **commit (matrix frozen at this commit)**.

### Task 2: Harness channel flag

**Files:** Modify `scripts/run_study_a.py`; extend `realm/validation/tests/test_run_study_a.py`.

- `--channel valence|relation` (default valence). For `relation`: predicted direction = matrix polarity; magnitude = fixed 10.0pp × polarity (direction-only claim — magnitudes are explicitly NOT the channel's claim; report says so); events with polarity 0 → predicted 0.0 (honest abstention, counted per the existing zero-pred rule). The relation channel needs NO simulation run (direction is analytic) — but keep the per-event report columns identical; add `event_type`/`question_type`/`rationale` columns to the relation report.
- Report header must label the run: relation@design-set = "IN-SAMPLE AT CLASS LEVEL"; relation@holdout = "HELD-OUT".
- Tests: `--channel` plumbing pure helpers (`relation_prediction(event) -> dict`).

### Task 3: Held-out dataset (authored AFTER Task 1 commit)

**Files:** Create `data/validation/study_a_holdout_events.json`; extend notes doc; extend `TestRealDataset` to also validate the holdout file (≥8 events, all verified).

Candidate events (verify each via web search; drop what can't be verified; target 8-10): bin Laden killing → Obama approval (Gallup); Iran hostage crisis → Carter rally (Gallup 32→58 region); Lewinsky/impeachment → Clinton approval UP (Gallup ~63→73, self-inflicted-scandal inversion — deliberate hard case for the matrix); Crimea 2014 → Putin approval (Levada 65→86, RU in country set); Afghanistan withdrawal 2021 → Biden approval drop (Gallup ~50→43); Oct 7 2023 → Netanyahu standing FELL (IL in country set; anti-rally hard case); Chernobyl 1986 → US opposition to new nuclear plants rose (Gallup); COVID March 2020 → Trump approval small rally (Gallup 44→49); George Floyd 2020 → support for BLM/police reform rose (Pew/Gallup); 7/7 2005 → Blair (only if verifiable). Every event: verified before inclusion, tags, outcome-free summaries.

### Task 4: Run all four cells + analysis

Runs: valence@holdout (full sim params, background), relation@design, relation@holdout. (valence@design already exists = official run.) Write `outputs/study_a_relation_analysis.md`: 2×2 table (channel × set), per-class breakdowns, explicit epistemics paragraph, and the decision rule stated in advance: the relation channel is promoted to a production option ONLY if held-out DA > 50% with p < 0.1 one-sided; otherwise it stays research. Commit.

### Task 5: Repositioning surface (§6 unlock)

- `realm/output/static/index.html`: title "REALM∵ Astrological Swarm Intelligence" → "REALM ∵ Population-Reaction Observatory" (+ any other astro-identity strings in that file's header only — the climate panel legitimately stays, it reports the transit modulator).
- `README.md`: audit identity claims — heading/tagline must present the reaction-distribution engine framing; astrology listed as one of four adapters; add a short "Validation status" block linking Study A (negative, published) + Study B.
- v2 dashboard About: add the §"heuristic-mode caveat" line (heuristic scenario deltas are event-valence propagation; Study A showed they do not predict poll shifts; the LLM scenario analyzer is the semantic channel).
- Naming decision (delegated): KEEP the name REALM — the name itself is astrology-neutral; only surfaces change. Record the decision + rationale in the design doc as §7.

### Task 6: Study B first entries

Three forward predictions with the FULL pipeline (LLM+web on), populations scoped, `resolve_by` dates when polls will exist: (1) US 2026 midterm generic-ballot/House control question (resolve 2026-11); (2) UMich consumer sentiment direction next release (resolve ~2026-09-15); (3) one Türkiye/Europe polling question with a known upcoming series. Append via `scripts/diary.py predict ...`; commit the diary file.

### Task 7: v0.24.0 + docs + push

pyproject → 0.24.0 + editable refresh; CHANGELOG; REALM_CLAUDE.md header + Sprint 24 block + test counts; README status; design doc §7 (naming decision + roadmap completion note); full pytest + ruff; commit; push; CI green.
