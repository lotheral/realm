# Study A — Analysis of the Official Run (2026-08-18)

> Companion to `outputs/study_a_results.md` (raw report) and
> `docs/study_a_dataset_notes.md` (dataset provenance). Design:
> design doc §4.1. Run: 22 events, n_agents=100, n_ticks=30,
> n_branches=5, seed=42, all events `sim_delta_isolated` (LLM off,
> web off — the blinded regime).

## Verdict

**The heuristic (LLM-off) scenario channel does not retrodict real
poll shifts. Directional accuracy 6/22 (27%), below the 50% coin-flip
baseline; signed Spearman ρ = −0.357 (systematically anti-correlated);
magnitude ρ = −0.105 (no magnitude signal).** Per design decision #3
this negative result is a valid completion of the research question for
this channel, and it is diagnostic: the failures decompose into three
identifiable mechanisms rather than noise.

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

## Where the channel works

`confidence_index` 2/2 (Lehman −20.8 vs −12.7; COVID −20.2 vs −29.2),
plus Katrina and Jan-6. These are exactly the cases where **valence and
referent coincide**: bad economic news → economic confidence falls; the
event is *about* the questioned subject and pushes it the same way. The
channel is an event-valence propagator, and it retrodicts correctly
precisely when the poll metric is a valence thermometer.

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

- Dataset: 22 events, 7 countries; 21/22 verified against named sources
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
