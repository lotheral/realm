# REALM Trait Distribution Validation (N=10000)

Generated: 2026-04-24 02:33:21
Target std: 0.17 (Big Five adult norm on [0,1])
Pass threshold for individual trait: std >= 0.14

## Summary

- **Pre-calibration**: mean trait std = 0.067, 0/24 traits >= 0.14
- **Post-calibration**: mean trait std = 0.160, 23/24 traits >= 0.14

## Phase 3 decision gate

Pre-calibration mean std = 0.067 -> **Escalate** — source fix alone didn't reach 0.10; investigate.
Post-calibration mean std = 0.160

## Section A — Big Five (literature-validatable)

Expected: mean~0.50, std in [0.15, 0.20] per Costa & McCrae norms.
Means far from 0.50 indicate systematic bias in the raw astrology mapping.

### Pre-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| openness | 0.832 | 0.069 | +0.32 | -0.35 | no |
| conscientiousness | 0.858 | 0.074 | -0.02 | -0.40 | no |
| extraversion | 0.886 | 0.082 | -0.47 | -0.44 | no |
| agreeableness | 0.859 | 0.078 | -0.08 | -0.54 | no |
| neuroticism | 0.811 | 0.063 | +0.40 | +0.29 | no |

### Post-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| openness | 0.499 | 0.173 | +0.32 | -0.35 | yes |
| conscientiousness | 0.501 | 0.170 | -0.01 | -0.41 | yes |
| extraversion | 0.502 | 0.168 | -0.47 | -0.44 | yes |
| agreeableness | 0.502 | 0.167 | -0.08 | -0.54 | yes |
| neuroticism | 0.495 | 0.170 | +0.40 | +0.28 | yes |

## Section B — Domain traits (no external ground truth)

These 19 traits have no population norm in the literature. Target std=0.17 is a REALM design choice, not an empirical benchmark. Interpret std alignment as 'model behaves as specified', not 'model matches reality'.

### Pre-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| risk_appetite | 0.805 | 0.097 | -0.08 | -0.25 | no |
| analytical_depth | 0.796 | 0.090 | +0.36 | -0.06 | no |
| impulsivity | 0.715 | 0.081 | +0.81 | +1.34 | no |
| patience | 0.595 | 0.083 | +0.29 | +1.03 | no |
| social_dominance | 0.885 | 0.079 | -0.23 | -0.63 | no |
| herd_susceptibility | 0.824 | 0.074 | +0.31 | +0.16 | no |
| authority_compliance | 0.601 | 0.065 | +0.49 | +1.67 | no |
| contrarian_tendency | 0.746 | 0.063 | +0.65 | +0.45 | no |
| empathy | 0.981 | 0.040 | -2.58 | +6.46 | no |
| financial_optimism | 0.809 | 0.074 | +0.26 | -0.12 | no |
| loss_aversion | 0.666 | 0.048 | +0.63 | +1.17 | no |
| fomo_susceptibility | 0.500 | 0.034 | -0.16 | +0.21 | no |
| communication_assertiveness | 0.734 | 0.086 | +0.45 | +0.57 | no |
| persuasion_skill | 0.913 | 0.063 | -0.23 | -0.85 | no |
| information_sharing | 0.726 | 0.079 | +1.13 | +1.85 | no |
| political_spectrum | 0.500 | 0.000 | +0.00 | +0.00 | no |
| tradition_vs_progress | 0.614 | 0.036 | +0.66 | +1.02 | no |
| individualism | 0.716 | 0.084 | +0.74 | +0.87 | no |
| spirituality | 0.659 | 0.061 | +0.33 | -0.53 | no |

### Post-calibration

| trait | mean | std | skew | kurtosis | meets std target? |
|-------|------|-----|------|----------|-------------------|
| risk_appetite | 0.495 | 0.166 | -0.08 | -0.25 | yes |
| analytical_depth | 0.501 | 0.171 | +0.36 | -0.06 | yes |
| impulsivity | 0.499 | 0.163 | +0.72 | +1.01 | yes |
| patience | 0.499 | 0.165 | +0.27 | +0.68 | yes |
| social_dominance | 0.498 | 0.169 | -0.23 | -0.63 | yes |
| herd_susceptibility | 0.497 | 0.169 | +0.31 | +0.16 | yes |
| authority_compliance | 0.499 | 0.165 | +0.41 | +1.32 | yes |
| contrarian_tendency | 0.498 | 0.167 | +0.59 | +0.17 | yes |
| empathy | 0.504 | 0.154 | -2.20 | +3.71 | yes |
| financial_optimism | 0.500 | 0.170 | +0.26 | -0.12 | yes |
| loss_aversion | 0.500 | 0.165 | +0.52 | +0.71 | yes |
| fomo_susceptibility | 0.501 | 0.167 | -0.14 | +0.07 | yes |
| communication_assertiveness | 0.499 | 0.169 | +0.44 | +0.54 | yes |
| persuasion_skill | 0.497 | 0.168 | -0.23 | -0.86 | yes |
| information_sharing | 0.500 | 0.167 | +0.98 | +1.26 | yes |
| political_spectrum | 0.500 | 0.000 | +0.00 | +0.00 | no |
| tradition_vs_progress | 0.497 | 0.167 | +0.55 | +0.51 | yes |
| individualism | 0.499 | 0.165 | +0.69 | +0.70 | yes |
| spirituality | 0.495 | 0.169 | +0.32 | -0.55 | yes |

## Section C — Big Five intercorrelation signs

Literature holds these pairs have specific signs. Wrong sign = mapping produces an implausible personality structure.

| pair | expected | pre-cal | post-cal | sign OK pre | sign OK post |
|------|----------|---------|----------|-------------|--------------|
| neuroticism~conscientiousness | -0.25 | +0.015 | +0.015 | NO | NO |
| neuroticism~extraversion | -0.20 | -0.011 | -0.011 | yes | yes |
| openness~extraversion | +0.15 | -0.007 | -0.007 | NO | NO |
| conscientiousness~agreeableness | +0.20 | +0.057 | +0.057 | yes | yes |
| extraversion~agreeableness | +0.15 | +0.086 | +0.086 | yes | yes |

## Section D — Histograms (selected traits)

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
    [0.30]  (0)
    [0.35]  (0)
    [0.40]  (0)
    [0.45]  (0)
    [0.50]  (0)
    [0.55]  (0)
    [0.60]  (1)
    [0.65]  (94)
    [0.70] ########### (1078)
    [0.75] ####################### (2242)
    [0.80] ############################## (2830)
    [0.85] ###################### (2090)
    [0.90] ########## (1036)
    [0.95] ###### (629)

POST-CALIBRATION
    [0.00]  (1)
    [0.05]  (5)
    [0.10] # (58)
    [0.15] ### (138)
    [0.20] ########### (430)
    [0.25] ################# (671)
    [0.30] ##################### (850)
    [0.35] ####################### (902)
    [0.40] ########################## (1010)
    [0.45] ############################## (1161)
    [0.50] ############################# (1153)
    [0.55] ######################## (944)
    [0.60] ################### (765)
    [0.65] ############### (605)
    [0.70] ########### (443)
    [0.75] ###### (266)
    [0.80] ##### (206)
    [0.85] ##### (218)
    [0.90] #### (174)
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
    [0.50]  (0)
    [0.55]  (0)
    [0.60]  (0)
    [0.65] ### (366)
    [0.70] ########### (1154)
    [0.75] ############################## (3029)
    [0.80] ############################# (2986)
    [0.85] ############### (1605)
    [0.90] ##### (582)
    [0.95] ## (278)

POST-CALIBRATION
    [0.00]  (0)
    [0.05]  (6)
    [0.10] ## (90)
    [0.15] ###### (284)
    [0.20] ######## (355)
    [0.25] ######### (382)
    [0.30] ################ (694)
    [0.35] ######################### (1061)
    [0.40] ############################## (1269)
    [0.45] ############################# (1266)
    [0.50] ########################### (1162)
    [0.55] ####################### (975)
    [0.60] ################### (825)
    [0.65] ############ (525)
    [0.70] ######## (345)
    [0.75] ###### (265)
    [0.80] #### (177)
    [0.85] ## (97)
    [0.90] # (83)
    [0.95] ### (139)
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
    [0.30]  (0)
    [0.35]  (0)
    [0.40]  (0)
    [0.45]  (0)
    [0.50]  (18)
    [0.55] ## (171)
    [0.60] ###### (505)
    [0.65] ######### (693)
    [0.70] ################# (1269)
    [0.75] ########################### (2052)
    [0.80] ############################## (2219)
    [0.85] ################### (1444)
    [0.90] ########## (800)
    [0.95] ########### (829)

POST-CALIBRATION
    [0.00]  (14)
    [0.05] # (45)
    [0.10] ### (144)
    [0.15] ###### (278)
    [0.20] ######## (373)
    [0.25] ######### (411)
    [0.30] ############ (532)
    [0.35] ################### (839)
    [0.40] ########################## (1163)
    [0.45] ############################# (1293)
    [0.50] ############################## (1322)
    [0.55] ####################### (1044)
    [0.60] ################## (818)
    [0.65] ############# (575)
    [0.70] ######## (363)
    [0.75] ###### (301)
    [0.80] ########### (485)
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
    [0.40]  (0)
    [0.45]  (0)
    [0.50]  (0)
    [0.55]  (0)
    [0.60]  (0)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (38)
    [0.80]  (198)
    [0.85] # (476)
    [0.90] ## (714)
    [0.95] ############################## (8574)

POST-CALIBRATION
    [0.00] # (454)
    [0.05]  (118)
    [0.10]  (130)
    [0.15]  (114)
    [0.20]  (140)
    [0.25]  (158)
    [0.30]  (222)
    [0.35]  (221)
    [0.40] # (297)
    [0.45] # (449)
    [0.50] # (372)
    [0.55] ############################## (7325)
    [0.60]  (0)
    [0.65]  (0)
    [0.70]  (0)
    [0.75]  (0)
    [0.80]  (0)
    [0.85]  (0)
    [0.90]  (0)
    [0.95]  (0)
```

## Section E — Clamp saturation

Fraction of trait values hitting 0.0 or 1.0 exactly.
- Pre-calibration: 10414/240000 (4.3%)
- Post-calibration: 1528/240000 (0.6%)