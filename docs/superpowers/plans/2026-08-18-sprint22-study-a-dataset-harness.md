# Sprint 22 — Study A Dataset + Retrodiction Harness + Study B Diary Bootstrap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Study A historical-retrodiction dataset (15–30 events with documented before/after opinion polls, blinding regime per event), the harness that scores REALM's predicted reaction shift against the observed poll deltas, and the Study B forward-prediction diary registry — per design doc §4.1/§4.2. Running the OFFICIAL study + article rewrite stays in Sprint 23.

**Architecture:** A `StudyAEvent` schema + loader in `realm/validation/study_a.py` validates `data/validation/study_a_events.json`. Pure-python metrics (directional accuracy + exact binomial test, Spearman with tie-ranks, confidence/tag breakdowns) live in `realm/validation/retrodiction.py`. `scripts/run_study_a.py` calls `predict_endpoint(PredictRequest(...))` in-process (same pattern as `scripts/backtest_polymarket.py`), enforcing each event's blinding regime, and compares `reaction.shift.support × 100` (the Sprint 21 first-class output) against `observed_shift_pp`. Study B is an append-only JSONL diary under `outputs/prediction_diary/` with a small CLI.

**Tech Stack:** Python 3.11, stdlib only for stats (`math.comb` — scipy is NOT a dependency), pytest, existing FastAPI pipeline in-process.

**Spec:** `docs/superpowers/specs/2026-08-18-reaction-distribution-repositioning-design.md` §4.1, §4.2, §5 row 22.

## Global Constraints

- Run everything with `.venv/Scripts/python.exe`; full suite must stay green (963 before this sprint); `ruff check .` clean.
- **Honesty rules (load-bearing):** every event carries `confidence` (high/med/low) + `verified` flag; poll values authored from model knowledge are DATA CANDIDATES until verified — the report must break all metrics down by confidence tier and by verified flag, and state the low/med/high ratio as a first-class metric. No mixing verified data with guesses in a single undifferentiated number. A negative result is a valid completion.
- **Blinding rules:** regime `sim_delta_isolated` → `use_llm=False, enable_web_research=False` (pre-cutoff events). Regime `post_cutoff_web_off` → `use_llm=True, enable_web_research=False`, only valid for events dated after 2026-01-31 (LLM cutoff guard in the loader). Every result row logs its regime.
- Sign convention: each event's `question` is phrased so YES = the polled metric's subject ("Will X be approved/supported?"); `observed_shift_pp = after_value - before_value`; predicted shift = `reaction.shift.support * 100`. Rally-type events (negative event → approval UP) are deliberately included and expected to be hard — no alignment fudging.
- Version bump to `0.22.0` in `pyproject.toml` only; refresh with `pip install -e . --no-deps`.
- Use Edit/Write tools for file changes; Bash tool for git commits; commit per task with the `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: Study A schema + loader

**Files:**
- Create: `realm/validation/study_a.py`
- Test: `realm/validation/tests/test_study_a.py`

**Interfaces:**
- Produces: `StudyAEvent` frozen dataclass (fields below), `load_events(path: str | Path) -> list[StudyAEvent]`, constants `REGIMES = ("sim_delta_isolated", "post_cutoff_web_off")`, `CONFIDENCE_LEVELS = ("high", "medium", "low")`, `LLM_CUTOFF_DATE = date(2026, 1, 31)`.
- `StudyAEvent` fields: `event_id: str`, `event_date: date`, `event_summary: str` (the scenario feed text), `question: str`, `population: PopulationSpec`, `poll_source: str`, `metric: str`, `before_value: float`, `after_value: float`, `before_date: str`, `after_date: str`, `observed_shift_pp: float`, `blinding_regime: str`, `confidence: str`, `verified: bool`, `verification_note: str`, `tags: tuple[str, ...]`, `notes: str`.
- Validation raises `ValueError` on: unknown regime/confidence, `post_cutoff_web_off` with `event_date <= LLM_CUTOFF_DATE`, `abs(observed_shift_pp - (after_value - before_value)) > 0.05`, empty `event_summary`/`question`, duplicate `event_id`, population that fails `PopulationSpec.validate()`.

- [ ] **Step 1: Write failing tests** (`test_study_a.py`) — build an in-memory event dict factory `make_event(**overrides)` with valid defaults (`blinding_regime="sim_delta_isolated"`, `event_date="2011-03-11"`, `population={"countries": ["DE"]}`, `before_value=40.0`, `after_value=26.0`, `observed_shift_pp=-14.0`, `confidence="medium"`); write the JSON to `tmp_path`, then test: happy path loads 1 event with parsed `PopulationSpec` and `date`; unknown regime raises; unknown confidence raises; shift-mismatch raises; `post_cutoff_web_off` with 2011 date raises (match `"post_cutoff"`); duplicate ids raise; bad population country raises.
- [ ] **Step 2: Run to verify failure** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement `study_a.py`** — `@dataclass(frozen=True)` + `load_events` that reads JSON `{"version": 1, "events": [...]}`, applies defaults (`verified=False`, `verification_note=""`, `tags=()`, `notes=""`), builds `PopulationSpec(**{k: tuple(v) if isinstance(v, list) else v ...})` — population dict keys map 1:1 to PopulationSpec kwargs with lists coerced to tuples — calls `.validate()`, parses `event_date` with `date.fromisoformat`, enforces all rules above.
- [ ] **Step 4: Tests pass; ruff clean.**
- [ ] **Step 5: Commit** `feat(sprint22): StudyAEvent schema + validating loader`.

---

### Task 2: Retrodiction metrics (pure python)

**Files:**
- Create: `realm/validation/retrodiction.py`
- Test: `realm/validation/tests/test_retrodiction.py`

**Interfaces (exact — Task 5 imports these):**
```python
@dataclass(frozen=True)
class DirectionalResult:
    hits: int; misses: int; zero_predictions: int; n: int
    accuracy: float          # hits / n (zero-predictions count as misses)
    p_value_one_sided: float # P(X >= hits | n, p=0.5), exact via math.comb

def directional_accuracy(predicted: Sequence[float], observed: Sequence[float]) -> DirectionalResult
def binomial_p_one_sided(hits: int, n: int) -> float
def spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> float  # average ranks on ties; 0.0 when n < 3 or zero variance
def breakdown(events, predicted, observed, key=lambda e: e.confidence) -> dict[str, DirectionalResult]
```
Semantics: a hit is `sign(pred) == sign(obs)` with both nonzero; `pred == 0` → `zero_predictions` (counted in `n` and as a miss); `obs == 0` never occurs in the dataset (loader tolerance) but if it did → miss.

- [ ] **Step 1: Failing tests** — DA: all-correct 4/4 accuracy 1.0 p==0.0625 (0.5^4); half-correct; zero-prediction counted as miss and in `zero_predictions`; binomial: `binomial_p_one_sided(8, 10)` ≈ 0.0546875 (C(10,8)+C(10,9)+C(10,10) over 1024 = 56/1024); spearman: perfect monotone → 1.0, reversed → −1.0, ties handled (e.g. xs=[1,2,2,3], ys=[1,2,3,4] → rho == pearson-of-ranks with average ranks ≈ 0.9487 within 1e-3), n<3 → 0.0; breakdown groups by key.
- [ ] **Step 2: Verify failure.** **Step 3: Implement** (rank via sorted index averaging; pearson on ranks in pure python). **Step 4: Pass + ruff.** **Step 5: Commit** `feat(sprint22): retrodiction metrics — exact binomial DA + Spearman`.

---

### Task 3: Author the dataset (~20 events)

**Files:**
- Create: `data/validation/study_a_events.json`
- Create: `docs/study_a_dataset_notes.md` (selection criteria, per-event sourcing notes, known caveats)
- Test: extend `realm/validation/tests/test_study_a.py` with `TestRealDataset` — loads the real file: ≥15 events, all regimes valid, every event has ≥1 tag from {"rally", "policy_shift", "confidence_index", "approval_drop"}, populations resolve, confidence ratio computable, ids unique.

Author 15–25 events from well-documented polling literature, each with `confidence` honestly set and `verified: false` initially. Event families to draw from (final numbers set during authoring, marked by confidence):
- **Aligned policy shifts** (negative event → support for subject falls): Fukushima→DE nuclear support; Fukushima→US nuclear favorability; refugee crisis 2015→Merkel approval; Katrina→Bush approval; Nixon pardon→Ford approval; Truss mini-budget→Truss/Con standing; Jan 6→Trump approval.
- **Rally events** (negative event → leader approval RISES — deliberate hard cases): 9/11→Bush 51→86 (Gallup); Gulf War 1991→Bush Sr.; Iraq 2003→Bush; Falklands→Thatcher; Charlie Hebdo + Nov 2015 Paris→Hollande; 2016 coup attempt→Erdoğan; Cuban missile crisis→JFK; COVID March 2020→Johnson (YouGov).
- **Confidence indices**: Lehman Sept 2008→Michigan ICS drop; COVID Feb→Apr 2020→Michigan ICS drop.
- **Security-policy swings**: Russia invasion 2022→Finland NATO support (~28→76, Yle/EVA); →Sweden NATO support; Sandy Hook→stricter-gun-law support (Gallup 43→58); Parkland→Gallup 60→67; Dobbs→Gallup pro-choice 49→55.

Every event: scenario-feed-style `event_summary` written as dated news copy (sentiment-bearing, no outcome leakage — the summary must not mention the poll response), question phrased YES=metric subject, country-scoped population, regime `sim_delta_isolated` (all are pre-cutoff), tags.

- [ ] **Step 1: Write `TestRealDataset` (failing — file absent).** **Step 2: Author the JSON + notes doc.** **Step 3: Tests pass (whole `realm/validation` suite).** **Step 4: Commit** `feat(sprint22): Study A dataset — N events, confidence-tagged, unverified`.

---

### Task 4: Verification pass (web research)

**Files:**
- Modify: `data/validation/study_a_events.json` (corrections + `verified`/`verification_note`)
- Modify: `docs/study_a_dataset_notes.md` (verification log)

Using web search, verify the before/after numbers for AT LEAST the events marked `confidence: high` plus any medium event whose numbers a search contradicts. Rules: a verified event gets `verified: true` + `verification_note` naming the source; a contradicted number is CORRECTED and noted; an unverifiable high event is downgraded to medium. Re-run the dataset test after edits. Commit `data(sprint22): Study A verification pass — X/Y events verified`.

---

### Task 5: Retrodiction harness script + smoke run

**Files:**
- Create: `scripts/run_study_a.py`
- Test: `realm/validation/tests/test_run_study_a.py` (imports the script's pure helpers via `importlib` — keep the script import-safe: all work under `if __name__ == "__main__":`)

**Interfaces:**
- Consumes: Task 1 loader, Task 2 metrics, `realm.api.predict.PredictRequest/predict_endpoint`, `PopulationSpecModel` field names.
- CLI: `--events data/validation/study_a_events.json --n-agents 100 --n-ticks 30 --n-branches 5 --seed 42 --limit N --out outputs/study_a_results.md --json outputs/study_a_results.json --label smoke`.
- Per event: build `PredictRequest(question=..., scenario_feed=event_summary, population=PopulationSpecModel(countries=[...], ...), master_seed=seed, use_llm/enable_web_research per regime)`; record `predicted_shift_pp = resp.reaction.shift.support * 100`, plus `resp.delta`, `resp.reaction.shift.oppose`, regime, per-event confidence.
- Report (md + json): run parameters; per-event table (id, regime, confidence, verified, predicted pp, observed pp, hit/miss); overall DA + one-sided binomial p; Spearman (predicted vs observed magnitudes, and separately on |values|); breakdowns by confidence tier, by verified flag, by tag; zero-prediction count; explicit caveat block (unverified events, smoke ≠ official run, sim_delta_isolated tests the sentiment-driven scenario channel only).
- Pure helper to test: `regime_flags(regime) -> dict` (`{"use_llm": False, "enable_web_research": False}` for `sim_delta_isolated`; `{"use_llm": True, "enable_web_research": False}` for `post_cutoff_web_off`; ValueError otherwise) and `event_to_request_kwargs(event, n_agents, n_ticks, n_branches, seed) -> dict`.

- [ ] **Step 1: Failing tests for the two pure helpers.** **Step 2: Implement script.** **Step 3: Smoke run:** `.venv/Scripts/python.exe scripts/run_study_a.py --limit 4 --n-agents 40 --n-ticks 10 --n-branches 2 --out outputs/study_a_smoke.md --json outputs/study_a_smoke.json --label smoke` — verify report renders, regimes logged, no crashes. **Step 4: ruff + tests.** **Step 5: Commit** `feat(sprint22): Study A retrodiction harness + smoke run`.

---

### Task 6: Study B diary bootstrap

**Files:**
- Create: `realm/validation/diary.py`
- Create: `scripts/diary.py`
- Create: `outputs/prediction_diary/README.md`
- Test: `realm/validation/tests/test_diary.py`

**Interfaces:**
- `realm/validation/diary.py`: `DIARY_PATH = Path("outputs/prediction_diary/entries.jsonl")`; `@dataclass DiaryEntry` (`entry_id, created_utc, question, population: dict, scenario_feed: str | None, predicted_probability, predicted_support, predicted_oppose, predicted_neutral, predicted_shift_support_pp: float | None, resolve_by: str, resolution: dict | None`); `append_entry(entry, path=...)` (JSONL append, creates parents); `load_entries(path=...) -> list[DiaryEntry]`; `score_entry(entry_id, observed_shift_pp, source, path=...) -> DiaryEntry` (rewrites file with resolution `{observed_shift_pp, source, scored_utc, directional_hit}`; ValueError on unknown id or already-scored).
- `scripts/diary.py` CLI: `predict "question" [--scenario ...] [--countries TR,DE] [--regions ...] [--age-min --age-max] [--resolve-by YYYY-MM-DD] [--n-agents ...]` → runs `predict_endpoint` LLM-on+web-on (forward predictions are epistemically clean — leakage impossible) and appends an entry, printing it; `list`; `score ENTRY_ID --observed-shift-pp X --source "..."`.
- Tests (tmp_path): append→load round-trip; score sets resolution + directional_hit; double-score raises; unknown id raises.

- [ ] **Step 1: Failing tests.** **Step 2: Implement module + CLI + README** (README: purpose per design §4.2, entry lifecycle, honesty rules — predictions are written BEFORE resolution, never edited, scoring only adds `resolution`). **Step 3: Tests + ruff.** **Step 4: Commit** `feat(sprint22): Study B forward-prediction diary bootstrap`.

---

### Task 7: Version, docs, full verification, push

- [ ] Bump `pyproject.toml` → `0.22.0`; `pip install -e . --no-deps`; verify `realm.__version__`.
- [ ] CHANGELOG `## v0.22.0` section; REALM_CLAUDE.md header + Sprint 22 block + test-count updates; README status line.
- [ ] Full suite (`pytest -q`) + `ruff check .`; record final test count into the docs.
- [ ] Commit `docs(sprint22): v0.22.0 — Study A dataset + harness, Study B diary`; push; watch CI to green.
