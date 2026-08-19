# REALM: A Population-Reaction Simulation Engine

**Modeling How Defined Populations React to Events — Stance Distributions, Shifts, and Segments**

**Suvar Ergun** · 2026 · v0.24.1 · MIT License · [`github.com/lotheral/realm`](https://github.com/lotheral/realm)

---

## Abstract

We present REALM, an agent-based platform whose research question is: *given an event and a defined target population, can a simulation of psychometrically realistic agents predict the population's reaction — which stances shift, in which direction, and in which segments?* REALM's primary output is a **reaction distribution** — support/oppose/neutral stance shares pooled across simulation branches, their shift against a no-event baseline, and breakdowns by country, region, age band, and gender for a per-question target population — with any single probability number treated as a derived view.

We report three validation results with full honesty. **(1) Population realism:** REALM's trait-diversification layer produces populations that pass 8/8 psychometric validity criteria against the Johnson IPIP-NEO-120 dataset (N=612,711), with 13/13 facet-level correlations significant. **(2) A structural diagnosis:** baseline (no-event) simulation output is *question-blind by construction* — different questions in the same category produce identical output — so the simulation cannot and should not compete with a question-aware prior on baseline probability; its entire information channel is the scenario delta. **(3) A negative retrodiction result:** in Study A, a 22-event blinded benchmark of documented before/after poll shifts across 7 countries, the LLM-free scenario channel achieved 18% directional accuracy (4/22, below the 50% coin-flip baseline; signed Spearman ρ = −0.497). The failures decompose into four identifiable mechanisms — referent blindness (rally events: 0/9), sentiment-parse instability, magnitude quantization, and category dependence: the originally reported economic-confidence hits (2/2) turned out to require LLM category routing, itself a blinding leak found in a post-publication audit, and vanish under the completed blinding gate (0/2). We publish this negative result as a valid completion of the research question for that channel, and describe the ongoing forward-prediction diary (Study B) that tests the full LLM-informed pipeline without the leakage that makes blinded retrodiction impossible for it.

REALM simulates up to 10,000 agents across 66 countries with per-question population targeting, 15 drift event types, 9 prediction categories, and an interactive dashboard. The platform, the benchmark dataset, and all validation harnesses are open-source under the MIT license.

---

## 1. Introduction

Opinion polls measure population reactions after the fact. Prediction markets aggregate point probabilities but cannot answer *"who moves, and why?"* Language models can narrate plausible reactions but provide no population structure and no counterfactual mechanics. REALM asks whether an agent-based simulation with realistic personality diversity can fill this gap: **detect, in advance, the reactions, opinions, and tendencies of a defined population toward an event.**

This framing dictates the output format. A useful answer to "how will population P react to event X?" is not a scalar probability; it is a distribution — how the stance shares move relative to the no-event baseline, and which segments move most. REALM therefore returns, for every question:

- stance shares (support / oppose / neutral) pooled across all simulation branches,
- the shift of those shares against the baseline run (direction + magnitude),
- segment breakdowns (country, region, age band, gender) over a caller-defined target population,
- a derived probability, only meaningful where the question genuinely reduces to a binary.

Honest measurement is the project's second commitment. This paper reports a validated strength (population realism), a structural limitation discovered by experiment (question-blindness of the baseline channel), and a negative benchmark result (the blinded scenario channel does not retrodict poll shifts), together with the failure-mode analysis that makes the negative result actionable.

---

## 2. Population Construction

### 2.1 Per-Question Target Populations

Each question defines its population. A `PopulationSpec` (countries and/or regions with union semantics, age band, gender, education filters) constrains demographic sampling: country candidates are restricted and re-weighted by national population; per-agent attributes are drawn by bounded rejection resampling, keeping generation deterministic for a given (seed, spec). "The world" is simply the unrestricted spec (66 countries, population-weighted). All validation runs in this paper use country-scoped populations matching each poll's population.

### 2.2 Trait Diversification Is Pluggable

Every agent carries a 24-dimensional trait vector (risk_appetite, herd_susceptibility, authority_compliance, loss_aversion, political_spectrum, …, all in [0,1]). Four interchangeable adapters populate it:

- **Big Five (real-data):** facet-level mapping from the Johnson IPIP-NEO-120 framework; the psychometrically strongest mode.
- **Demographic:** country-level Hofstede dimensions + V-Dem-blended political axis.
- **Astrological (procedural):** Swiss-Ephemeris natal calculations used as a deterministic, continuous, structured hash of birth time — a *procedural diversity generator* in the sense that procedural graphics use Perlin noise. We make no causal claim, and we report its measured weakness: near-orthogonal OCEAN intercorrelations (|r| < 0.1 vs ~0.20 in the literature).
- **Blended:** weighted combination (default 60/25/15 astro/big-five/demographic).

Mode choice is a configuration decision; validation studies must and do report which mode was used. The astrological mode is *one option*, not the project's identity.

### 2.3 Simulation Engine

Agents interact on a small-world + scale-free hybrid network. Per tick: agents post and engage according to traits; an `ExperienceDriftEngine` fires events (15 config-driven types) that shift traits within a cumulative ±10% clamp; category-conditioned event weights, volatility, and asymmetry parameters differentiate domains. Multi-branch runs (default 5 branches × perturbed seeds) provide distributional output; per-agent deviations are pooled across *all* branches into the reaction distribution.

### 2.4 Prediction Pipeline and Division of Labor

The full pipeline is: LLM question analysis (category, subject, prior; optional web research) → multi-branch simulation → calibrated blend → LLM narrative. The division of labor is explicit and empirically motivated (§4.2): **the LLM estimates the current level; the simulation estimates the dynamics.** For scenario questions the user supplies an event feed; it is analyzed either by an LLM scenario analyzer (per-trait impacts) or, in LLM-off mode, by a lexicon-based sentiment parse applied to the category's primary traits. All LLM stages are hard-gated by a single `use_llm` switch — a gate whose completeness we had to fix during this work, because a partially gated pipeline silently leaked LLM knowledge into "simulation-only" runs (§4.3).

---

## 3. The Reaction Distribution

For a request, REALM runs a 0-tick reference simulation to capture baseline trait means, then B baseline branches and (if a scenario is supplied) B scenario branches on the same target population. Each agent's weighted trait deviation from the reference means (category primary traits ×2.0, secondary ×1.0, suppressed ×0.25) is computed with drift applied; deviations from all branches are pooled (B × N samples) and bucketed by a single global threshold (max(0.005, 0.5σ)) into support/oppose/neutral. Segments below a minimum pooled size are dropped; each dimension reports its largest segments. The scenario response is the element-wise shift between scenario and baseline stance shares, decomposed in the API into blend-mechanical and simulation-movement components.

This surface — not a probability — is the product claim under test.

---

## 4. Validation

### 4.1 Population Realism (positive result)

Trait distributions from REALM populations were benchmarked against the Johnson IPIP-NEO-120 public dataset (N=612,711): **8/8 validity criteria PASS** in facet mode, with **13/13** facet-level correlation checks passing and 15/15 structural intercorrelation pairs matching in the synthetic benchmark. Known honest caveats are retained in the repository's validation reports: the calibration layer is distribution-specific (a calibrator trained on synthetic marginals mis-corrects real data unless source-aware — implemented), and the astrological mode's trait intercorrelations are weaker than literature values. A small celebrity-cohort study (N=22, discriminant accuracy 0.718) is reported as directional only, given its size and selection bias.

### 4.2 Question-Blindness of the Baseline Channel (structural diagnosis)

A controlled experiment (three semantically different questions per category, fixed seeds) showed baseline simulation output is **bit-for-bit identical across questions within a category**: the baseline channel sees only the category, never the question text. Cross-category variation reduces to calibrated offsets. Consequently an earlier 5-market Polymarket backtest in which "the simulation added negative value" to a blended point forecast (ΔBrier +0.048) is reinterpreted: the simulation arm emitted a near-constant 0.5 (σ = 0.008) — diluting an LLM prior with noise is not evidence about reaction modeling, because the baseline channel contains no question information *by construction*. That test also suffered a memorization confound (all markets predated the LLM cutoff). Both design errors shaped Study A: test the **scenario delta**, and blind it properly.

### 4.3 Study A — Blinded Retrodiction Against Documented Poll Shifts (negative result)

**Benchmark.** 22 historical events across 7 countries (US, GB, DE, FR, TR, FI, SE), each with a documented before/after opinion measurement from a named pollster or index, an event summary written as outcome-free news copy, a country-scoped target population, and a mechanism tag: 9 *rally* (negative event → leader approval rises), 5 *approval_drop*, 6 *policy_shift* (including threat-to-status-quo cases), 2 *confidence_index*. 21/22 events' numbers are verified against sources (the verification pass corrected 5 authored values and replaced one unverifiable series — a recorded lesson that authored numbers are candidates, never data). Rally events are included *because* they are hard: excluding them would be calibration theater.

**Blinding.** All events predate the LLM's knowledge cutoff, so all ran in `sim_delta_isolated` mode: LLM and web research disabled, testing the lexicon-driven scenario channel in isolation. This gate had to be *made* complete — twice. First, the original `use_llm=False` toggle gated only the question analyzer, and the LLM scenario analyzer — which knows how 9/11 turned out — was still running (an early smoke predicted +62pp for 9/11 through this leak). The fixed pipeline predicts −27pp for the same event and honestly takes the miss. Second, a post-publication audit found that *category routing* had been LLM-first since Sprint 17 and was gated only by an environment variable: with it set, the LLM classified every event's question, and its category choice re-parameterized the simulation itself (drift weights, sigmoid sensitivity, asymmetry). Four of 22 events were LLM-routed differently from the offline keyword path; the numbers below are from the clean re-run after closing that gate (the contaminated run scored 6/22 with ρ = −0.357 — both of its economic-confidence hits were LLM-routing artifacts).

**Result** (n_agents=100, n_ticks=30, n_branches=5, seed=42; predicted shift = support-share shift × 100):

| Metric | Value |
|---|---|
| Directional accuracy | **4/22 (18%)** — below coin flip; one-sided binomial p(≥4 hits) = 1.000 |
| Signed Spearman ρ (predicted vs observed) | **−0.497** |
| Magnitude Spearman ρ | −0.124 (no magnitude signal) |
| rally | **0/9** |
| approval_drop | 2/5 |
| policy_shift | 2/6 |
| confidence_index | **0/2** (2/2 in the contaminated run — LLM-routing artifacts) |
| Zero-predictions (neutral parse → honest 0.0) | 3 |

**Failure-mode analysis.** The misses decompose into three mechanisms:

1. **Referent blindness** (dominant): the channel propagates *event valence* onto category traits, but a poll subject relates to the event semantically. Attacks lower simulated "support" yet raise real leader approval (all 9 rally events); war news lowers simulated support yet raised Finnish NATO support by +32pp; Fukushima lowered simulated support yet raised German phase-out support by +9pp.
2. **Parse instability:** near-identical events received incoherent predictions from lexicon quirks — Sandy Hook +42pp but Parkland −0.2pp; the Nixon pardon read *positive* (+42pp, "grants … full … unconditional") against an observed −21pp.
3. **Magnitude quantization:** outputs cluster near 0, ±20–29, and ±42–46pp — artifacts of the perturbation floor/cap and affected-population ratio — leaving no usable magnitude ranking.
4. **Category dependence** (found by the blinding audit): valence propagation only lands on the right traits when the question is classified into the right category, and the offline keyword router cannot classify exactly the consumer-sentiment questions where valence-referent coincidence should work — they fall to the `balanced` category and produce near-zero deltas. The channel's apparent "working regime" (economic confidence 2/2) was an artifact of LLM-assisted classification.

The four hits that survive complete blinding (Katrina, Jan-6, Sandy Hook, Dobbs) are cases where valence and referent coincide, but at 4/22 the channel has no working regime to claim — only interpretable failures. **Conclusion: the LLM-free scenario channel is an event-valence propagator, and event valence alone does not predict poll shifts.** Under the project's proof-first rule this negative result stands as published; it falsifies that channel as a general reaction predictor, not the reaction-distribution instrument built on top of it, and not the LLM-informed channel — which *cannot* be tested by retrodiction at all (leakage), only forward.

### 4.4 Study B — Forward Prediction Diary (ongoing)

The clean test of the full pipeline (LLM + web + simulation) is prospective: an append-only diary of predictions on upcoming events, written before resolution, never edited, scored as polls arrive (`outputs/prediction_diary/`). Forward prediction makes leakage impossible, so the LLM stages are legitimate there. The diary accumulates slowly by design; its running directional score is a first-class honesty metric of the project.

---

## 5. Discussion

### 5.1 What Holds, What Fell, What Is Untested

- **Holds:** psychometric realism of the generated populations (8/8); the reaction-distribution output surface (per-question populations, pooled stances, segments); the diagnosis methodology itself.
- **Fell:** the blinded, lexicon-driven scenario channel as a poll-shift predictor (18% DA, anti-correlated); the earlier framing of the simulation as a baseline-probability contributor (question-blind by construction).
- **Untested:** the LLM-informed scenario channel on real reactions — Study B exists to test it honestly.

### 5.2 The Constructive Reading

The failure modes are specific enough to act on. Referent blindness calls for a *relation* layer — the polarity of (event → question subject) rather than the polarity of the event: an LLM provides this forward (it is the scenario analyzer's job), and a structured event-type × question-type polarity matrix is a candidate for blinded/offline use (e.g. `external threat × incumbent approval → positive`, the rally regularity known since Mueller 1970). Parse instability argues for replacing lexicon scoring with the relation layer entirely. Magnitude quantization requires freeing the perturbation from its floor/cap regime before magnitudes can mean anything.

### 5.3 Limitations

- Study A: N=22, one seed, one parameter set; single-pollster series with cross-country wording differences; two events with imperfect windows (documented per-event); 1/22 baseline value unverified.
- Agent traits are synthetic population-level tendencies, not individuals; the engine models sentiment dynamics, not truth.
- political_spectrum is a country-level dispersion proxy (Hofstede + V-Dem), not measured polarization.
- The derived probability inherits every limitation above; it is reported as a view of the distribution, not as a calibrated forecast.

---

## 6. Technical Specifications

| Component | Detail |
|-----------|--------|
| Language | Python 3.11 |
| Output | ReactionDistribution: pooled stances, baseline shift, segments (country/region/age-band/gender) |
| Population targeting | PopulationSpec: countries/regions (union), age, gender, education; deterministic constrained sampling |
| Ephemeris | Kerykeion (Swiss Ephemeris) — one of four adapter modes |
| Adapters | astrological · big_five (Johnson IPIP-NEO, N=612,711) · demographic · blended |
| Traits | 24 dimensions |
| Countries | 66 (population-weighted) |
| Drift events | 15 types (config-driven, category-conditioned) |
| Categories | 9 |
| Benchmark | Study A: 22 events, 7 countries, 21/22 verified, blinded harness (`scripts/run_study_a.py`) |
| Diary | Study B: append-only forward registry (`scripts/diary.py`) |
| Validation | BF 8/8 PASS · Study A DA 4/22 (negative, published; corrected post-audit) · 1023 automated tests · CI |
| License | MIT |

---

## 7. Conclusion

REALM set out to answer a falsifiable question: can a simulation of psychometrically realistic agents predict how a defined population reacts to events? The honest answer so far has three parts. The population layer is real — its trait distributions match large-scale psychometric data. The output layer is real — reaction distributions over targeted populations, with segments and shifts, are a genuinely different product surface from point probabilities. But the only reaction *mechanism* that could be tested under blinding — event-valence propagation — measurably fails against documented poll shifts (27% directional accuracy, 0/9 on rally events), for reasons the benchmark makes precise: reactions follow the relation between event and subject, not the valence of the event. We publish that negative result, ship the 22-event benchmark and harness for others to beat, and move the live hypothesis to the only channel that can carry it honestly: registered forward predictions.

---

## References

[1] Johnson, J. A. (2014). Measuring thirty facets of the Five Factor Model with a 120-item public domain inventory: Development of the IPIP-NEO-120. *Journal of Research in Personality*, 51, 78-89.

[2] Hofstede, G. (2011). *Dimensionalizing Cultures: The Hofstede Model in Context.* Online Readings in Psychology and Culture, 2(1).

[3] Coppedge, M., et al. (2023). *V-Dem Codebook v13.* Varieties of Democracy Institute.

[4] Watts, D. J., & Strogatz, S. H. (1998). Collective dynamics of 'small-world' networks. *Nature*, 393, 440-442.

[5] Barabási, A. L., & Albert, R. (1999). Emergence of Scaling in Random Networks. *Science*, 286, 509-512.

[6] Mueller, J. E. (1970). Presidential Popularity from Truman to Johnson. *American Political Science Review*, 64(1), 18-34.

[7] Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, 78, 1-3.

Study A poll sources (Gallup, Ipsos-MORI, Ifop, Infratest dimap, Metropoll, YouGov, Novus, Yle/Taloustutkimus, University of Michigan) are cited per-event in `data/validation/study_a_events.json` and `docs/study_a_dataset_notes.md`.

---

*REALM is open-source software released under the MIT License.*
*Repository: [`github.com/lotheral/realm`](https://github.com/lotheral/realm)*
