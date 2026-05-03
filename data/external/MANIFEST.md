# data/external/ — external dataset cache

Raw third-party datasets used by REALM validation scripts. **Files in this
directory are NOT committed to the repo** (see `.gitignore`) because of size
and licensing cleanliness. Use `python scripts/load_bigfive_real.py --download`
to (re)fetch them locally.

## big-five-data.csv

- **Source**: <https://github.com/automoto/big-five-data>
- **Raw URL**: <https://raw.githubusercontent.com/automoto/big-five-data/master/big_five_scores.csv>
- **License**: MIT (repository packaging); psychometric items are public-domain IPIP.
- **Retrieved**: 2026-04-24
- **SHA256**: `c9a3cf2fdca354345136ad50bcd101b6a260b4e864d8cd8fd5b7184aaf6ceaa8`
- **Rows**: 307,313
- **Size**: ~25 MB
- **Schema**: `case_id, country, age, sex, agreeable_score, extraversion_score, openness_score, conscientiousness_score, neuroticism_score`
  - `country` is a **10-character-truncated written name** (e.g. `South Afri`, `Russian Fe`, `Philippine`), NOT an ISO code.
  - `sex`: `1` = male, `2` = female (dataset has no third option).
  - OCEAN scores pre-computed on `[0, 1]` scale from IPIP-NEO-300 responses.
- **Consumers**:
  - `scripts/load_bigfive_real.py` — loader + country mapping + stratified sampler
  - `scripts/validate_bf_study_real.py` — side-by-side synthetic/real validity study
  - `scripts/validate_bf_subgroups.py` — §11 per-country × 7 criteria sub-group matrix

## IPIP120.dat (Johnson 2014 IPIP-NEO-120 item-level responses)

- **Source OSF project**: <https://osf.io/tbmh5/> (child <https://osf.io/wxvth/>)
- **Direct download**: <https://osf.io/download/q9jrh/>
- **License**: Public domain (IPIP items + open-access dataset)
- **Retrieved**: 2026-04-24
- **SHA256**: `526daf7ebe7d480ba71258cd20f0fc3b37ab3a43a2e4191c19a49e185a1df53b`
- **Rows**: 619,150 respondents
- **Size**: ~95 MB (fixed-width ASCII, 151 chars/row)
- **Schema** (see `data/external/DAT120.doc`):
  - 1-6   `CASE`      case id (F6.0)
  - 7     `SEX`       1=M, 2=F
  - 8-9   `AGE`
  - 10-22 timestamp fields (SEC, MIN, HOUR, DAY, MONTH, YEAR)
  - 23-31 `COUNTRY`   9-char name, right-padded
  - 32-151 `I1..I120` item responses 1-5 (0 = missing).
    **Reverse-keyed items pre-reversed** — sum items per facet without recoding.
- **Consumers**:
  - `data/personality/ipip_neo_120_scoring_key.json` — derived scoring key
  - `realm/personality/validation/facet_scorer.py` — item→facet→domain scorer
  - `scripts/validate_facet_derivation.py` — audits BF-derivation facet citations
  - `scripts/draft_facet_coefficients.py` — emits backlog per-facet coefficients draft

## IPIP-NEO-120_Scoring_Tool.xls

- **Source**: <https://osf.io/ycvdk/> file `qza3d`
- **SHA256**: `7e22906e4fc2a696f76d58b7732b67602b7cb1bb828611506dfc9cf9128bb849`
- **Retrieved**: 2026-04-24
- **Purpose**: source for item→facet mapping in
  `data/personality/ipip_neo_120_scoring_key.json`.

## vdem_scores.json (Sprint 14 WP3 — committed)

Unlike the other entries above, this file IS committed to the repo. It is a
small (~6 KB) JSON of curated indicative country-level scores aligned with
the V-Dem v13 (2023) Country-Year dataset rankings. **The values are not raw
CSV extracts** from V-Dem; they are hand-curated representations on the
`[0, 1]` scale that match the directional ordering published by V-Dem (e.g.
Scandinavian countries near the liberal pole, Gulf states / one-party
regimes near the authoritarian pole).

- **Source reference**: <https://v-dem.net/data/the-v-dem-dataset/>
- **License**: V-Dem data is CC-BY 4.0; this curated representation inherits
  that license.
- **Retrieved**: 2026-04-25 (curated — actual extraction script TBD)
- **Schema**: ISO2-keyed mapping → `{libdem, partipdem, polyarchy, eqdr}` ∈ [0, 1]
- **Coverage**: 66 countries (matching `data/hofstede_scores.json`)
- **Consumers**:
  - `realm/demographics/country_data.py:load_vdem` / `get_vdem`
  - `realm/personality/adapters/demographic.py:_political_spectrum_for_country` (60% Hofstede + 40% V-Dem blend)

**Production replacement**: download the V-Dem v13 Country-Year CSV from the
source URL above and run a one-shot extraction script that pulls the latest
year's `v2x_libdem`, `v2x_partipdem`, `v2x_polyarchy`, `v2xeg_eqdr` columns
for each ISO2 in `data/hofstede_scores.json`. The curated values shipped
here are sufficient for the validity ordering (Scandinavia > continental EU
> Latin America > MENA / one-party) the v0.14.0 article relies on.

## Citation

When reporting on this data, cite both the packaged repo and the underlying
IPIP project:

> automoto (2021). big-five-data: Pre-computed Big Five personality scores
> derived from IPIP-NEO-300 responses. <https://github.com/automoto/big-five-data>
>
> IPIP (ipip.ori.org). International Personality Item Pool: A Scientific
> Collaboratory for the Development of Advanced Measures of Personality
> Traits and Other Individual Differences.
