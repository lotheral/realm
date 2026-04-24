# BigFiveAdapter Validity Study (N=10000, seed=42)

Generated: 2026-04-24 04:21:28

## Methodology

A synthetic Big Five population (N agents) was sampled from Costa & McCrae adult norms (mean=0.50, std=0.17 per trait on [0,1]) with 6 literature-documented intercorrelation pairs: O~E=+0.15, O~C=-0.10, C~A=+0.20, C~N=-0.25, E~A=+0.15, E~N=-0.20. The same population was then run through four pipeline configurations — (BigFive adapter, Astrological adapter) x (calibration off, calibration on) — to compare distribution, pass-through accuracy, intercorrelation preservation, and butterfly-scenario sensitivity.

Calibration uses **adapter-specific stats**: `config/trait_calibration_big_five.json` for the BigFive path and `config/trait_calibration_astrological.json` for the Astrological path. Each was generated from a 5K population matching the adapter (`scripts/build_calibration_stats.py --adapter=<type>`). This removes the cross-distribution distortion that affected an earlier shared-stats version of this study.

## Section 1 — Population synthesis verification

Does the synthetic Big Five population match its target distribution?

| trait | target mean | observed mean | target std | observed std |
|-------|-------------|---------------|------------|--------------|
| openness | 0.500 | 0.499 | 0.170 | 0.170 |
| conscientiousness | 0.500 | 0.501 | 0.170 | 0.170 |
| extraversion | 0.500 | 0.500 | 0.170 | 0.168 |
| agreeableness | 0.500 | 0.501 | 0.170 | 0.170 |
| neuroticism | 0.500 | 0.498 | 0.170 | 0.168 |

Observed input correlations (should match targets within ±0.03):

| pair | target r | observed r |
|------|----------|------------|
| openness~extraversion | +0.15 | +0.142 |
| openness~conscientiousness | -0.10 | -0.082 |
| conscientiousness~agreeableness | +0.20 | +0.204 |
| conscientiousness~neuroticism | -0.25 | -0.236 |
| extraversion~agreeableness | +0.15 | +0.147 |
| extraversion~neuroticism | -0.20 | -0.202 |

## Section 2 — Big Five pass-through accuracy (BigFive path)

Per-trait Pearson r between input OCEAN scores and output Big Five values. Expect r >= 0.99 pre-cal (direct copy through adapter + CulturalModifier). Post-cal may drop slightly as calibration rescales toward the astrological reference mean.

| trait | cal OFF | cal ON |
|-------|---------|--------|
| openness | +0.996 | +0.996 |
| conscientiousness | +0.993 | +0.993 |
| extraversion | +0.996 | +0.996 |
| agreeableness | +0.998 | +0.998 |
| neuroticism | +1.000 | +1.000 |

## Section 3 — Derived traits (BigFive path, 13 literature-sourced)

Per-trait mean/std/skew/kurtosis. Two traits flagged as low-confidence by the derivation table: contrarian_tendency, authority_compliance.

### Cal OFF
| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| analytical_depth | 0.505 | 0.083 | +0.02 | -0.08 | yes |
| authority_compliance | 0.537 | 0.070 | -0.07 | -0.04 | yes |
| communication_assertiveness | 0.494 | 0.069 | +0.03 | -0.02 | yes |
| contrarian_tendency | 0.477 | 0.065 | +0.03 | -0.02 | yes |
| empathy | 0.505 | 0.080 | +0.00 | -0.06 | yes |
| financial_optimism | 0.496 | 0.082 | -0.00 | -0.09 | yes |
| impulsivity | 0.484 | 0.094 | +0.04 | +0.04 | yes |
| information_sharing | 0.500 | 0.062 | +0.03 | -0.03 | yes |
| loss_aversion | 0.508 | 0.061 | +0.06 | +0.01 | yes |
| patience | 0.526 | 0.096 | -0.03 | -0.00 | yes |
| persuasion_skill | 0.500 | 0.072 | -0.00 | -0.05 | yes |
| risk_appetite | 0.503 | 0.090 | -0.02 | +0.01 | yes |
| social_dominance | 0.516 | 0.075 | +0.02 | +0.00 | yes |

### Cal ON
| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| analytical_depth | 0.500 | 0.173 | +0.02 | -0.15 | yes |
| authority_compliance | 0.501 | 0.170 | -0.07 | -0.08 | yes |
| communication_assertiveness | 0.501 | 0.167 | +0.02 | -0.07 | yes |
| contrarian_tendency | 0.499 | 0.169 | +0.03 | -0.07 | yes |
| empathy | 0.499 | 0.170 | +0.00 | -0.08 | yes |
| financial_optimism | 0.504 | 0.168 | +0.00 | -0.14 | yes |
| impulsivity | 0.498 | 0.170 | +0.04 | -0.10 | yes |
| information_sharing | 0.500 | 0.168 | +0.02 | -0.09 | yes |
| loss_aversion | 0.496 | 0.170 | +0.05 | -0.10 | yes |
| patience | 0.502 | 0.171 | -0.02 | -0.11 | yes |
| persuasion_skill | 0.500 | 0.168 | +0.00 | -0.10 | yes |
| risk_appetite | 0.500 | 0.168 | -0.01 | -0.10 | yes |
| social_dominance | 0.501 | 0.168 | +0.01 | -0.07 | yes |

## Section 4 — Fallback traits + excluded (BigFive path)

The 5 fallback traits are effectively disabled on the BigFive path — no published Big Five correlation found in literature, so they stay at 0.5 in cal OFF. With adapter-specific calibration stats, cal ON should keep the mean near 0.5 (since the stats source has the same 0.5 mean) but stretch the std modestly. Saturation indicates the stretch factor was too aggressive for a near-zero source variance.

| trait | mean (cal OFF) | std (cal OFF) | mean (cal ON) | std (cal ON) | saturated (cal ON)? |
|-------|----------------|---------------|---------------|--------------|--------------------|
| herd_susceptibility | 0.521 | 0.024 | 0.499 | 0.170 | no |
| fomo_susceptibility | 0.497 | 0.014 | 0.503 | 0.171 | no |
| tradition_vs_progress | 0.492 | 0.019 | 0.498 | 0.170 | no |
| individualism | 0.473 | 0.036 | 0.500 | 0.171 | no |
| spirituality | 0.529 | 0.010 | 0.499 | 0.169 | no |
| political_spectrum | 0.500 | 0.000 | 0.500 | 0.000 | no |

Note: `political_spectrum` is excluded by design across all adapters (REALM models temperament, not ideology).

## Section 5 — Big Five intercorrelation preservation (BigFive path)

Does the input OCEAN correlation structure survive the pipeline? Input is the synthetic sample; outputs are the BigFive path, calibration off and on.

| pair | target | input observed | output (cal OFF) | output (cal ON) |
|------|--------|----------------|------------------|-----------------|
| openness~extraversion | +0.15 | +0.142 | +0.144 | +0.144 |
| openness~conscientiousness | -0.10 | -0.082 | -0.087 | -0.087 |
| conscientiousness~agreeableness | +0.20 | +0.204 | +0.200 | +0.200 |
| conscientiousness~neuroticism | -0.25 | -0.236 | -0.235 | -0.235 |
| extraversion~agreeableness | +0.15 | +0.147 | +0.146 | +0.146 |
| extraversion~neuroticism | -0.20 | -0.202 | -0.199 | -0.199 |

Sign preservation: 6/6 off, 6/6 on.

## Section 6 — Derived-trait structural intercorrelations (BigFive path, cal OFF)

Two derived traits sharing the same dominant OCEAN driver should correlate in a predictable direction. Predicted sign = sign of coefficient_a * coefficient_b on the shared driver. Tolerance benchmark: observed |r| >= 0.10 with matching sign counts as 'structure', otherwise 'noise-like'.

| trait_a | trait_b | shared driver | predicted sign | observed r | matches? |
|---------|---------|---------------|----------------|------------|----------|
| risk_appetite | analytical_depth | O | + | +0.375 | yes |
| impulsivity | loss_aversion | N | + | +0.201 | yes |
| social_dominance | financial_optimism | E | + | +0.644 | yes |
| social_dominance | communication_assertiveness | E | + | +0.955 | yes |
| social_dominance | persuasion_skill | E | + | +0.542 | yes |
| social_dominance | information_sharing | E | + | +0.502 | yes |
| empathy | contrarian_tendency | A | - | -0.801 | yes |
| empathy | authority_compliance | A | + | +0.664 | yes |
| financial_optimism | communication_assertiveness | E | + | +0.727 | yes |
| financial_optimism | persuasion_skill | E | + | +0.728 | yes |
| financial_optimism | information_sharing | E | + | +0.703 | yes |
| communication_assertiveness | persuasion_skill | E | + | +0.706 | yes |
| communication_assertiveness | information_sharing | E | + | +0.637 | yes |
| persuasion_skill | information_sharing | E | + | +0.943 | yes |
| contrarian_tendency | authority_compliance | A | - | -0.959 | yes |

**Structural match rate: 15/15 = 100%**

Mean |r| across all 78 unique derived-trait pairs: **0.368**.

Interpretation: derived traits show non-trivial coupling consistent with shared OCEAN drivers in the derivation table.

## Section 7 — Cross-path comparison: BigFive vs Astrological

Mean trait std across all 24 traits under each pipeline configuration.

| configuration | mean trait std | traits >= 0.14 |
|---------------|----------------|----------------|
| BigFive, cal OFF | 0.081 | 5/24 |
| BigFive, cal ON | 0.163 | 23/24 |
| Astrological, cal OFF | 0.067 | 0/24 |
| Astrological, cal ON | 0.160 | 23/24 |

## Section 8 — Butterfly lift (tech-news scenario, n=150, 12 ticks, 3 branches)

Baseline vs scenario tech_share under each configuration. Scenario injects the identical 20-headline Apple AI device cascade at tick 0 (same payload as `scripts/demo_butterfly.py`).

| configuration | baseline | scenario | Δ (lift) | relative % |
|---------------|----------|----------|----------|------------|
| big_five, cal OFF | 0.187 | 0.253 | +0.066 | +35.4% |
| big_five, cal ON  | 0.168 | 0.236 | +0.069 | +41.1% |
| astrological, cal OFF | 0.187 | 0.255 | +0.068 | +36.6% |
| astrological, cal ON  | 0.155 | 0.217 | +0.062 | +39.9% |

## Section 9 — Honest limitations

**Fallback-5 disabled on BigFive path:** herd_susceptibility, fomo_susceptibility, tradition_vs_progress, individualism, spirituality all stay at 0.5 on the BigFive path (cal OFF) because no published Big Five correlation was found for them. Under cal ON with adapter-specific stats, mean stays near 0.5 but std may saturate at tails when the stretch factor is large (e.g. spirituality, tradition_vs_progress where source std is ~0.01). See Section 4.

**Low-confidence derivations:** contrarian_tendency and authority_compliance were flagged as low-confidence in the derivation table (weak Big Five literature support). Their Section 3 numbers should be read as design sketches rather than validated claims.

**Calibrator now adapter-aware:** earlier sessions used a single `config/trait_calibration.json` built from an astrological run, applied to all adapters. As of 2026-04-24 the calibrator loads `config/trait_calibration_{adapter_type}.json` based on the active adapter, removing the cross-distribution distortion. Stats files must be regenerated when their underlying distribution changes (damping, derivation table, cultural blend, etc).

**Narrow derived-trait variance:** Section 3 cal-OFF stds reveal that each derived trait's std is bounded by the OCEAN input std (~0.17) scaled by its max coefficient (typically 0.3-0.45). Without calibration, derived traits sit around std=0.05-0.08 — similar to the DemographicAdapter narrow-variance finding from 2026-04-24. A BlendedAdapter combining BigFive + per-agent noise (e.g. astrological residuals or questionnaire jitter) is flagged as future work.

**Weak derived-trait intercorrelation structure** — see Section 6 match rate. Linear derivation from five independent OCEAN axes cannot reproduce the tangled structure of real human personality; richer mapping (cross-trait coupling or post-hoc correlation injection) is a roadmap item.

## Section 10 — Success criteria evaluation

| # | criterion | measurement | result |
|---|-----------|-------------|--------|
| 1 | BigFive mean trait std >= 0.14 (cal ON) | 0.163 | PASS |
| 2 | Big Five input<->output Pearson r >= 0.99 (cal OFF) | min = 0.993 | PASS |
| 3 | Input correlation signs preserved in output (cal OFF) | 6/6 | PASS |
| 4a | Derived 13 traits all std > 0.05 (cal OFF) | min = 0.061 | PASS |
| 4b | Derived 13 traits all std > 0.05 (cal ON) | min = 0.167 | PASS |
| 5 | Butterfly lift positive on BigFive path | cal OFF = +0.066, cal ON = +0.069 | PASS |
| 6 | Derived structural pairs match >= 50% | 15/15 = 100% | PASS |

## Summary

**7/7 criteria passed.**
