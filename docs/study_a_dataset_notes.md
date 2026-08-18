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

## Verification log (Task 4)

Filled during the verification pass; every `verified: true` names its
source here and in the event's `verification_note`.

*(pending)*
