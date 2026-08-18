# Study A Retrodiction — smoke run

> 2026-08-18 23:37 · n_agents=40 n_ticks=10 n_branches=2 seed=42 · events=6 (LIMITED subset of 22)
>
> Predicted shift = `reaction.shift.support × 100` (Sprint 21 pooled stance output). All events ran under their logged blinding regime. A negative overall result is a valid study outcome.

## Headline metrics

- **Directional accuracy:** 1/6 (17%), p=0.984, zero-preds=1 (one-sided binomial vs 50%)
- **Spearman ρ (signed shifts):** -0.232
- **Spearman ρ (magnitudes):** 0.058
- **Authorship-confidence ratio (first-class honesty metric):** high 4 / medium 2 / low 0

## Breakdown — by authorship confidence

- high: 0/4 (0%), p=1.000, zero-preds=0
- medium: 1/2 (50%), p=0.750, zero-preds=1

## Breakdown — by verification status

- unverified: 1/2 (50%), p=0.750, zero-preds=1
- verified: 0/4 (0%), p=1.000, zero-preds=0

## Breakdown — by mechanism tag

- approval_drop: 0/1 (0%), p=1.000, zero-preds=0
- policy_shift: 1/1 (100%), p=0.500, zero-preds=0
- rally: 0/4 (0%), p=1.000, zero-preds=1

## Per-event results

| event | regime | conf | ver | tag | predicted pp | observed pp | hit |
|---|---|---|---|---|---:|---:|---|
| fukushima_de_nuclear | sim_delta_isolated | medium | n | policy_shift | -27.50 | -14.0 | HIT |
| sept11_bush_approval | sim_delta_isolated | high | Y | rally | -21.25 | +35.0 | miss |
| gulf_war_bush_sr_approval | sim_delta_isolated | high | Y | rally | -22.50 | +25.0 | miss |
| iraq2003_bush_approval | sim_delta_isolated | high | Y | rally | -21.25 | +13.0 | miss |
| ford_nixon_pardon | sim_delta_isolated | high | Y | approval_drop | +48.75 | -21.0 | miss |
| falklands_thatcher | sim_delta_isolated | medium | n | rally | +0.00 | +17.0 | miss |

## Caveats

- Unverified events carry authored (training-data) poll numbers — candidates, not confirmed data; see the by-verification breakdown and `docs/study_a_dataset_notes.md`.
- `sim_delta_isolated` measures ONLY the sentiment-driven scenario channel (LLM off, web off). Rally-type events are included as deliberate hard cases for a sentiment-sign mechanism.
- SMOKE run (reduced parameters/subset) — NOT the official Study A result; the official run is Sprint 23 scope.
