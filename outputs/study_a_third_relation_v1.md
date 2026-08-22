# Study A Retrodiction — third-relation-v1 run

> 2026-08-22 23:36 · channel=relation (matrix v1, analytic, no simulation) · events=8
>
> Relation channel: DIRECTION-ONLY claim from a frozen literature-prior polarity matrix (v1: commit f2df2de; v2: realm/validation/relation_v2.py, Sprint 27); magnitudes are fixed ±10pp placeholders and carry no information. Polarity-0 abstentions count as zero-prediction misses.
> EPISTEMICS: results on the 22-event design set are IN-SAMPLE AT THE CLASS LEVEL (the failure classes were known when the matrix was written); only the held-out set is a clean test.

## Headline metrics

- **Directional accuracy:** 1/8 (12%), p=0.996, zero-preds=5 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** 0.069
- **Spearman ρ (magnitudes):** 0.056
- **Authorship-confidence ratio (first-class honesty metric):** high 5 / medium 3 / low 0

## Breakdown — by authorship confidence

- high: 1/5 (20%), p=0.969, zero-preds=4
- medium: 0/3 (0%), p=1.000, zero-preds=1

## Breakdown — by verification status

- verified: 1/8 (12%), p=0.996, zero-preds=5

## Breakdown — by mechanism tag

- approval_drop: 0/4 (0%), p=1.000, zero-preds=3
- policy_shift: 1/2 (50%), p=0.750, zero-preds=1
- rally: 0/2 (0%), p=1.000, zero-preds=1

## Per-event results

| event | tag | event_type | question_type | predicted pp | observed pp | hit |
|---|---|---|---|---:|---:|---|
| saddam_capture_bush_approval | rally | unknown | incumbent_standing | +0.0 | +7.0 | miss |
| partygate_johnson_favorability | approval_drop | unknown | incumbent_standing | +0.0 | -11.0 | miss |
| saturday_night_massacre_nixon | approval_drop | unknown | incumbent_standing | +0.0 | -3.0 | miss |
| mobilization_putin_approval | approval_drop | unknown | incumbent_standing | +0.0 | -6.0 | miss |
| uvalde_gun_laws | policy_shift | external_attack | hazard_policy | +10.0 | +14.0 | HIT |
| oct7_likud_support | approval_drop | external_attack | incumbent_standing | +10.0 | -9.0 | miss |
| three_mile_island_nuclear | policy_shift | disaster | unknown | +0.0 | -13.0 | miss |
| sandy_obama_approval | rally | disaster | incumbent_standing | -10.0 | +2.0 | miss |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
