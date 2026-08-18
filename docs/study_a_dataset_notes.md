# Study A Dataset — Selection Criteria, Sourcing, and Caveats

> Sprint 22 (2026-08-18). Companion to `data/validation/study_a_events.json`.
> Design: `docs/superpowers/specs/2026-08-18-reaction-distribution-repositioning-design.md` §4.1.

## Selection criteria

1. **Documented before/after opinion measurement** for a defined national
   population, from a named polling organization or index, bracketing a
   single identifiable event.
2. **Tight windows** where possible (days to ~2 months) so the shift is
   attributable to the event rather than slow drift.
3. **Mechanism diversity — deliberately adversarial to the current model.**
   Four families, tagged in the dataset:
   - `rally` (9 events): negative event → leader approval RISES
     (rally-round-the-flag). A sentiment-sign mechanism is expected to
     get these WRONG. Including them is the point: the study measures the
     mechanism REALM has, not the mechanism that would look best.
   - `approval_drop` (5): negative event → approval falls (aligned).
   - `policy_shift` (6): event moves support for a policy; includes
     threat-to-status-quo cases (Dobbs leak, Sandy Hook) where support
     for the questioned subject rises after a negative event about it.
   - `confidence_index` (2): economic shock → consumer sentiment index
     falls (aligned; metric is index points, not pp — magnitude
     comparisons use rank correlation, so this is acceptable and
     disclosed).
4. **Population expressible as a PopulationSpec** — country-scoped
   (US/GB/DE/FR/TR/FI/SE). Events whose natural population is not
   modelable (e.g. "EU27 residents" spanning membership) were excluded.
5. **No outcome leakage:** `event_summary` is written as dated news copy
   and must not mention polls, surveys, or approval ratings (enforced by
   `TestRealDataset::test_no_outcome_leakage_in_summaries`).

## Honesty envelope

- All numbers were authored from model (training-data) knowledge and are
  **candidates until `verified: true`** with a `verification_note`.
- `confidence` is *authorship* confidence in the numeric values —
  high/medium/low — NOT poll quality. The harness reports every metric
  broken down by confidence tier and by verified flag; the low/med/high
  ratio is a first-class output (per the project's low-confidence
  authorship-tracking rule).
- Known systematic caveats:
  - French, Turkish, and UK entries have the weakest numeric anchors
    (pollster-dependent), hence medium/low tags.
  - `jan6_trump_approval` uses Gallup's −12pp reading; poll aggregators
    showed roughly −5pp. Either sign-matches; magnitude rank is
    Gallup-specific.
  - Approval/satisfaction questions differ in wording across countries
    ("approve", "satisfied", "favorable") — treated as equivalent
    directional metrics.
  - All events predate the LLM cutoff → every regime is
    `sim_delta_isolated` (LLM off, web off): the study isolates the
    simulation's scenario channel exactly as design §4.1 mechanism (b)
    requires.

## Verification log (Task 4 — 2026-08-18, web search)

All nine `confidence: high` events were checked against web sources.
**Result: 9/9 verified; one numeric correction.**

| event_id | outcome | source |
|---|---|---|
| sept11_bush_approval | confirmed 51→86 exactly | [Gallup 4912](https://news.gallup.com/poll/4912/bush-job-approval-reflects-record-rally-effect.aspx) |
| gulf_war_bush_sr_approval | confirmed 64→89 (89 = March 1991 post-victory) | [Gallup retrospective](https://news.gallup.com/opinion/gallup/234971/george-bush-retrospective.aspx) |
| iraq2003_bush_approval | confirmed 58→71 exactly | [Gallup 8074](https://news.gallup.com/poll/8074/iraq-war-triggers-major-rally-effect.aspx) |
| ford_nixon_pardon | confirmed 71→50 exactly | [Gallup 23995](https://news.gallup.com/poll/23995/gerald-ford-retrospective.aspx) |
| sandy_hook_gun_laws | confirmed 43→58 exactly (USA Today/Gallup Dec 19-22 2012) | [Gallup 159569](https://news.gallup.com/poll/159569/americans-stricter-gun-laws-oppose-bans.aspx) |
| parkland_gun_laws | confirmed 60→67 exactly | [Gallup 229562](https://news.gallup.com/poll/229562/preference-stricter-gun-laws-highest-1993.aspx) |
| ukraine_finland_nato | **CORRECTED** before 28→30 (Taloustutkimus Jan 2022); after 62 confirmed (Yle Mar 9-11) | [Yle](https://yle.fi/a/3-12357832), [NPR](https://www.npr.org/2022/03/03/1084112625/neutral-finland-sweden-warm-to-idea-of-nato-membership) |
| lehman_consumer_sentiment | confirmed 70.3→57.6 exactly | [UMich ICS table](https://www.sca.isr.umich.edu/files/tbmics.pdf) |
| covid_consumer_sentiment | confirmed 101.0→71.8 exactly | [Chicago Fed Letter 2023-490](https://www.chicagofed.org/publications/chicago-fed-letter/2023/490) |

## Verification log — second pass (Sprint 23, 2026-08-18, web search)

The remaining 13 medium/low events were checked before the official run.
**Result: 12/13 now verified; 5 numeric corrections; 1 metric switch;
Sweden stays unverified (baseline unconfirmed).**

| event_id | outcome |
|---|---|
| fukushima_de_nuclear | **METRIC SWITCHED** — authored "continued use 40→26" unverifiable; replaced with verified Infratest phase-out support 62→71 (+9). Now a referent-inversion hard case. |
| falklands_thatcher | **CORRECTED** 34→51 became 25→59 ([Ipsos-MORI via UPI](https://www.upi.com/Archives/1983/06/04/Falklands-The-war-that-saved-Margaret-Thatcher/1953423547200/)); Jan baseline predates invasion by 3 months (noted). |
| cuban_missile_kennedy | confirmed 61→74 exactly ([Gallup 6979](https://news.gallup.com/poll/6979/cuban-missile-crisis-years-later.aspx)) |
| charlie_hebdo_hollande | **CORRECTED** 21→29 became 19→40 (+21, record jump; [France24](https://www.france24.com/en/20150119-hollande-approval-rate-doubles-wake-terror-attacks-ifop-poll-france)) |
| nov2015_paris_hollande | **CORRECTED** 20→33 became 20→27 (Ifop/JDD conservative series; pollster variance noted) |
| coup2016_erdogan | confirmed 46.6→67.6 ([Metropoll via Bloomberg/AFP](https://www.bloomberg.com/news/articles/2016-08-11/erdogan-s-approval-rating-soars-in-turkey-following-coup-attempt)) |
| covid_johnson_approval | confirmed 46→66 exactly ([YouGov via Fortune](https://fortune.com/2020/10/05/boris-johnson-trump-approval-rating-covid-hospitalized-coronavirus)) |
| katrina_bush_approval | **REVISED to monthly averages** 44→41 (−3), downgraded to low confidence — Gallup's own headline: ["Little Impact of Katrina on Bush's Overall Job Ratings"](https://news.gallup.com/poll/24283/little-impact-katrina-bushs-overall-job-ratings.aspx). Weakest attribution in the set. |
| jan6_trump_approval | **CORRECTED** 46→34 became 39→34 (−5; [Gallup 328637](https://news.gallup.com/poll/328637/last-trump-job-approval-average-record-low.aspx): "down five points from December"). Poll window starts Jan 4 (straddle noted). |
| truss_minibudget_con_support | **REVISED** to confirmed YouGov endpoints 28 (Sept 23-25) → 21 (Sept 28-29, [YouGov](https://yougov.co.uk/politics/articles/43901-voting-intention-con-21-lab-54-28-29-sep-2022)); both post-announcement (noted). |
| dobbs_leak_prochoice | confirmed 49→55 exactly ([Gallup 393104](https://news.gallup.com/poll/393104/pro-choice-identification-rises-near-record-high.aspx)) |
| ukraine_sweden_nato | after=51 confirmed ([Novus via The Local](https://www.thelocal.se/20220422/majority-of-swedes-now-in-favour-of-joining-nato-poll/)); January baseline 37 UNCONFIRMED → stays `verified: false`. |
| refugee2015_merkel | **CORRECTED** 67→54 became 63→54 (−9; [Infratest dimap via Bloomberg](https://www.bloomberg.com/news/articles/2015-10-02/merkel-approval-rating-drops-to-four-year-low-on-refugee-crisis)) |

Post-pass dataset status: **21/22 verified**, 1 unverified (Sweden).
Authorship-confidence lesson (recorded honestly): of 13 authored
medium/low value-pairs, 5 needed correction and 1 was unverifiable —
authored numbers are candidates, never data.

Interesting verification finding: the Yle poll fielded Feb 23-25, 2022
(straddling the invasion's first hours) ALREADY showed 53% — most of the
Finnish swing happened within days of the event, supporting the tight
attribution window.
