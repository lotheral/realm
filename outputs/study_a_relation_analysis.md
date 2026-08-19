# Study A — Relation Channel vs Valence Channel (Sprint 24)

> 2026-08-19. Companion to `outputs/study_a_analysis.md`. Raw reports:
> `study_a_results.md` (valence@design), `study_a_holdout_valence.md`,
> `study_a_design_relation.md`, `study_a_holdout_relation.md`.
> Relation matrix frozen at commit `f2df2de` BEFORE the held-out set was
> authored; the held-out set (8 events, all verified, disjoint) is the
> only clean cell for the relation channel.

## Pre-stated decision rule

Written before the held-out runs: the relation channel is promoted to a
production option ONLY if held-out directional accuracy exceeds 50% with
one-sided binomial p < 0.1. **The bar was not met → the channel stays
research-only and is NOT wired into the API.**

## The 2×2 result

| | design set (22 events) | held-out set (8 events) |
|---|---|---|
| **valence** (simulated, blinded) | 4/22 (18%), p=1.000 | 2/8 (25%), p=0.965 |
| **relation** (analytic, frozen matrix) | 20/22 (91%), p≈6e-5 — **IN-SAMPLE at class level** | **4/8 (50%), p=0.637** |

Secondary relation@held-out statistics (reported, not the decision
metric): 3/8 abstentions (polarity 0 for pairs outside the matrix);
among the 5 committed predictions, 4/5 correct (p=0.19). Coverage 62.5%,
precision-when-committed 80% — suggestive, far from significant at N=5.

## Reading the cells honestly

- **relation@design 20/22 is NOT evidence.** The matrix was written by
  the same author who had just analyzed those 22 events' failure
  classes. It demonstrates only that the classes are internally
  consistent — the definition of in-sample.
- **relation@held-out 4/8 is the evidence, and it is null.** The four
  misses are informative: two abstentions on archetypes the matrix
  lacks (military success/bin Laden was caught only by an incidental
  "attacks" keyword; incumbent-initiated conquest/Crimea and a personal
  scandal/Lewinsky had no class), one compound event mis-signed
  (Afghanistan: an external attack inside a self-authored withdrawal —
  the attack keyword won, the blame dynamic ruled reality), and one
  abstention from vocabulary (COVID emergency text hit no
  economic-shock keyword).
- **valence@held-out replicates the design-set failure** (2/8, and 7 of
  8 predictions are |≤0.6pp| neutral-parse residue — both "hits" are
  sign coincidences at noise magnitude, which we flag rather than
  claim). Valence cells were corrected 2026-08-20 after the Sprint 25
  category-routing blinding fix (see `outputs/study_a_analysis.md`
  erratum); the original contaminated runs reported 6/22 and 3/8. The
  relation channel is analytic (no router, no simulation) and is
  unaffected by the leak.

## Conclusions

1. Structured referent-relations clearly outperform valence *on the
   classes they cover* — but coverage and compound-event handling are
   exactly where the honest test failed. A matrix v2 (victory class,
   actor-attribution for self-authored operations, richer economic
   vocabulary) is plausible, and MUST be evaluated on a third,
   yet-unauthored event set; re-testing v2 on this held-out set would
   re-create the in-sample problem one level up.
2. The production posture stands: heuristic scenario deltas are
   event-valence propagation (labeled so in the dashboard); the LLM
   scenario analyzer remains the semantic channel; its evidence
   accumulates in Study B (forward diary), where blinding is not
   needed because the outcomes do not exist yet.
3. Methodological note for the article/appendix: the freeze-then-author
   protocol (matrix commit `f2df2de` precedes the held-out file's first
   commit in git history) is auditable in the repository — the claim
   "held-out" is checkable, not taken on trust.
