# Real-Population Big Five Validation Plan

## Context

The synthetic Big Five validity study (`outputs/bf_validity_study.md`, 2026-04-24)
proved BigFiveAdapter behaves correctly on a Costa & McCrae-distributed synthetic
population with 6 literature-documented intercorrelation pairs (7/7 success
criteria PASS after the adapter-aware calibrator shipped). The next maturity
step is to repeat the same study against a **real human Big Five population**.

If the real-data study reproduces the synthetic study's pass rate (or surfaces
honest gaps), REALM has a defensible "tested on real personality data" claim
for the BigFive path that is independent of any astrological assumption.

## Dataset comparison

| Source | N | OCEAN format | Demographics | License | Pre-processing needed |
|---|---|---|---|---|---|
| **automoto/big-five-data** ([GitHub](https://github.com/automoto/big-five-data)) | 307,313 | **Pre-computed normalized [0,1]** per O/C/E/A/N | age, sex (1=M,2=F), country | **MIT** (commercial OK) | None — drop-in |
| OpenPsychometrics IPIP-FFM-data-8Nov2018 | 1,015,342 | 50 raw Likert items | age, gender, country (+race, native_language) | Public domain (no explicit text license) | Item-to-trait composite (sum/normalize per IPIP scoring rules) |
| OpenPsychometrics BIG5 | 19,719 | 50 raw Likert items | gender, age, race, native_language, country | Public domain | Same as above |
| Johnson IPIP-NEO OSF ([osf.io/tbmh5](https://osf.io/tbmh5/)) | 947,456 (combined IPIP-NEO-120 + 300) | Items + 30 facets | International demographics | Public domain | Aggregation from items; richest psychometric depth |
| SAPA Project ([personality-project.org](https://personality-project.org/sapa/)) | ~24,000 | Matrix-sampled items (most participants don't see all items) | Limited | Free with citation | Heavy: matrix sampling means imputation needed |

## Selected dataset: automoto/big-five-data

**Why this one:**
1. **Pre-computed OCEAN scores in [0,1]** — drops directly into `BigFiveAdapter.build()` with no scoring code. Same scale (0..1) the synthetic sampler uses.
2. **MIT license** — explicit, broad, commercial-safe (matters for B2B pitch).
3. **Demographics (age, sex, country)** — directly maps to three required DemographicProfile fields.
4. **N=307,313** — 30× the validity-study N; can sample subsets stratified by country for fairness.
5. **Already cleaned** — invalid responses filtered before scores were computed (per repo README).
6. **Derived from IPIP-NEO-300** — the gold standard for Big Five measurement; psychometrically validated foundation.

**Why not the others:**
- **OpenPsychometrics IPIP-FFM** (1M+ N) is the volume backup if automoto turns out to have hidden caveats, but requires implementing IPIP scoring (sum 10 items per trait, reverse-key the negatively-worded ones, normalize) — extra ~50-line scoring module. License less crisp ("public domain" stated by the site but no LICENSE file).
- **SAPA project** matrix-sampling means each participant has missing items for traits — needs imputation strategy, complicates "real distribution" claim.
- **Johnson IPIP-NEO OSF** is the gold standard psychometrically (30 facets + 5 domains) but heaviest data engineering. Worth holding for a follow-up validity study that wants facet-level detail.

## Pipeline design

### File: `scripts/load_bigfive_real.py`

```
download → cache to data/external/big-five-data.csv
load_real_population(
    n: int = 10000,
    seed: int = 42,
    min_country_n: int = 100,
    stratify_by: tuple[str, ...] = ("country", "sex"),
) -> list[DemographicProfile]
```

Steps:
1. **Download**: from `https://raw.githubusercontent.com/automoto/big-five-data/master/<filename>.csv` to `data/external/`. Skip if cached. Document SHA256 in a manifest file.
2. **Filter**: drop rows with NaN OCEAN, unknown country, or countries below `min_country_n` (default 100 per Loth's 2026-04-24 decision).
3. **Stratified sample**: group by `country × sex`, compute each cell's proportion of the filtered dataset, draw seeded samples from each cell proportionally to hit the target N=10000 (rounded). Guarantees each (country, sex) cell present in the final sample at its filtered-dataset frequency.
4. **Map to DemographicProfile**: this is the friction point — the dataset has only (age, sex, country, OCEAN). REALM's `DemographicProfile` needs 17 fields. Two options:
   - **Hybrid (recommended)**: For each real row, generate a synthetic `DemographicProfile` via `WorldGenerator` restricted to the same country, then override `(age_years, gender, big_five_scores)` with real values via `dataclasses.replace`. Birth datetime synthesized from age + city-level birth-hour distribution. Profession/income/education sampled from country-tier defaults.
   - **Strict**: Fill non-essential fields with placeholders. Cleaner provenance, but breaks any pipeline that uses `birth_datetime` or `profession_code` for downstream behavior. Astrological path would crash without birth datetime, but BigFive path doesn't need it.
   - **Decision**: Hybrid. The validity study runs the BigFive adapter (doesn't need birth_datetime astrologically), but downstream butterfly may use `country` for network topology and other modifiers. Hybrid keeps everything operational.
5. **Country format**: dataset uses ISO codes; verify ISO2 vs ISO3. If ISO3, add a 3→2 mapping table. REALM's `WorldGenerator` keys on ISO2.
6. **Sex mapping**: 1→"M", 2→"F", missing→sample 49/49/2 default.

### File: `scripts/validate_bf_study_real.py`

Mirror of `scripts/validate_bf_study.py` with two changes:
- **Population source**: replaces `build_bf_profiles` with `load_real_population`. The downstream pipeline (run through BigFiveAdapter, calibration off/on, butterfly comparison) is identical.
- **New §0 "Real vs synthetic input distribution"**: per-trait mean/std/skew of real input vs Costa & McCrae targets. Per-pair input intercorrelations vs the 6 literature pairs in `DEFAULT_CORRELATIONS`. Documents how the real population differs from the synthetic baseline.

Output: `outputs/bf_validity_study_real.md`.

## Methodology — what the report measures

Same 10-section structure as `outputs/bf_validity_study.md`, plus:

- **§0 Side-by-side population characterization**: synthetic 10K vs real 10K. Per-trait mean / std / skew / kurtosis for each. Real OCEAN intercorrelation matrix (5×5) vs the synthetic 6-pair target. Dataset demographics: age histogram + median, country distribution top 10 with %, sex split. Explicit note on dataset skew (young, Western, internet-tested). Also reports the demographic shift between the real 10K and REALM's `WorldGenerator` population-weighted baseline (which is the distribution the synthetic study's WorldGenerator-demographics side used).

- **§1–§9 same structure as synthetic study, each metric reported in both columns (synthetic / real)**: pass-through, derived traits, fallback handling, intercorrelation preservation, structural pairs, cross-path comparison, butterfly lift, honest limitations.

- **§10 success criteria evaluation** with two result columns (synthetic / real): same 7 criteria as the synthetic study — where the synthetic study passed 7/7, how many does the real population pass? Plus 1 new criterion specific to real-data:
  - **§10 #8-real**: Real input OCEAN intercorrelation matrix matches BigFive output (cal OFF) within ε=0.05 per pair. Tests that the pipeline doesn't *introduce* spurious correlations beyond what's in the input.

- **§11 stratified sub-group matrix** (new, see above): top-10-countries × 7 criteria, plus sex and age-band breakdowns. Informational.

## Decisions made 2026-04-24

Loth settled the four open questions with concrete choices:

1. **Country coverage: filter countries with ≥100 participants.** Smaller-N countries generate noise; the threshold keeps per-country stratification (see below) statistically meaningful. Expected to drop the long tail of rare country codes and "ZZ/unknown" entries without a remap table.
2. **Age range: accept the skew, document as limitation.** The automoto dataset skews young/Western/internet-using — that's the nature of voluntary online IPIP-NEO testing. Self-selection bias is already a declared risk; age skew falls under it. No filter, no remap; §0 reports age histogram + mean/median explicitly alongside the note.
3. **Stratified sample N=10,000**: sample from filtered dataset, **stratified by country × sex proportional to their joint distribution in the filtered data**. Matches the synthetic study's N for direct comparability. Uses dataset-proportional weights (not REALM's population weights); the demographic shift from "real country weights" vs "REALM WorldGenerator weights" is itself a §0 observation.
4. **Side-by-side synthetic vs real.** Single report with two population columns. Every per-trait metric, every intercorrelation pair, every butterfly lift, every success criterion is reported once for the synthetic 10K and once for the real 10K. This answers the most important question the synthetic study couldn't: *how close is our Costa & McCrae synthetic sampler to actual humans?*

## Stratified sub-group analysis (new value-add)

Beyond the aggregate 10K × 10K comparison, the real dataset enables analyses the synthetic study structurally cannot do. Loth flagged this as a key differentiator.

**Analysis dimensions:**
- **Per-country** (top 10 countries by N in the filtered dataset): run the 7-criterion validity check per country. Does the pipeline pass uniformly across cultures, or does some country (e.g. small-sample outliers) fail criterion 3 or 6?
- **Per-sex** (M vs F): does BigFiveAdapter produce different butterfly lift by sex? Different intercorrelation preservation?
- **Per-age-band** (18–25 / 26–35 / 36–50 / 51+): same battery. Expect underrepresentation of 51+; report N per band up front.

**Report section** (§11, new): a compact matrix of `subgroup × {7 criteria}` showing PASS / FAIL per cell. Plus highlight bullets for the most interesting sub-group deviations. This is pure empirical measurement — the synthetic study cannot produce this because its population is homogeneous by construction.

**Success bar for §11**: informational, not gating. Any criterion failing in a specific sub-group is documented, not treated as overall project failure. The value is in knowing *where* the pipeline is weakest, not in a single pass/fail.

## Risks / honest framing

- **The dataset is self-selected** (people who voluntarily took an online IPIP-NEO test). Demographics skew Western, English-speaking, internet-using, and younger (18–35 heavy). Calling this "the real population" overstates — it's "real online-tested individuals in the automoto snapshot". Frame accordingly, and report age histogram + country top-10 + sex split explicitly in §0.
- **Small-country noise filtered, not imputed.** Countries below 100 participants are excluded — their inclusion would inject high-variance per-country estimates that the §11 sub-group analysis cannot interpret fairly. Document the set of excluded countries in §0 so the reader sees which populations are missing from the study.
- **No facet-level detail** — only 5 OCEAN composite scores, no NEO-PI-R facets. The validity study can confirm OCEAN-level pass-through but cannot validate the derivation table's facet-grounded coefficients (e.g. "patience derives from C5 Self-Discipline"). For facet validation, switch to the IPIP-NEO OSF dataset in a follow-up.
- **MIT license is on the GitHub repo packaging**, not on the underlying psychometric items (those are public-domain IPIP). Cite both sources in the report.
- **Validation against this dataset only**. A single dataset doesn't prove generalization. Plan a second validation pass against OpenPsychometrics IPIP-FFM-data-8Nov2018 (different scoring, different sample) as a robustness check.

## Deliverables (next session)

1. `scripts/load_bigfive_real.py` — downloader + loader with caching, country mapping, hybrid profile builder, country × sex stratified sampler (`min_country_n=100`).
2. `scripts/validate_bf_study_real.py` — mirror of synthetic validity script, side-by-side synthetic/real columns throughout. Runs both 10K populations through the same 4 pipeline configurations.
3. `scripts/validate_bf_subgroups.py` (or merged into #2) — §11 stratified analysis: top-10-countries × 7 criteria matrix + sex and age-band breakdowns.
4. `data/external/big-five-data.csv` (cached) + a `data/external/MANIFEST.md` recording source URL + SHA256 + license + retrieval date.
5. `outputs/bf_validity_study_real.md` — final report with synthetic/real side-by-side and §11 sub-group matrix.

## Out of scope

- Implementing IPIP-FFM scoring code (only needed if the automoto dataset turns out to have hidden problems we discover during loader build).
- Facet-level validity (requires Johnson IPIP-NEO OSF — separate study).
- Cross-cultural / measurement invariance analysis (separate research question).
- Re-fitting calibration stats from real data — the existing `config/trait_calibration_big_five.json` was built from the synthetic Costa & McCrae sampler, which matches the population mean/std targets exactly. If real data shows substantially different stats, we may want to regenerate, but that's a follow-up decision after measuring.

## Sources

- [openpsychologydata.metajnl.com — Selected personality data from the SAPA-Project (Condon & Revelle, 2015)](https://openpsychologydata.metajnl.com/articles/10.5334/jopd.al)
- [SAPA project home — personality-project.org/sapa](https://personality-project.org/sapa/)
- [OpenPsychometrics raw data index](http://openpsychometrics.org/_rawdata/)
- [GitHub: automoto/big-five-data — pre-computed OCEAN scores from IPIP-NEO-300, MIT license](https://github.com/automoto/big-five-data)
- [Johnson IPIP-NEO data repository on OSF](https://osf.io/tbmh5/)
- [IPIP project home — public-domain personality items](https://ipip.ori.org/)
- [Wikipedia — Synthetic Aperture Personality Assessment](https://en.wikipedia.org/wiki/Synthetic_Aperture_Personality_Assessment)
