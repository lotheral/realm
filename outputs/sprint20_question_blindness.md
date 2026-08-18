# Sprint 20 — Baseline Question-Blindness Diagnosis

Scale: 50 agents x 10 ticks x 3 branches, master_seed=42, LLM disabled.

## Experiment 1 — same category, different questions

| question | category | sim-only probability | branch values |
|---|---|---|---|
| Will Bitcoin close above $150,000 by the end of 2026? | crypto | 0.5024 | [-0.0005, -0.0003, 0.003] |
| Will Ethereum flip Bitcoin in market cap this decade? | crypto | 0.5024 | [-0.0005, -0.0003, 0.003] |
| Will a major exchange collapse trigger a crypto winter this year? | crypto | 0.5024 | [-0.0005, -0.0003, 0.003] |

H1 verdict: **CONFIRMED — bit-for-bit identical.** The baseline simulation is question-blind: question text influences nothing but routing.

## Experiment 2 — cross-category spread

| expected category | routed | sim-only probability |
|---|---|---|
| crypto | crypto | 0.5024 |
| science | balanced | 0.5017 |
| geopolitics | geopolitics | 0.4938 |
| sports | sports | 0.5128 |

Baseline sim-only output should equal the per-category calibrated level (Sprint 16: geopolitics 49.20% ... science 53.34% at calibration scale) — i.e. category identity, not question content.

## Experiment 3 — scenario feeds (the information channel)

| feed | baseline p | scenario p | delta |
|---|---|---|---|
| bullish | 0.5024 | 0.7156 | +0.2132 |
| bearish | 0.5024 | 0.2717 | -0.2307 |
| neutral | 0.5024 | 0.5024 | +0.0000 |

## Interpretation

If H1 is confirmed: Sprint 18's 'sim adds negative value (+0.048 Brier)' finding is a structural tautology, not an empirical defeat — sim-only baseline output carries zero question-specific information BY CONSTRUCTION, so blending it toward a question-aware prior can only dilute. The correct target for all validation effort is the scenario DELTA (Experiment 3's channel), which is exactly the reaction-distribution thesis of the 2026-08-18 repositioning design.

## Second finding — heuristic scenario path was direction-blind (FIXED in Sprint 20)

The first run of Experiment 3 (pre-fix) produced +0.125 for bullish, bearish AND neutral feeds alike: predict.py used the strict base-only sentiment inventory (missing 'panic', 'fear', 'insolvency', 'optimism', ...), and a neutral parse fell back to a FABRICATED +0.08 positive nudge. Fix: full inventory + expanded affect terms; neutral parse now applies zero perturbation with a warning. Post-fix, the numbers above show symmetric, direction-correct movement with the LLM disabled.
