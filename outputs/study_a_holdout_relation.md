# Study A Retrodiction — holdout-relation run

> 2026-08-19 00:16 · channel=relation (analytic, no simulation) · events=8
>
> Relation channel: DIRECTION-ONLY claim from the frozen literature-prior polarity matrix (commit f2df2de); magnitudes are fixed ±10pp placeholders and carry no information. Polarity-0 abstentions count as zero-prediction misses.
> EPISTEMICS: results on the 22-event design set are IN-SAMPLE AT THE CLASS LEVEL (the failure classes were known when the matrix was written); only the held-out set is a clean test.

## Headline metrics

- **Directional accuracy:** 4/8 (50%), p=0.637, zero-preds=3 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** 0.491
- **Spearman ρ (magnitudes):** 0.057
- **Authorship-confidence ratio (first-class honesty metric):** high 5 / medium 3 / low 0

## Breakdown — by authorship confidence

- high: 3/5 (60%), p=0.500, zero-preds=1
- medium: 1/3 (33%), p=0.875, zero-preds=2

## Breakdown — by verification status

- verified: 4/8 (50%), p=0.637, zero-preds=3

## Breakdown — by mechanism tag

- approval_drop: 0/1 (0%), p=1.000, zero-preds=0
- confidence_index: 2/2 (100%), p=0.250, zero-preds=0
- rally: 2/5 (40%), p=0.812, zero-preds=3

## Per-event results

| event | tag | event_type | question_type | predicted pp | observed pp | hit |
|---|---|---|---|---:|---:|---|
| binladen_obama_approval | rally | external_attack | incumbent_standing | +10.0 | +6.0 | HIT |
| iran_hostage_carter | rally | external_attack | incumbent_standing | +10.0 | +19.0 | HIT |
| lewinsky_clinton_approval | rally | unknown | incumbent_standing | +0.0 | +9.0 | miss |
| crimea_putin_approval | rally | unknown | incumbent_standing | +0.0 | +21.0 | miss |
| afghanistan_biden_approval | approval_drop | external_attack | incumbent_standing | +10.0 | -6.0 | miss |
| covid_trump_approval | rally | unknown | incumbent_standing | +0.0 | +5.0 | miss |
| brexit_gfk_confidence | confidence_index | self_inflicted | confidence_index | -10.0 | -11.0 | HIT |
| kuwait_invasion_us_sentiment | confidence_index | external_attack | confidence_index | -10.0 | -11.8 | HIT |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
