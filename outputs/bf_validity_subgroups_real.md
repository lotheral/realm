# Real-Data BigFive Sub-group Validity Matrix (N=10000, seed=42)

Generated: 2026-04-24 05:07:35

Informational-only breakdown of `validate_bf_study_real.py` criteria applied per sub-group (country, sex, age-band). Minimum sub-group size for evaluation: N >= 30. Butterfly lift (criterion 5) is omitted because per-sub-group branch simulations don't meaningfully characterize sub-group behavior with the n=150 branch size, and criterion 8-real is a whole-sample distribution check.

Criteria abbreviated as #1, #2, #3, #4a, #4b, #6 per §10.

## Overall (full real sample, baseline for comparison)

| subgroup | N | #1 mean std (cal ON) | #2 min r | #3 signs | #4a min std | #4b min std | #6 struct | passed |
|---|---|---|---|---|---|---|---|---|
| overall | 10000 | 0.151 PASS | 0.996 PASS | 10/10 PASS | 0.036 FAIL | 0.165 PASS | 15/15 PASS | 5/6 |

## Per-country (top 10 by sample N)

| subgroup | N | #1 mean std (cal ON) | #2 min r | #3 signs | #4a min std | #4b min std | #6 struct | passed |
|---|---|---|---|---|---|---|---|---|
| US | 8659 | 0.125 FAIL | 1.000 PASS | 10/10 PASS | 0.034 FAIL | 0.152 PASS | 15/15 PASS | 4/6 |
| GB | 670 | 0.128 FAIL | 1.000 PASS | 10/10 PASS | 0.035 FAIL | 0.154 PASS | 15/15 PASS | 4/6 |
| IN | 115 | 0.123 FAIL | 1.000 PASS | 10/10 PASS | 0.029 FAIL | 0.135 PASS | 15/15 PASS | 4/6 |
| PH | 102 | 0.113 FAIL | 1.000 PASS | 10/10 PASS | 0.033 FAIL | 0.139 PASS | 15/15 PASS | 4/6 |
| TH | 84 | 0.069 FAIL | 1.000 PASS | 10/10 PASS | 0.017 FAIL | 0.075 PASS | 15/15 PASS | 4/6 |
| DE | 48 | 0.128 FAIL | 1.000 PASS | 10/10 PASS | 0.027 FAIL | 0.124 PASS | 15/15 PASS | 4/6 |
| ZA | 38 | 0.109 FAIL | 1.000 PASS | 10/10 PASS | 0.030 FAIL | 0.118 PASS | 15/15 PASS | 4/6 |
| CN | 38 | 0.091 FAIL | 1.000 PASS | 10/10 PASS | 0.026 FAIL | 0.102 PASS | 15/15 PASS | 4/6 |
| FR | 35 | 0.138 FAIL | 1.000 PASS | 10/10 PASS | 0.036 FAIL | 0.151 PASS | 15/15 PASS | 4/6 |

## Per-sex

| subgroup | N | #1 mean std (cal ON) | #2 min r | #3 signs | #4a min std | #4b min std | #6 struct | passed |
|---|---|---|---|---|---|---|---|---|
| M | 3893 | 0.155 PASS | 0.995 PASS | 10/10 PASS | 0.036 FAIL | 0.162 PASS | 15/15 PASS | 5/6 |
| F | 6107 | 0.146 PASS | 0.996 PASS | 10/10 PASS | 0.035 FAIL | 0.155 PASS | 15/15 PASS | 5/6 |

## Per-age-band

| subgroup | N | #1 mean std (cal ON) | #2 min r | #3 signs | #4a min std | #4b min std | #6 struct | passed |
|---|---|---|---|---|---|---|---|---|
| 18-25 | 6605 | 0.149 PASS | 0.996 PASS | 10/10 PASS | 0.036 FAIL | 0.159 PASS | 15/15 PASS | 5/6 |
| 26-35 | 1912 | 0.152 PASS | 0.993 PASS | 10/10 PASS | 0.035 FAIL | 0.161 PASS | 15/15 PASS | 5/6 |
| 36-50 | 1176 | 0.148 PASS | 0.995 PASS | 10/10 PASS | 0.033 FAIL | 0.151 PASS | 15/15 PASS | 5/6 |
| 51+ | 307 | 0.130 FAIL | 0.999 PASS | 10/10 PASS | 0.032 FAIL | 0.145 PASS | 15/15 PASS | 4/6 |

## Interpretation hints

- Expect **#2 to pass everywhere** — the BigFiveAdapter pipe-through is a direct copy with a cultural modifier, so per-trait Pearson r should stay ≥ 0.99 independent of sub-group.

- Expect **#8-real style mean drift** (not shown here) to worsen in sub-groups with the largest IPIP-NEO response bias — typically younger age bands and English-speaking majorities.

- Small-N sub-groups (close to the minimum N threshold) will show noise in #3 and #6; weight interpretation toward the larger per-country cells.

- #1 (mean trait std cal ON) may FAIL in sub-groups where input variance is narrow — compression compounds through the calibrator when source std is low.
