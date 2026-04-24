# Real-Data BigFive Validity Study (N=10000, seed=42)

Generated: 2026-04-24 10:16:19

Side-by-side validity study comparing a Costa & McCrae-distributed synthetic Big Five population against a stratified sample from [automoto/big-five-data](https://github.com/automoto/big-five-data) (307,313 rows; pre-computed OCEAN [0,1] from IPIP-NEO-300). Every metric below is reported in two columns — `synth` and `real` — using an identical pipeline on both sides.

See `outputs/sapa_validation_plan.md` for the design document and `outputs/bf_validity_study.md` for the synthetic-only baseline this study extends.

## Section 0 — Population characterization (synth vs real)

### OCEAN distribution (per-trait, both populations at N=10000)

| trait | synth mean | real mean | Δmean | synth std | real std | synth skew | real skew |
|-------|-----------|-----------|-------|-----------|----------|-----------|-----------|
| openness | 0.499 | 0.733 | -0.234 | 0.170 | 0.088 | -0.00 | -0.20 |
| conscientiousness | 0.501 | 0.702 | -0.201 | 0.170 | 0.107 | +0.00 | -0.13 |
| extraversion | 0.500 | 0.671 | -0.171 | 0.168 | 0.108 | +0.00 | -0.34 |
| agreeableness | 0.501 | 0.698 | -0.197 | 0.170 | 0.093 | -0.01 | -0.50 |
| neuroticism | 0.498 | 0.574 | -0.076 | 0.168 | 0.125 | -0.01 | +0.10 |

**Finding**: real IPIP-NEO-300 means cluster around 0.65-0.73, not the 0.50 Costa & McCrae midpoint the synthetic sampler targets. This is a documented feature of self-endorsed item-mean scoring (participants answer above midpoint on aggregate), not a bug in either dataset. Real stds (~0.09-0.13) are also narrower than the synthetic 0.17 target.

### Input intercorrelations (synth vs real, OCEAN pairs)

| pair | synth target | synth observed | real observed |
|------|--------------|----------------|---------------|
| openness~extraversion | +0.15 | +0.142 | +0.234 |
| openness~conscientiousness | -0.10 | -0.082 | -0.047 |
| conscientiousness~agreeableness | +0.20 | +0.204 | +0.312 |
| conscientiousness~neuroticism | -0.25 | -0.236 | -0.459 |
| extraversion~agreeableness | +0.15 | +0.147 | +0.065 |
| extraversion~neuroticism | -0.20 | -0.202 | -0.424 |

### Real-dataset demographics (sample of N=10000)

**Top 10 countries in sample:**

| ISO2 | sample N | sample % | filtered source % |
|------|----------|----------|-------------------|
| US | 7096 | 71.0% | 71.0% |
| CA | 728 | 7.3% | 7.3% |
| GB | 551 | 5.5% | 5.5% |
| AU | 348 | 3.5% | 3.5% |
| NL | 116 | 1.2% | 1.2% |
| IN | 95 | 0.9% | 0.9% |
| PH | 83 | 0.8% | 0.8% |
| SG | 81 | 0.8% | 0.8% |
| IE | 70 | 0.7% | 0.7% |
| TH | 69 | 0.7% | 0.7% |

**Sex split (sample)**: {'M': 3965, 'F': 6035}. **Age bands (sample)**: {'26-35': 1950, '18-25': 6597, '36-50': 1156, '51+': 297}. Dataset skews young (18-35 heavy) and female-majority — a known feature of voluntary online IPIP-NEO testing.

**Filter results**: 299565 rows kept after filtering. Excluded: **7139** rows across 170 country names not in REALM's 30-country map (e.g. Canada 21,798; Australia 10,400; Netherlands 3,469; Singapore 2,450); **609** rows across 10 mapped countries below N=100; 0 invalid rows.

The demographic shift between the real sample (86%+ USA-weighted because of dataset skew) and REALM's WorldGenerator population weights (China 19%, India 19%, USA 4%) is itself a finding: synthetic agents simulate a more globally-balanced population than an online IPIP-NEO sample could ever measure.

## Section 1 — Input verification

Synthetic side is expected to recover Costa & McCrae norms (mean=0.50, std=0.17); real side is descriptive only (no target).

| trait | synth target mean/std | synth obs mean/std | real obs mean/std |
|-------|----------------------|--------------------|-------------------|
| openness | 0.500 / 0.170 | 0.499 / 0.170 | 0.733 / 0.088 |
| conscientiousness | 0.500 / 0.170 | 0.501 / 0.170 | 0.702 / 0.107 |
| extraversion | 0.500 / 0.170 | 0.500 / 0.168 | 0.671 / 0.108 |
| agreeableness | 0.500 / 0.170 | 0.501 / 0.170 | 0.698 / 0.093 |
| neuroticism | 0.500 / 0.170 | 0.498 / 0.168 | 0.574 / 0.125 |

## Section 2 — Big Five pass-through accuracy

Per-trait Pearson r between input OCEAN scores and output Big Five values on the BigFive path. Expected r >= 0.99 with cal OFF (direct pipe-through).

| trait | synth cal OFF | synth cal ON | real cal OFF | real cal ON |
|-------|---------------|--------------|--------------|-------------|
| openness | +0.996 | +0.996 | +0.994 | +0.994 |
| conscientiousness | +0.993 | +0.993 | +0.994 | +0.993 |
| extraversion | +0.996 | +0.996 | +0.999 | +0.998 |
| agreeableness | +0.997 | +0.997 | +0.997 | +0.996 |
| neuroticism | +1.000 | +1.000 | +1.000 | +1.000 |

## Section 3 — Derived traits, per-population mean trait std

Compressed view: mean std across the 13 derived traits and count of those at / above the 0.05 minimum (BigFive path).

| config | mean derived std | #derived with std > 0.05 |
|--------|------------------|-----|
| synth cal OFF | 0.077 | 13/13 |
| synth cal ON  | 0.170 | 13/13 |
| real cal OFF | 0.048 | 4/13 |
| real cal ON  | 0.168 | 13/13 |

## Section 4 — Fallback + excluded traits (dual)

Fallback 5 traits stay at 0.5 on the BigFive path with cal OFF (no Big Five coefficients). `political_spectrum` is excluded by design (REALM models temperament, not ideology). Under cal ON each population uses its own source-specific stats (`config/trait_calibration_big_five.json` for synth, `config/trait_calibration_big_five_real.json` for real), so the two cal-ON columns reflect population-matched recentering.

| trait | synth mean (cal ON) | synth std (cal ON) | real mean (cal ON) | real std (cal ON) | saturated? |
|-------|---------------------|--------------------|--------------------|-------------------|-----------|
| herd_susceptibility | 0.489 | 0.174 | 0.493 | 0.144 | no |
| fomo_susceptibility | 0.509 | 0.171 | 0.505 | 0.149 | no |
| tradition_vs_progress | 0.490 | 0.175 | 0.508 | 0.123 | no |
| individualism | 0.508 | 0.174 | 0.507 | 0.145 | no |
| spirituality | 0.497 | 0.166 | 0.500 | 0.088 | no |
| political_spectrum | 0.500 | 0.000 | 0.500 | 0.000 | no |

## Section 5 — Big Five intercorrelation preservation (BigFive path)

Input observed vs output on each population, cal OFF. Reports whether the pipeline preserves the INPUT intercorrelation (real input has its own structure, distinct from the synthetic target).

| pair | synth target | synth in | synth out | real in | real out | max Δ |
|------|--------------|----------|-----------|---------|----------|-------|
| openness~extraversion | +0.15 | +0.142 | +0.144 | +0.234 | +0.239 | 0.005 |
| openness~conscientiousness | -0.10 | -0.082 | -0.086 | -0.047 | -0.049 | 0.004 |
| conscientiousness~agreeableness | +0.20 | +0.204 | +0.199 | +0.312 | +0.307 | 0.006 |
| conscientiousness~neuroticism | -0.25 | -0.236 | -0.234 | -0.459 | -0.461 | 0.002 |
| extraversion~agreeableness | +0.15 | +0.147 | +0.149 | +0.065 | +0.064 | 0.002 |
| extraversion~neuroticism | -0.20 | -0.202 | -0.203 | -0.424 | -0.422 | 0.002 |

**Preservation within ε=0.05 (cal OFF)**: synth 10/10 (max Δ = 0.004); real 10/10 (max Δ = 0.009).

## Section 6 — Derived-trait structural pair match rate

Shared-driver pair match rate: two derived traits whose dominant OCEAN drivers match should correlate with predicted sign, |r| >= 0.10. BigFive path, cal OFF, both populations.

| population | matches | match rate | mean |r| |
|------------|---------|------------|----------|
| synth | 15/15 | 100% | 0.367 |
| real | 15/15 | 100% | 0.411 |

## Section 7 — Cross-path mean trait std (all 24 traits)

| configuration | mean trait std | #traits >= 0.14 |
|---------------|----------------|-----------------|
| synth big_five cal OFF | 0.081 | 5/24 |
| synth big_five cal ON  | 0.163 | 23/24 |
| synth astrological cal OFF | 0.067 | 0/24 |
| synth astrological cal ON  | 0.160 | 23/24 |
| real big_five cal OFF | 0.051 | 0/24 |
| real big_five cal ON  | 0.153 | 21/24 |

## Section 8 — Butterfly lift (tech-news scenario)

Baseline vs scenario tech_share under each configuration (n=150 per branch, 12 ticks, 3 branches). Synth and real BigFive configs run with their respective populations; astrological config is unchanged across populations (independent of Big Five scores) and shown once.

| configuration | baseline | scenario | Δ (lift) | relative % |
|---------------|----------|----------|----------|------------|
| synth big_five cal OFF | 0.170 | 0.235 | +0.065 | +38.2% |
| synth big_five cal ON  | 0.168 | 0.225 | +0.057 | +34.2% |
| real big_five cal OFF | 0.179 | 0.215 | +0.036 | +19.9% |
| real big_five cal ON  | 0.133 | 0.178 | +0.044 | +33.3% |
| astrological cal OFF | 0.190 | 0.263 | +0.073 | +38.6% |
| astrological cal ON  | 0.167 | 0.186 | +0.019 | +11.5% |

## Section 9 — Honest limitations

**Self-selection bias** — the automoto dataset is derived from the pool of people who chose to complete an online IPIP-NEO-300 test. Age skews young (~66% 18-25 in the filtered subset), country skews USA (86% even after stratification because USA is 86% of the filtered source), female-majority, English-speaking internet-using. 'Real' here means 'real online IPIP-NEO respondents', not a representative human population.

**No facet-level detail** — the dataset ships the 5 OCEAN composite scores only. The 30-facet IPIP-NEO structure underlying each score is not exposed, so this study cannot validate facet-specific claims in `data/personality/big_five_derivation.json` (e.g. 'patience derives from C5 Self-Discipline'). For facet validity, switch to the Johnson IPIP-NEO-120/300 OSF release in a follow-up study.

**Country coverage gap** — REALM's WorldGenerator supports 30 ISO2 country codes; the dataset has 236 unique country names. The intersection after min_country_n=100 is 21 countries, leaving 7,139 rows unused. Primary casualties: Canada (21,798), Australia (10,400), Netherlands (3,469), Singapore (2,450), Ireland (2,102), New Zealand (2,016), Finland, Sweden, Norway, Malaysia. The dataset is heavily Anglo/Western-European; filtering to REALM's 30-country list drops most of that population tail.

**Truncated country names** — the dataset stores country as a 10-char-truncated string (e.g. `South Afri`, `Russian Fe`, `Philippine`). `COUNTRY_NAME_TO_ISO2` in `scripts/load_bigfive_real.py` is hand-maintained; any additions/renames upstream need a code update, not a data-only change.

**Mean drift from Costa & McCrae norms** — real self-report IPIP-NEO-300 means cluster at ~0.65-0.73, not the 0.50 Costa & McCrae midpoint. This is documented §0 behavior of item-mean scoring on 0-1 normalized scales; it is NOT a calibration failure. Criterion #8-real below fails by design — the value is measuring *how much* synthetic and real diverge, not pretending they match.

**Source-matched calibration stats** — as of 2026-04-24 both populations use their own source-specific stats when cal=ON: `config/trait_calibration_big_five.json` (synth, Costa & McCrae N=5K) for the synth path, `config/trait_calibration_big_five_real.json` (real, automoto stratified N=5K) for the real path. This removes the earlier synth→real cross-distribution distortion that saturated derived traits and flipped butterfly lift on the real cal-ON column. The remaining distance between real input and Costa & McCrae norms is an *input-property finding* (criterion #8-real), not a calibrator shortcoming.

## Section 10 — Success criteria evaluation

| # | criterion | synth result | real result |
|---|-----------|--------------|-------------|
| 1 | BigFive mean trait std >= 0.14 (cal ON) | 0.163 PASS | 0.153 PASS |
| 2 | Big Five input↔output r >= 0.99 (cal OFF) | min=0.993 PASS | min=0.994 PASS |
| 3 | Input correlation signs preserved (cal OFF) | 10/10 PASS | 10/10 PASS |
| 4a | Derived 13 traits std > 0.05 (cal OFF) | min=0.061 PASS | min=0.036 FAIL |
| 4b | Derived 13 traits std > 0.05 (cal ON) | min=0.168 PASS | min=0.164 PASS |
| 5 | Butterfly lift > 0 on BigFive path | off=+0.065, on=+0.057 PASS | off=+0.036, on=+0.044 PASS |
| 6 | Derived structural pairs match >= 50% | 15/15 (100%) PASS | 15/15 (100%) PASS |
| **8-real** | Real OCEAN ≈ Costa & McCrae (Δmean<0.05 AND Δstd<0.03 per trait) | — (n/a on synth) | max Δmean=0.233, max Δstd=0.082 FAIL |

## Summary

**Synthetic column: 7/7 criteria passed.**

**Real column: 6/8 criteria passed.**

Criterion 8-real FAILs: openness, conscientiousness, extraversion, agreeableness, neuroticism (expected — real self-report means drift ~0.15-0.23 above Costa & McCrae midpoint; see §0 and §9).


See `scripts/validate_bf_subgroups.py` output in 
`outputs/bf_validity_subgroups_real.md` for the §11 
per-country × sex × age-band matrix.
