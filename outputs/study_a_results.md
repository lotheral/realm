# Study A Retrodiction — official run

> 2026-08-18 23:56 · n_agents=100 n_ticks=30 n_branches=5 seed=42 · events=22
>
> Predicted shift = `reaction.shift.support × 100` (Sprint 21 pooled stance output). All events ran under their logged blinding regime. A negative overall result is a valid study outcome.

## Headline metrics

- **Directional accuracy:** 6/22 (27%), p=0.992, zero-preds=2 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** -0.357
- **Spearman ρ (magnitudes):** -0.105
- **Authorship-confidence ratio (first-class honesty metric):** high 9 / medium 10 / low 3

## Breakdown — by authorship confidence

- high: 3/9 (33%), p=0.910, zero-preds=0
- medium: 2/10 (20%), p=0.989, zero-preds=2
- low: 1/3 (33%), p=0.875, zero-preds=0

## Breakdown — by verification status

- unverified: 0/1 (0%), p=1.000, zero-preds=0
- verified: 6/21 (29%), p=0.987, zero-preds=2

## Breakdown — by mechanism tag

- approval_drop: 2/5 (40%), p=0.812, zero-preds=0
- confidence_index: 2/2 (100%), p=0.250, zero-preds=0
- policy_shift: 2/6 (33%), p=0.891, zero-preds=0
- rally: 0/9 (0%), p=1.000, zero-preds=2

## Per-event results

| event | regime | conf | ver | tag | predicted pp | observed pp | hit |
|---|---|---|---|---|---:|---:|---|
| fukushima_de_nuclear | sim_delta_isolated | medium | Y | policy_shift | -19.60 | +9.0 | miss |
| sept11_bush_approval | sim_delta_isolated | high | Y | rally | -27.20 | +35.0 | miss |
| gulf_war_bush_sr_approval | sim_delta_isolated | high | Y | rally | -27.80 | +25.0 | miss |
| iraq2003_bush_approval | sim_delta_isolated | high | Y | rally | -27.20 | +13.0 | miss |
| ford_nixon_pardon | sim_delta_isolated | high | Y | approval_drop | +42.40 | -21.0 | miss |
| falklands_thatcher | sim_delta_isolated | medium | Y | rally | +0.00 | +34.0 | miss |
| cuban_missile_kennedy | sim_delta_isolated | medium | Y | rally | -28.60 | +13.0 | miss |
| charlie_hebdo_hollande | sim_delta_isolated | medium | Y | rally | +0.00 | +21.0 | miss |
| nov2015_paris_hollande | sim_delta_isolated | medium | Y | rally | -24.40 | +7.0 | miss |
| coup2016_erdogan | sim_delta_isolated | low | Y | rally | -20.60 | +21.0 | miss |
| covid_johnson_approval | sim_delta_isolated | medium | Y | rally | -21.20 | +20.0 | miss |
| katrina_bush_approval | sim_delta_isolated | low | Y | approval_drop | -24.20 | -3.0 | HIT |
| jan6_trump_approval | sim_delta_isolated | medium | Y | approval_drop | -0.20 | -5.0 | HIT |
| truss_minibudget_con_support | sim_delta_isolated | low | Y | approval_drop | +46.40 | -7.0 | miss |
| sandy_hook_gun_laws | sim_delta_isolated | high | Y | policy_shift | +42.40 | +15.0 | HIT |
| parkland_gun_laws | sim_delta_isolated | high | Y | policy_shift | -0.20 | +7.0 | miss |
| dobbs_leak_prochoice | sim_delta_isolated | medium | Y | policy_shift | +42.60 | +6.0 | HIT |
| ukraine_finland_nato | sim_delta_isolated | high | Y | policy_shift | -20.80 | +32.0 | miss |
| ukraine_sweden_nato | sim_delta_isolated | medium | n | policy_shift | -23.00 | +14.0 | miss |
| lehman_consumer_sentiment | sim_delta_isolated | high | Y | confidence_index | -20.80 | -12.7 | HIT |
| covid_consumer_sentiment | sim_delta_isolated | high | Y | confidence_index | -20.20 | -29.2 | HIT |
| refugee2015_merkel | sim_delta_isolated | medium | Y | approval_drop | +0.40 | -9.0 | miss |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
