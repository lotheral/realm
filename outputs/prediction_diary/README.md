# Study B — Forward-Prediction Diary

> Sprint 22 bootstrap. Design: `docs/superpowers/specs/2026-08-18-reaction-distribution-repositioning-design.md` §4.2.

An append-only registry (`entries.jsonl`) of REALM predictions on
**upcoming** events, written *before* the events resolve and scored as
polls arrive. Epistemically clean — leakage is impossible for events
that have not happened yet — so entries run with the FULL pipeline
(LLM + web research on), unlike Study A's blinded retrodiction.

## Rules (honesty contract)

1. Entries are written **before** resolution and **never edited**.
   Scoring only appends a `resolution` block; the prediction fields are
   immutable.
2. Every entry names its target population and a `resolve_by` date plus
   (when scored) the poll/source used to resolve it.
3. Directional hit = sign of `predicted_shift_support_pp` (or
   `predicted_probability - 0.5` when no scenario shift was predicted)
   matches the sign of the observed poll shift.
4. Misses are as much a result as hits. The diary accumulates slowly;
   that is by design.

## Usage

```bash
# make a prediction (full pipeline; appends an entry)
python scripts/diary.py predict "Will support for X rise?" \
  --scenario "..." --countries TR --resolve-by 2026-12-31

# list entries + running score
python scripts/diary.py list

# score an entry once the poll is out
python scripts/diary.py score diary_20260818_ab12cd34 \
  --observed-shift-pp 4.5 --source "Pollster, 2026-12-15"
```
