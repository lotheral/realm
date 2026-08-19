# Study A — Analysis of the Official Run (2026-08-18)

> Companion to `outputs/study_a_results.md` (raw report) and
> `docs/study_a_dataset_notes.md` (dataset provenance). Design:
> design doc §4.1. Run: 22 events, n_agents=100, n_ticks=30,
> n_branches=5, seed=42, all events `sim_delta_isolated` (LLM off,
> web off — the blinded regime).

## Erratum (2026-08-20, Sprint 25) — corrected numbers

The 2026-08-18 official run was contaminated by a **third LLM blinding
leak**: category routing has been LLM-first since Sprint 17 and was
gated only by the `REALM_LLM_CATEGORY_BACKEND` environment variable —
the per-request `use_llm=False` flag never reached it. With the var set
(as it was), the LLM classified every event's question and its category
choice re-parameterized the simulation (drift weights, sigmoid
sensitivity, asymmetry). Four of 22 events were routed differently from
the keyword-only path; after the fix the clean run
(`outputs/study_a_results_postfix.md`, same seed/params) gives:

- **DA 4/22 (18%)** (was 6/22), p = 1.000; zero-preds 3 (was 2)
- **signed Spearman ρ = −0.506** (was −0.357; −0.497 before the
  Sprint 26 Sweden data correction below); magnitude ρ = −0.124
- **confidence_index 0/2** (was 2/2) — both former hits (Lehman, COVID
  consumer sentiment) existed only because the LLM routed those
  questions to `economics`; the keyword router cannot classify them
  (they fall to `balanced`, predicting a near-zero +0.6pp)
- rally 0/9, approval_drop 2/5, policy_shift 2/6 — unchanged
- held-out set: **2/8** (was 3/8), signed ρ = −0.128; both surviving
  hits are noise-magnitude sign coincidences (|predicted| ≤ 0.6pp)

The verdict below **stands and strengthens**. Numbers in the original
text are kept for the record and marked; a fourth failure mode is added.

**Sprint 26 addenda (2026-08-20):**

- **Sweden data correction.** The `ukraine_sweden_nato` baseline (37)
  was Demoskop's January 2022 AGAINST share, not the FOR share (42).
  Corrected to the single-pollster Demoskop series Jan 42 → Mar 51
  (+9pp, was +14pp with mixed pollsters); the event is now verified —
  **dataset 22/22 verified**. Sweden's sign is unchanged, so DA stays
  4/22; signed ρ moves −0.497 → −0.506. Artifacts regenerated.
- **Magnitude de-quantization (queue item closed).** The
  `clamp(|sentiment|·2, 0.08, 0.15)` map collapsed 15 distinct parser
  scores into 6 magnitudes (7 at floor, 5 at cap). Replaced with
  `0.15·tanh(|sentiment|·2/0.15)` — strictly monotone, 14 distinct
  magnitudes, no floor. Measured result (comparison run
  `outputs/study_a_results_dequant.md`): DA 4/22 unchanged, magnitude ρ
  −0.124 → **−0.066**. Honest conclusion: the artifact is gone and the
  channel STILL carries no magnitude signal — the lexicon scores
  themselves do not rank real shift sizes. Magnitude claims stay off.

## Verdict

**The heuristic (LLM-off) scenario channel does not retrodict real
poll shifts. Directional accuracy 4/22 (18%) under complete blinding
(originally reported 6/22 before the erratum above), below the 50%
coin-flip baseline; signed Spearman ρ = −0.506 (systematically
anti-correlated); magnitude ρ = −0.124 (no magnitude signal).** Per
design decision #3 this negative result is a valid completion of the
research question for this channel, and it is diagnostic: the failures
decompose into identifiable mechanisms rather than noise.

## The three failure modes

**1. Referent blindness (dominant; explains rally 0/9 and the NATO and
Fukushima misses).** The channel propagates *event valence* — a
negative-sentiment feed pushes the population's category traits down,
which lowers "support". But a poll question's subject has a *semantic
relation* to the event that valence cannot see:

- Rally-round-the-flag: attacks (negative valence) RAISE leader
  approval — all 9 rally events missed (predicted −21 to −29pp or 0,
  observed +7 to +35pp).
- Threat-to-status-quo: war news (negative) RAISED Finnish/Swedish NATO
  support (+32/+14pp observed; −21/−23pp predicted); Fukushima
  (negative) RAISED German phase-out support (+9 observed, −19.6
  predicted).

**2. Parse instability (explains the incoherent pairs).** Near-identical
events received opposite predictions from word-inventory quirks:

- Sandy Hook +42.4pp vs Parkland −0.2pp — the same mechanism, opposite
  outputs.
- Ford pardon predicted +42.4pp ("grants", "full", "unconditional" read
  positive) vs observed −21pp; Truss mini-budget +46.4pp ("tax cuts"
  reads positive; "crash/collapse" underweighted) vs observed −7pp.
- Falklands and Charlie Hebdo parsed neutral → honest 0.0 (Sprint 20
  behavior), counted as misses.

**3. Magnitude quantization.** Predictions cluster at ≈0, ±20-29, or
±42-46pp — artifacts of the perturbation floor (0.08), cap (0.15), and
the 70% affected-population ratio — so predicted magnitudes carry no
rank information (ρ = −0.105).

## Where the channel works — revised by the erratum

The original text claimed `confidence_index` 2/2 (Lehman, COVID
consumer sentiment) as the showcase of **valence-referent coincidence**.
The erratum killed both: those hits required the LLM to route the
questions to `economics`; under clean keyword-only routing they fall to
`balanced` and the channel predicts ≈+0.6pp (wrong sign, miss). This
exposes a **fourth failure mode — category dependence**: the channel's
event-valence propagation only lands on the right traits when the
question is classified into the right category, and the offline keyword
router cannot do that for exactly the "valence thermometer" questions
where the mechanism should shine.

What survives clean blinding: Katrina and Jan-6 (approval_drop — the
event is *about* the leader and pushes approval the same way as its
valence) and Sandy Hook + Dobbs (policy_shift, at quantized +42pp
magnitudes). The coincidence reading still holds for these four, but at
4/22 the channel has no claim to a working regime — only to
interpretable failures.

## What this does and does not falsify

- **Falsified:** the heuristic sentiment-sign scenario channel as a
  general poll-shift predictor.
- **Not tested (by design):** the full pipeline with the LLM scenario
  analyzer. It could not run here — an LLM that knows how 9/11 turned
  out cannot be blinded for retrodiction (the Sprint 22 gate fix exists
  precisely because it leaked +62pp of outcome knowledge into an early
  smoke). The clean test of the full pipeline is **Study B** (forward
  diary, `outputs/prediction_diary/`), where LLM+web are legitimate
  because the outcome does not exist yet.
- **Unaffected:** trait-distribution realism (8/8 psychometric criteria
  vs Johnson IPIP-NEO) and the reaction-distribution output surface
  (population targeting, pooled stances, segments) — the instrument is
  sound; the current direction mechanism behind it is what failed.

## Honesty envelope

- Dataset: 22 events, 7 countries; 22/22 verified against named sources
  (5 authored values corrected, 1 metric switched during verification —
  see the dataset notes' lesson: authored numbers are candidates, never
  data). Authorship-confidence ratio: 9 high / 10 medium / 3 low.
- Deliberate composition: 9/22 events are rally-type — chosen
  *because* they are hard for a valence mechanism. A dataset of only
  confidence-index events would have flattered the channel; that would
  have been calibration theater.
- Single seed (42), single parameter set. Branch pooling (5×100 agents)
  reduces but does not eliminate run-to-run variance; signs at ±20pp
  magnitudes are stable.

## Implications for the roadmap

1. **Sprint 24 candidate mechanism:** a *referent-relation* layer —
   the scenario channel needs (event → question-subject) polarity, not
   just event valence. Options: LLM-derived relation for forward use
   (already exists as the scenario analyzer), a structured rule layer
   for blinded/offline use (event-type × question-type polarity matrix
   — e.g. `threat × incumbent-approval → +`), or dropping the blinded
   heuristic channel and accepting Study B as the only honest test.
2. **Study B is now the primary evidence channel** for the full
   pipeline; the diary should accumulate entries from Sprint 24 on.
3. The dashboard/product surface should not present heuristic-mode
   scenario deltas as poll-shift predictions; they are valence
   propagation, and the About tab should say so.
