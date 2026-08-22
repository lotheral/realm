# Study A Retrodiction — third-relation-v2 run

> 2026-08-22 23:36 · channel=relation (matrix v2, analytic, no simulation) · events=8
>
> Relation channel: DIRECTION-ONLY claim from a frozen literature-prior polarity matrix (v1: commit f2df2de; v2: realm/validation/relation_v2.py, Sprint 27); magnitudes are fixed ±10pp placeholders and carry no information. Polarity-0 abstentions count as zero-prediction misses.
> EPISTEMICS: matrix v2 was authored AFTER the design and held-out results were known — BOTH of those sets are in-sample for v2. Only the third event set (authored after the v2 freeze commit) is a clean test; see docs/study_a_third_set_protocol.md.

## Headline metrics

- **Directional accuracy:** 3/8 (38%), p=0.855, zero-preds=3 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** 0.277
- **Spearman ρ (magnitudes):** -0.169
- **Authorship-confidence ratio (first-class honesty metric):** high 5 / medium 3 / low 0

## Breakdown — by authorship confidence

- high: 3/5 (60%), p=0.500, zero-preds=2
- medium: 0/3 (0%), p=1.000, zero-preds=1

## Breakdown — by verification status

- verified: 3/8 (38%), p=0.855, zero-preds=3

## Breakdown — by mechanism tag

- approval_drop: 1/4 (25%), p=0.938, zero-preds=2
- policy_shift: 1/2 (50%), p=0.750, zero-preds=1
- rally: 1/2 (50%), p=0.750, zero-preds=0

## Per-event results

| event | tag | event_type | question_type | predicted pp | observed pp | hit |
|---|---|---|---|---:|---:|---|
| saddam_capture_bush_approval | rally | military_success | incumbent_standing | +10.0 | +7.0 | HIT |
| partygate_johnson_favorability | approval_drop | unknown | incumbent_standing | +0.0 | -11.0 | miss |
| saturday_night_massacre_nixon | approval_drop | unknown | incumbent_standing | +0.0 | -3.0 | miss |
| mobilization_putin_approval | approval_drop | self_inflicted | incumbent_standing | -10.0 | -6.0 | HIT |
| uvalde_gun_laws | policy_shift | external_attack | hazard_policy | +10.0 | +14.0 | HIT |
| oct7_likud_support | approval_drop | external_attack | incumbent_standing | +10.0 | -9.0 | miss |
| three_mile_island_nuclear | policy_shift | disaster | unknown | +0.0 | -13.0 | miss |
| sandy_obama_approval | rally | disaster | incumbent_standing | -10.0 | +2.0 | miss |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
