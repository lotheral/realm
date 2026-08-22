# Study A Retrodiction — third-valence run

> 2026-08-22 23:39 · n_agents=100 n_ticks=30 n_branches=5 seed=42 · events=8
>
> Predicted shift = `reaction.shift.support × 100` (Sprint 21 pooled stance output). All events ran under their logged blinding regime. A negative overall result is a valid study outcome.

## Headline metrics

- **Directional accuracy:** 5/8 (62%), p=0.363, zero-preds=1 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** 0.317
- **Spearman ρ (magnitudes):** -0.488
- **Authorship-confidence ratio (first-class honesty metric):** high 5 / medium 3 / low 0

## Breakdown — by authorship confidence

- high: 2/5 (40%), p=0.812, zero-preds=1
- medium: 3/3 (100%), p=0.125, zero-preds=0

## Breakdown — by verification status

- verified: 5/8 (62%), p=0.363, zero-preds=1

## Breakdown — by mechanism tag

- approval_drop: 3/4 (75%), p=0.312, zero-preds=1
- policy_shift: 1/2 (50%), p=0.750, zero-preds=0
- rally: 1/2 (50%), p=0.750, zero-preds=0

## Per-event results

| event | regime | conf | ver | tag | predicted pp | observed pp | hit |
|---|---|---|---|---|---:|---:|---|
| saddam_capture_bush_approval | sim_delta_isolated | high | Y | rally | -0.20 | +7.0 | miss |
| partygate_johnson_favorability | sim_delta_isolated | high | Y | approval_drop | +0.00 | -11.0 | miss |
| saturday_night_massacre_nixon | sim_delta_isolated | high | Y | approval_drop | -0.20 | -3.0 | HIT |
| mobilization_putin_approval | sim_delta_isolated | high | Y | approval_drop | -26.00 | -6.0 | HIT |
| uvalde_gun_laws | sim_delta_isolated | high | Y | policy_shift | -0.20 | +14.0 | miss |
| oct7_likud_support | sim_delta_isolated | medium | Y | approval_drop | -24.00 | -9.0 | HIT |
| three_mile_island_nuclear | sim_delta_isolated | medium | Y | policy_shift | -22.80 | -13.0 | HIT |
| sandy_obama_approval | sim_delta_isolated | medium | Y | rally | +32.80 | +2.0 | HIT |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
