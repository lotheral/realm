# Study A Retrodiction — design-relation run

> 2026-08-20 02:00 · channel=relation (analytic, no simulation) · events=22
>
> Relation channel: DIRECTION-ONLY claim from the frozen literature-prior polarity matrix (commit f2df2de); magnitudes are fixed ±10pp placeholders and carry no information. Polarity-0 abstentions count as zero-prediction misses.
> EPISTEMICS: results on the 22-event design set are IN-SAMPLE AT THE CLASS LEVEL (the failure classes were known when the matrix was written); only the held-out set is a clean test.

## Headline metrics

- **Directional accuracy:** 20/22 (91%), p=0.000, zero-preds=1 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** 0.710
- **Spearman ρ (magnitudes):** 0.328
- **Authorship-confidence ratio (first-class honesty metric):** high 9 / medium 10 / low 3

## Breakdown — by authorship confidence

- high: 9/9 (100%), p=0.002, zero-preds=0
- medium: 8/10 (80%), p=0.055, zero-preds=1
- low: 3/3 (100%), p=0.125, zero-preds=0

## Breakdown — by verification status

- verified: 20/22 (91%), p=0.000, zero-preds=1

## Breakdown — by mechanism tag

- approval_drop: 4/5 (80%), p=0.188, zero-preds=1
- confidence_index: 2/2 (100%), p=0.250, zero-preds=0
- policy_shift: 6/6 (100%), p=0.016, zero-preds=0
- rally: 8/9 (89%), p=0.020, zero-preds=0

## Per-event results

| event | tag | event_type | question_type | predicted pp | observed pp | hit |
|---|---|---|---|---:|---:|---|
| fukushima_de_nuclear | policy_shift | disaster | hazard_policy | +10.0 | +9.0 | HIT |
| sept11_bush_approval | rally | external_attack | incumbent_standing | +10.0 | +35.0 | HIT |
| gulf_war_bush_sr_approval | rally | external_attack | incumbent_standing | +10.0 | +25.0 | HIT |
| iraq2003_bush_approval | rally | external_attack | incumbent_standing | +10.0 | +13.0 | HIT |
| ford_nixon_pardon | approval_drop | self_inflicted | incumbent_standing | -10.0 | -21.0 | HIT |
| falklands_thatcher | rally | external_attack | incumbent_standing | +10.0 | +34.0 | HIT |
| cuban_missile_kennedy | rally | external_attack | incumbent_standing | +10.0 | +13.0 | HIT |
| charlie_hebdo_hollande | rally | external_attack | incumbent_standing | +10.0 | +21.0 | HIT |
| nov2015_paris_hollande | rally | external_attack | incumbent_standing | +10.0 | +7.0 | HIT |
| coup2016_erdogan | rally | external_attack | incumbent_standing | +10.0 | +21.0 | HIT |
| covid_johnson_approval | rally | self_inflicted | incumbent_standing | -10.0 | +20.0 | miss |
| katrina_bush_approval | approval_drop | disaster | incumbent_standing | -10.0 | -3.0 | HIT |
| jan6_trump_approval | approval_drop | rights_threat | incumbent_standing | +0.0 | -5.0 | miss |
| truss_minibudget_con_support | approval_drop | self_inflicted | incumbent_standing | -10.0 | -7.0 | HIT |
| sandy_hook_gun_laws | policy_shift | external_attack | hazard_policy | +10.0 | +15.0 | HIT |
| parkland_gun_laws | policy_shift | external_attack | hazard_policy | +10.0 | +7.0 | HIT |
| dobbs_leak_prochoice | policy_shift | rights_threat | rights_policy | +10.0 | +6.0 | HIT |
| ukraine_finland_nato | policy_shift | external_attack | protective_policy | +10.0 | +32.0 | HIT |
| ukraine_sweden_nato | policy_shift | external_attack | protective_policy | +10.0 | +9.0 | HIT |
| lehman_consumer_sentiment | confidence_index | economic_shock | confidence_index | -10.0 | -12.7 | HIT |
| covid_consumer_sentiment | confidence_index | economic_shock | confidence_index | -10.0 | -29.2 | HIT |
| refugee2015_merkel | approval_drop | self_inflicted | incumbent_standing | -10.0 | -9.0 | HIT |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
