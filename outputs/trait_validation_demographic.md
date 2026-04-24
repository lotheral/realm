# REALM Trait Distribution Validation (N=10000)

Generated: 2026-04-24 04:28:39
Target std: 0.17 (Big Five adult norm on [0,1])
Pass threshold for individual trait: std >= 0.14

## Summary

- **Pre-calibration**: mean trait std = 0.053, 0/24 traits >= 0.14
- **Post-calibration**: mean trait std = 0.142, 20/24 traits >= 0.14

## Phase 3 decision gate

Pre-calibration mean std = 0.053 -> **Escalate** â€” source fix alone didn't reach 0.10; investigate.
Post-calibration mean std = 0.142

## Section A â€” Big Five (literature-validatable)

Expected: mean~0.50, std in [0.15, 0.20] per Costa & McCrae norms.
Means far from 0.50 indicate systematic bias in the raw astrology mapping.

### Pre-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| openness | 0.472 | 0.048 | -0.82 | +1.03 | no |
| conscientiousness | 0.522 | 0.066 | +1.37 | +2.42 | no |
| extraversion | 0.475 | 0.048 | +1.30 | +1.22 | no |
| agreeableness | 0.505 | 0.040 | -0.02 | -0.49 | no |
| neuroticism | 0.500 | 0.000 | +0.00 | +0.00 | no |

### Post-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| openness | 0.503 | 0.170 | -0.82 | +1.03 | yes |
| conscientiousness | 0.498 | 0.163 | +1.18 | +1.58 | yes |
| extraversion | 0.508 | 0.177 | +1.30 | +1.22 | yes |
| agreeableness | 0.504 | 0.170 | -0.02 | -0.49 | yes |
| neuroticism | 0.500 | 0.000 | +0.00 | +0.00 | no |

## Section B â€” Domain traits (no external ground truth)

These 19 traits have no population norm in the literature. Target std=0.17 is a REALM design choice, not an empirical benchmark. Interpret std alignment as 'model behaves as specified', not 'model matches reality'.

### Pre-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| risk_appetite | 0.510 | 0.076 | -0.69 | -0.41 | no |
| analytical_depth | 0.518 | 0.050 | +0.32 | -1.11 | no |
| impulsivity | 0.449 | 0.106 | +0.67 | -0.26 | no |
| patience | 0.582 | 0.127 | -0.23 | -0.76 | no |
| social_dominance | 0.553 | 0.038 | +0.02 | -0.90 | no |
| herd_susceptibility | 0.569 | 0.080 | -1.27 | +1.15 | no |
| authority_compliance | 0.621 | 0.084 | -1.40 | +1.77 | no |
| contrarian_tendency | 0.426 | 0.058 | +1.67 | +2.24 | no |
| empathy | 0.518 | 0.040 | +1.00 | +1.64 | no |
| financial_optimism | 0.485 | 0.035 | +0.99 | +1.33 | no |
| loss_aversion | 0.528 | 0.073 | +1.38 | +1.44 | no |
| fomo_susceptibility | 0.489 | 0.048 | +0.01 | -0.92 | no |
| communication_assertiveness | 0.481 | 0.037 | +1.40 | +2.05 | no |
| persuasion_skill | 0.500 | 0.000 | +0.00 | +0.00 | no |
| information_sharing | 0.500 | 0.000 | +0.00 | +0.00 | no |
| political_spectrum | 0.500 | 0.000 | +0.00 | +0.00 | no |
| tradition_vs_progress | 0.473 | 0.063 | -0.73 | +0.26 | no |
| individualism | 0.411 | 0.118 | +1.51 | +1.87 | no |
| spirituality | 0.596 | 0.033 | +0.36 | -1.54 | no |

### Post-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| risk_appetite | 0.497 | 0.171 | -0.69 | -0.41 | yes |
| analytical_depth | 0.498 | 0.171 | +0.32 | -1.11 | yes |
| impulsivity | 0.505 | 0.174 | +0.67 | -0.26 | yes |
| patience | 0.496 | 0.172 | -0.23 | -0.76 | yes |
| social_dominance | 0.497 | 0.168 | +0.02 | -0.90 | yes |
| herd_susceptibility | 0.499 | 0.170 | -1.27 | +1.15 | yes |
| authority_compliance | 0.499 | 0.170 | -1.40 | +1.77 | yes |
| contrarian_tendency | 0.501 | 0.170 | +1.66 | +2.22 | yes |
| empathy | 0.502 | 0.167 | +1.00 | +1.64 | yes |
| financial_optimism | 0.504 | 0.169 | +0.87 | +0.91 | yes |
| loss_aversion | 0.498 | 0.166 | +1.30 | +1.08 | yes |
| fomo_susceptibility | 0.503 | 0.171 | +0.01 | -0.92 | yes |
| communication_assertiveness | 0.500 | 0.169 | +1.40 | +2.05 | yes |
| persuasion_skill | 0.500 | 0.000 | +0.00 | +0.00 | no |
| information_sharing | 0.500 | 0.000 | +0.00 | +0.00 | no |
| political_spectrum | 0.500 | 0.000 | +0.00 | +0.00 | no |
| tradition_vs_progress | 0.498 | 0.170 | -0.73 | +0.26 | yes |
| individualism | 0.500 | 0.171 | +1.51 | +1.87 | yes |
| spirituality | 0.499 | 0.169 | +0.36 | -1.54 | yes |

## Section C â€” Big Five intercorrelation signs

Literature holds these pairs have specific signs. Wrong sign = mapping produces an implausible personality structure.

| pair | expected | pre-cal | post-cal | sign OK pre | sign OK post |
|------|----------|---------|----------|-------------|--------------|
| neuroticism~conscientiousness | -0.25 | +0.000 | +0.000 | NO | NO |
| neuroticism~extraversion | -0.20 | +0.000 | +0.000 | NO | NO |
| openness~extraversion | +0.15 | +0.613 | +0.613 | yes | yes |
| conscientiousness~agreeableness | +0.20 | -0.258 | -0.237 | NO | NO |
| extraversion~agreeableness | +0.15 | +0.366 | +0.366 | yes | yes |

## Section D â€” Histograms (selected traits)

ASCII histograms, 20 bins across [0, 1]. Real personality distributions aren't strictly normal; skew/bimodality is expected, not a failure.

### openness
```
PRE-CALIBRATION
    [0.00]  (0)
    [0.05]  (0)
    [0.10]  (0)
    [0.15]  (0)
    [0.20]  (0)
    [0.25]  (0)
    [0.30]  (170)
    [0.35] ### (713)
    [0.40] ### (874)
    [0.45] ############################## (6673)
    [0.50] ##### (1113)
    [0.55] ## (457)
    [0.60]  (0)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)

POST-CALIBRATION
    [0.00]  (0)
    [0.05] #### (406)
    [0.10] ### (393)
    [0.15]  (0)
    [0.20] ## (258)
    [0.25] # (104)
    [0.30] ##### (596)
    [0.35]  (0)
    [0.40] # (135)
    [0.45] ####### (733)
    [0.50] ########################### (2762)
    [0.55] ############################## (3043)
    [0.60] ## (260)
    [0.65] # (105)
    [0.70] ## (204)
    [0.75] ##### (544)
    [0.80] #### (457)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)
```

### neuroticism
```
PRE-CALIBRATION
    [0.00]  (0)
    [0.05]  (0)
    [0.10]  (0)
    [0.15]  (0)
    [0.20]  (0)
    [0.25]  (0)
    [0.30]  (0)
    [0.35]  (0)
    [0.40]  (0)
    [0.45]  (0)
    [0.50] ############################## (10000)
    [0.55]  (0)
    [0.60]  (0)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)

POST-CALIBRATION
    [0.00]  (0)
    [0.05]  (0)
    [0.10]  (0)
    [0.15]  (0)
    [0.20]  (0)
    [0.25]  (0)
    [0.30]  (0)
    [0.35]  (0)
    [0.40]  (0)
    [0.45]  (0)
    [0.50] ############################## (10000)
    [0.55]  (0)
    [0.60]  (0)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)
```

### risk_appetite
```
PRE-CALIBRATION
    [0.00]  (0)
    [0.05]  (0)
    [0.10]  (0)
    [0.15]  (0)
    [0.20]  (0)
    [0.25]  (0)
    [0.30] # (236)
    [0.35] #### (578)
    [0.40] ########### (1469)
    [0.45] ########### (1412)
    [0.50] ############################## (3691)
    [0.55] ##################### (2614)
    [0.60]  (0)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)

POST-CALIBRATION
    [0.00]  (0)
    [0.05] ## (236)
    [0.10]  (84)
    [0.15] ### (324)
    [0.20] # (170)
    [0.25] ######### (855)
    [0.30] ####### (614)
    [0.35] # (140)
    [0.40] ############## (1272)
    [0.45] ###### (577)
    [0.50] ####### (649)
    [0.55] ############################## (2627)
    [0.60]  (0)
    [0.65] ############################ (2452)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)
```

### empathy
```
PRE-CALIBRATION
    [0.00]  (0)
    [0.05]  (0)
    [0.10]  (0)
    [0.15]  (0)
    [0.20]  (0)
    [0.25]  (0)
    [0.30]  (0)
    [0.35]  (0)
    [0.40]  (174)
    [0.45] ############################## (5382)
    [0.50] ################ (2910)
    [0.55] ##### (996)
    [0.60] ## (538)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)

POST-CALIBRATION
    [0.00]  (0)
    [0.05] # (174)
    [0.10]  (0)
    [0.15]  (0)
    [0.20]  (0)
    [0.25]  (0)
    [0.30] # (114)
    [0.35] ############################## (2930)
    [0.40] ######################### (2473)
    [0.45] # (105)
    [0.50] ##### (557)
    [0.55] ############### (1529)
    [0.60] ####### (746)
    [0.65] #### (477)
    [0.70]  (75)
    [0.75] # (101)
    [0.80] # (181)
    [0.85]  (0)
    [0.90] # (117)
    [0.95] #### (421)
```

## Section E â€” Clamp saturation

Fraction of trait values hitting 0.0 or 1.0 exactly.
- Pre-calibration: 0/240000 (0.0%)
- Post-calibration: 728/240000 (0.3%)