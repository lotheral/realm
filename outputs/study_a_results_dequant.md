# Study A Retrodiction — official-dequant run

> 2026-08-20 02:11 · n_agents=100 n_ticks=30 n_branches=5 seed=42 · events=22
>
> Predicted shift = `reaction.shift.support × 100` (Sprint 21 pooled stance output). All events ran under their logged blinding regime. A negative overall result is a valid study outcome.

## Headline metrics

- **Directional accuracy:** 4/22 (18%), p=1.000, zero-preds=3 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** -0.509
- **Spearman ρ (magnitudes):** -0.066
- **Authorship-confidence ratio (first-class honesty metric):** high 9 / medium 10 / low 3

## Breakdown — by authorship confidence

- high: 1/9 (11%), p=0.998, zero-preds=0
- medium: 2/10 (20%), p=0.989, zero-preds=3
- low: 1/3 (33%), p=0.875, zero-preds=0

## Breakdown — by verification status

- verified: 4/22 (18%), p=1.000, zero-preds=3

## Breakdown — by mechanism tag

- approval_drop: 2/5 (40%), p=0.812, zero-preds=0
- confidence_index: 0/2 (0%), p=1.000, zero-preds=0
- policy_shift: 2/6 (33%), p=0.891, zero-preds=0
- rally: 0/9 (0%), p=1.000, zero-preds=3

## Per-event results

| event | regime | conf | ver | tag | predicted pp | observed pp | hit |
|---|---|---|---|---|---:|---:|---|
| fukushima_de_nuclear | sim_delta_isolated | medium | Y | policy_shift | -16.00 | +9.0 | miss |
| sept11_bush_approval | sim_delta_isolated | high | Y | rally | -25.60 | +35.0 | miss |
| gulf_war_bush_sr_approval | sim_delta_isolated | high | Y | rally | -26.20 | +25.0 | miss |
| iraq2003_bush_approval | sim_delta_isolated | high | Y | rally | -25.60 | +13.0 | miss |
| ford_nixon_pardon | sim_delta_isolated | high | Y | approval_drop | +43.40 | -21.0 | miss |
| falklands_thatcher | sim_delta_isolated | medium | Y | rally | +0.00 | +34.0 | miss |
| cuban_missile_kennedy | sim_delta_isolated | medium | Y | rally | -26.60 | +13.0 | miss |
| charlie_hebdo_hollande | sim_delta_isolated | medium | Y | rally | +0.00 | +21.0 | miss |
| nov2015_paris_hollande | sim_delta_isolated | medium | Y | rally | -23.40 | +7.0 | miss |
| coup2016_erdogan | sim_delta_isolated | low | Y | rally | -17.80 | +21.0 | miss |
| covid_johnson_approval | sim_delta_isolated | medium | Y | rally | +0.00 | +20.0 | miss |
| katrina_bush_approval | sim_delta_isolated | low | Y | approval_drop | -21.40 | -3.0 | HIT |
| jan6_trump_approval | sim_delta_isolated | medium | Y | approval_drop | -0.20 | -5.0 | HIT |
| truss_minibudget_con_support | sim_delta_isolated | low | Y | approval_drop | +36.40 | -7.0 | miss |
| sandy_hook_gun_laws | sim_delta_isolated | high | Y | policy_shift | +38.60 | +15.0 | HIT |
| parkland_gun_laws | sim_delta_isolated | high | Y | policy_shift | -0.20 | +7.0 | miss |
| dobbs_leak_prochoice | sim_delta_isolated | medium | Y | policy_shift | +35.00 | +6.0 | HIT |
| ukraine_finland_nato | sim_delta_isolated | high | Y | policy_shift | -20.20 | +32.0 | miss |
| ukraine_sweden_nato | sim_delta_isolated | medium | Y | policy_shift | -22.40 | +9.0 | miss |
| lehman_consumer_sentiment | sim_delta_isolated | high | Y | confidence_index | +0.60 | -12.7 | miss |
| covid_consumer_sentiment | sim_delta_isolated | high | Y | confidence_index | +0.60 | -29.2 | miss |
| refugee2015_merkel | sim_delta_isolated | medium | Y | approval_drop | +0.40 | -9.0 | miss |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
