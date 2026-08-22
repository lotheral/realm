# Study A Third Event Set — Pre-Stated Protocol (Sprint 27)

> Written and committed TOGETHER WITH matrix v2
> (`realm/validation/relation_v2.py`), BEFORE any third-set event was
> authored. The freeze-then-author ordering is auditable in git
> history, exactly as with the Sprint 24 v1 freeze (f2df2de).

## Why a third set

Matrix v2 was authored from the design-set and held-out failure
analysis, so results on BOTH of those sets are in-sample for v2.
Re-testing v2 on the Sprint 24 held-out set would re-create the
in-sample problem one level up. Only a new, yet-unauthored event set
can test v2 cleanly.

## Pre-stated decision rule

Identical to the Sprint 24 bar, applied to the third set:

- Matrix v2 is promoted to a production option ONLY if third-set
  directional accuracy exceeds 50% with one-sided binomial p < 0.1.
- **Abstentions (polarity 0) count as misses.** Coverage is part of
  the claim.
- Matrix v1 and the valence channel are run on the same set as
  comparison rows; they carry no promotion decision (v1 already failed
  its bar; valence is falsified).
- Secondary statistics (coverage, precision-when-committed) are
  reported but are NOT the decision metric.

## Event selection criteria (pre-stated)

1. **Size:** target N = 10; 8–12 acceptable.
2. **Disjointness:** no event may be the same real-world event as any
   of the 30 events already used (22 design + 8 held-out), regardless
   of question or poll series. A distinct event inside the same broader
   conflict is allowed only if separated by ≥ 3 months from the used
   event.
3. **Verification:** every event requires a named pollster/series and
   numeric before/after values confirmed via web sources at authoring
   time (`verified: true` only with a verification note naming the
   source). Candidates that cannot be verified are dropped and logged.
4. **Window:** before/after poll readings within ~8 weeks of the
   event; exceptions must be documented in the event's notes.
5. **Class coverage quotas:** at least 2 events targeting v2-new
   archetypes (military success, personal scandal, incumbent conquest
   / self-authored operations, public-health emergency), at least 2
   targeting v1 archetypes, and at least 1 plausible hard case chosen
   for data quality — explicitly NOT for its expected prediction.
6. **No outcome-based selection:** no candidate may be dropped because
   of the prediction the matrix would make for it. Drops happen only
   for verification/window/disjointness failures, and every dropped
   candidate is logged with its reason in the dataset's `_comment` or
   notes.
7. **Natural copy:** event summaries are written as natural news copy,
   NOT engineered toward (or away from) the classifier's keyword
   rules.

## Candidate pool (named before verification)

Listed here so that inclusion/exclusion is determined by the criteria
above, not by post-hoc choice. Verification may kill any of these;
replacements must satisfy the same criteria and be logged.

- Capture of Saddam Hussein (2003-12) — Bush approval (military_success)
- Partygate revelations (2021-12/2022-01) — Johnson approval (personal_scandal)
- Saturday Night Massacre (1973-10) — Nixon approval (self_inflicted/scandal)
- Russia partial mobilization (2022-09) — Putin approval, Levada (self_inflicted)
- Russia full-scale invasion (2022-02) — Putin approval, Levada (acting-side rally)
- Uvalde school shooting (2022-05) — stricter gun laws support (hazard_policy)
- UK COVID first lockdown window (2020-03/04) — GfK consumer confidence (public_health_emergency × confidence)
- October 7 attack (2023-10) — Netanyahu approval/suitability (hard case: attack + blame-for-failure)
- Three Mile Island (1979-03) — nuclear power support (disaster × hazard_policy)
- Killing of al-Baghdadi (2019-10) — Trump approval (military_success, plausible polarized-era null: hard case)
- Poland Constitutional Tribunal abortion ruling (2020-10) — support for legal abortion (rights_threat)
- Hurricane Sandy (2012-10) — Obama approval (disaster; election-window contamination risk noted)

## Run parameters

Valence rows use the standard official parameters (n_agents=100,
n_ticks=30, n_branches=5, seed=42), `sim_delta_isolated` regime for
all third-set events. Relation rows are analytic (no simulation);
`--matrix-version` selects v1 vs v2.
