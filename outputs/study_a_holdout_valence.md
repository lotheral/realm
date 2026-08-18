# Study A Retrodiction — holdout-valence run

> 2026-08-19 00:18 · n_agents=100 n_ticks=30 n_branches=5 seed=42 · events=8
>
> Predicted shift = `reaction.shift.support × 100` (Sprint 21 pooled stance output). All events ran under their logged blinding regime. A negative overall result is a valid study outcome.

## Headline metrics

- **Directional accuracy:** 3/8 (38%), p=0.855, zero-preds=1 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** 0.218
- **Spearman ρ (magnitudes):** -0.137
- **Authorship-confidence ratio (first-class honesty metric):** high 5 / medium 3 / low 0

## Breakdown — by authorship confidence

- high: 1/5 (20%), p=0.969, zero-preds=1
- medium: 2/3 (67%), p=0.500, zero-preds=0

## Breakdown — by verification status

- verified: 3/8 (38%), p=0.855, zero-preds=1

## Breakdown — by mechanism tag

- approval_drop: 1/1 (100%), p=0.500, zero-preds=0
- confidence_index: 1/2 (50%), p=0.750, zero-preds=1
- rally: 1/5 (20%), p=0.969, zero-preds=0

## Per-event results

| event | regime | conf | ver | tag | predicted pp | observed pp | hit |
|---|---|---|---|---|---:|---:|---|
| binladen_obama_approval | sim_delta_isolated | high | Y | rally | -0.20 | +6.0 | miss |
| iran_hostage_carter | sim_delta_isolated | high | Y | rally | -0.20 | +19.0 | miss |
| lewinsky_clinton_approval | sim_delta_isolated | medium | Y | rally | -0.20 | +9.0 | miss |
| crimea_putin_approval | sim_delta_isolated | medium | Y | rally | +0.60 | +21.0 | HIT |
| afghanistan_biden_approval | sim_delta_isolated | high | Y | approval_drop | -0.20 | -6.0 | HIT |
| covid_trump_approval | sim_delta_isolated | high | Y | rally | -24.20 | +5.0 | miss |
| brexit_gfk_confidence | sim_delta_isolated | high | Y | confidence_index | +0.00 | -11.0 | miss |
| kuwait_invasion_us_sentiment | sim_delta_isolated | medium | Y | confidence_index | -0.20 | -11.8 | HIT |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
