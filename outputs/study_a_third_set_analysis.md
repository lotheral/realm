# Study A — Third Event Set: Matrix v2 Verdict (Sprint 27)

> 2026-08-22. Companion to `outputs/study_a_relation_analysis.md` (Sprint
> 24) and `outputs/study_a_analysis.md`. Raw reports:
> `study_a_third_relation_v1.*`, `study_a_third_relation_v2.*`,
> `study_a_third_valence.*`. Protocol: matrix v2 frozen at commits
> `dcc5019` + `cfa8adc`, third set authored AFTER the freeze at commit
> `649e750` under the pre-stated criteria in
> `docs/study_a_third_set_protocol.md` — the freeze-then-author ordering
> is auditable in git history.

## Pre-stated decision rule (written before the runs)

Matrix v2 is promoted to a production option ONLY if third-set
directional accuracy exceeds 50% with one-sided binomial p < 0.1,
abstentions counting as misses.

**The bar was not met. Matrix v2 stays research-only and is NOT wired
into the API.**

## The result

| channel | design (22, in-sample for both) | held-out (8, clean for v1 only) | third set (8, clean for all) |
|---|---|---|---|
| relation v1 | 20/22 (91%) | 4/8 (50%), p=0.637 | **1/8 (12%), p=0.996** |
| relation v2 | 22/22 (100%) | 7/8 (88%) | **3/8 (38%), p=0.855** |
| valence (sim) | 4/22 (18%) | 2/8 (25%) | **5/8 (62%), p=0.363** |

Secondary v2 statistics (reported, not the decision metric): 5/8
committed, 3/5 correct when committed (p=0.5); coverage 62.5%. All
three channels are statistically null on this set at N=8.

## The headline finding: a reproducible generalization gap

Each matrix version scores near-perfectly on every set known at its
authoring time and collapses on the next unseen set:

- v1: 20/22 in-sample → 4/8 on its first clean test.
- v2: 22/22 + 7/8 in-sample → 3/8 on its first clean test.

The pattern replicated across two independent iterations. The apparent
class-level consistency of an authored archetype matrix is largely
**authorial overfitting to known cases**: the author cannot help
encoding the specific surface forms and class boundaries of the events
they have analyzed. The freeze-then-author protocol did exactly its
job, twice, at the cost of one afternoon per iteration.

## Third-set failure modes (v2)

1. **Culpability inversion (structural, the deep one).**
   `oct7_likud_support`: an external attack answered with blame for
   the security failure (Likud 28 → 19 seats), the inverse of the
   Mueller rally prior. `sandy_obama_approval`: a disaster answered
   with (noise-magnitude) approval gain after a praised response —
   the inverse of the disaster→blame prior. Whether the public
   rallies or blames depends on **perceived incumbent culpability and
   response quality**, which is not a function of event type. No
   keyword system sees this; it requires semantic reading of the
   event's attribution structure.
2. **Morphological brittleness.** `saturday_night_massacre_nixon`:
   the summary's natural copy reads "resign in protest"; the
   self_inflicted keyword is "resigns". The correct class existed,
   the prior was correct (−1, observed −3), and the channel still
   abstained on an inflectional suffix.
3. **Class-breadth gap.** `partygate_johnson_favorability`: the v2
   personal_scandal class covers intimate scandals ("affair",
   "under oath"); a conduct/rule-breaking scandal matched nothing and
   abstained (observed −11).
4. **Question-orientation gap.** `three_mile_island_nuclear`: the
   historical poll asks about *favoring building more* nuclear plants
   (hazard-expanding), the mirror of the phase-out phrasing the
   question classifier knows. Unclassified → abstention, despite the
   disaster class firing correctly on the event side.

The three v2 hits (Saddam capture, mobilization, Uvalde) confirm that
the new classes fire where the surface forms cooperate — the problem
is that surface forms cooperating is the exception, not the rule.

## Reading the valence row honestly

5/8 is valence's best cell ever, and it is composition, not skill: in
this set the events where sentiment sign and referent direction
*coincide* (mobilization, Oct 7, TMI — negative event, negative shift;
Sandy's summary carries the praised response) happen to outnumber the
divergent cases. Where they diverge, valence missed as always (Uvalde:
negative event, gun-law support UP; Saddam: positive event parsed
neutral). Two of eight parses were sentiment-neutral (vs 7/8 on the
held-out set), and magnitudes remain uninformative (predicted −26.0 vs
observed −6.0; magnitude ρ = −0.488). p=0.363: null.

## Verdict and what follows

1. **The keyword-classifier + fixed-prior implementation of the
   relation channel is falsified at its second iteration.** A v3 with
   the same technology is NOT recommended: two clean tests show the
   approach's accuracy lives in its author's memory of analyzed cases,
   not in transferable structure.
2. The *idea* behind the channel — reactions follow the semantic
   relation between event and referent — survives, and the third set
   sharpened it: the missing variable is **perceived culpability /
   response quality**, which requires semantic classification (an LLM
   reading the event) rather than richer keyword lists. That path is
   exactly what Study B's full pipeline tests forward, without
   blinding problems.
3. Direction-signal search (per the Sprint 26 calibration roadmap)
   now has one candidate left standing: Study B full-pipeline
   forward results (first scoring ~2026-09-20). Calibration work
   remains blocked until a channel shows direction.
4. Matrix v2 closes the last open queue item from the Sprint 24
   post-roadmap queue. Relation channel: research-only, permanently
   labeled; both matrices and all three event sets remain in the repo
   as a reusable falsification benchmark.
