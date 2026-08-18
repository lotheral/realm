# REALM Repositioning — Reaction-Distribution Engine Design

> **Date:** 2026-08-18
> **Status:** Approved (Loth, 2026-08-18 — full delegation granted for execution)
> **Supersedes:** the "Astrological Swarm Intelligence Prediction Engine" framing and the
> Sprint 19 "collective sentiment platform" framing, both of which this document sharpens
> rather than discards.

## 1. Original intent (restated by the product owner)

REALM's founding intent, in Loth's own words (2026-08-18): **simulate the world
population; detect in advance the reactions, opinions, and tendencies of people toward
events.** Astrology was never the focus — it was chosen as a *convenience mechanism* to
obtain temperament diversity across the simulated population. The project's documentation
and branding drifted into treating astrology as the core identity; this document corrects
that drift.

Three framing decisions were made explicitly on 2026-08-18:

| # | Question | Decision |
|---|----------|----------|
| 1 | Core output | **Reaction distribution** — "if event X happens, which segments react how, where do opinions shift?" Probability numbers are secondary/derived. |
| 2 | Population subject | **Per-question target population** — each question defines its population (country, demographic, segment); "world" is the union of these. |
| 3 | Success definition | **Proof first, then product** — close the research question ("does reaction prediction work, and how well?") with honest measurement; productization is gated on that evidence. |

## 2. What REALM is (product definition)

**REALM is a population-reaction simulation engine.** Given:

- an **event or question** (text),
- a **target population specification** (country/countries, demographic filters, segment),
- optionally a **scenario feed** (the event framed as news items),

it produces a **reaction distribution**:

- stance shares across the population (e.g. support / oppose / indifferent),
- the **shift** of those shares relative to the no-event baseline (direction + magnitude),
- **segment breakdown** (by country, age band, profession cluster, trait cluster),
- a derived probability only where the question genuinely reduces to a binary outcome.

### 2.1 Personality diversification is pluggable; astrology is one mode

The adapter layer already implements this correctly:
`astrological` | `big_five` (Johnson IPIP-NEO real data, N=612,711) | `demographic` |
`blended`. The ephemeris-seeded mode is a *procedural diversity generator* (the article's
"Perlin noise" framing) — no causal claim, not the default identity of the project.
Known measured weakness of the astrological mode: near-orthogonal OCEAN intercorrelations
(|r|<0.1 vs literature ~0.20); the real-data adapter is superior on joint-distribution
realism. Mode choice is a user/config decision, and validation studies must report which
mode was used.

### 2.2 Division of labor (confirmed direction from Sprint 19, now with a reason)

- The **LLM + web research** estimates *current level* — "where does opinion stand now?"
- The **simulation** estimates *dynamics* — "how does it move when the event lands?"

Sprint 20 diagnosis (this session) is expected to confirm the structural reason: in
baseline mode the simulation never sees question content, only the category — so
baseline sim output is question-blind by construction and cannot beat (or even inform) a
question-aware prior. The simulation's entire information channel is the **scenario
delta**. All validation effort therefore targets the delta, not the baseline level.

## 3. Scientific status at revival (2026-08-18)

- 887/887 tests green after 106-day freeze; venv intact; main == origin.
- Best-supported claim: trait distributions are psychometrically plausible (8/8 criteria
  vs Johnson IPIP-NEO-120 real data).
- **Falsified (with caveats):** sim improves baseline point prediction. Sprint 18's 5-market
  backtest showed the blend hurting — but the sim arm emitted ~constant 0.5 (std 0.0083),
  i.e. no information, and all 5 markets predated the LLM's knowledge cutoff. The test was
  both confounded and aimed at the wrong target.
- **Unproven (the actual thesis):** the simulation's scenario deltas correspond to real
  population reaction. No metric or study exists yet. Closing this is the project's
  central remaining task.

## 4. Validation design

### 4.1 Study A — Historical retrodiction against polling data (primary)

Select 15–30 historical events with documented before/after opinion measurements for a
defined population. Candidate sources: Eurobarometer waves, World Values Survey,
Gallup/Pew archives, government-approval time series, referendum polling series, consumer
confidence indices; for Türkiye, Konda/Metropoll-style series where accessible.

Per event:
1. Define target population (matching the poll's population).
2. Build the population with the chosen adapter mode; capture baseline stance distribution.
3. Feed the event as `scenario_feed`; record predicted shift (direction, magnitude,
   segment breakdown).
4. Compare against the actual poll delta.

**Blinding protocol (hard requirement):** the LLM must not be allowed to retrieve the
*post-event* opinion data it is being tested on. Mechanisms, in order of preference:
(a) use events after the LLM's knowledge cutoff with web research disabled;
(b) for older events, run the LLM prior stage with an event-masked prompt or disable the
LLM stage entirely and test the sim delta in isolation;
(c) always log which regime each event ran under. The Sprint 18 mistake (2020 markets,
memorization confound) must not be repeated.

**Metrics:**
- Directional accuracy of the shift (sign agreement), with binomial test vs 50%.
- Magnitude correlation (Spearman) between predicted and observed shift sizes.
- Segment-level agreement where polls provide breakdowns (e.g. did the model correctly
  identify which segment moved most?).
- Honest reporting of N, event selection criteria, and per-event confidence — including
  the low/med/high confidence ratio as a first-class metric.

A negative result is a valid completion of the research question and will be published
as such.

### 4.2 Study B — Forward prediction diary (background, starts immediately)

A registry (`outputs/prediction_diary/`) of predictions on upcoming events, written
*before* the events resolve, scored as polls arrive. Epistemically clean (leakage
impossible); slow to accumulate. Runs continuously in the background from Sprint 22
onward; costs almost nothing to maintain.

### 4.3 Explicitly out of scope (YAGNI)

- Social-media sentiment replication as ground truth (noisy, biased, expensive API access).
- Beating prediction markets at point probability (falsified target; not the product).
- Global-population claims without a per-question population definition.

## 5. Sprint plan

| Sprint | Scope | Session |
|--------|-------|---------|
| **20** | Revival: external-surface smoke tests; critical fixes (web-research side channel, drift-engine factory + state round-trip, LLM gate centralization, dependency/CI hygiene); question-blindness diagnosis experiment; documentation sync (versions, missing Sprint 18 milestone section, backtest caveat regeneration); this design doc. | 2026-08-18 (this) |
| **21** | Reaction-distribution output layer: `PopulationSpec` (per-question target population), stance-distribution observable surfaced from the sim (mechanism already computes it internally), `ReactionDistribution` response schema, dashboard surface. | next |
| **22** | Study A dataset assembly (events + polls, blinding regime per event) + retrodiction harness; Study B diary bootstrap. | next+1 |
| **23** | Run Study A, write results honestly, rewrite `REALM_ARTICLE_DRAFT.md` around the reaction-distribution thesis and actual numbers. | next+2 |
| **24** | Repositioning surface work gated on evidence: naming, README identity, dashboard About, product decision. | after results |

## 6. Non-goals of Sprint 20

No renaming, no README identity rewrite, no article edits beyond factual corrections —
all repositioning surface work waits for Study A numbers (decision #3: proof first).

## 7. Sprint 24 closure — naming decision and roadmap completion (2026-08-19)

Study A delivered its numbers (negative for the valence channel;
`outputs/study_a_analysis.md`), unlocking §6. Decisions taken under the
standing full delegation:

- **Name: REALM stays.** The name itself is astrology-neutral; what had
  drifted was the surface framing. Changed surfaces: observatory
  dashboard title ("Astrological Swarm Intelligence" → "Population-
  Reaction Observatory"), README heading + honest validation-status
  block, v2 About heuristic-mode caveat. The article title was already
  rewritten in Sprint 23.
- **Product posture:** the heuristic scenario channel is presented as
  event-valence propagation, never as poll-shift prediction. The
  referent-relation channel (frozen literature-prior matrix, commit
  f2df2de) failed its pre-stated held-out bar (DA 4/8, needed >50% with
  p<0.1) and therefore stays research-only, NOT wired into the API.
  The full LLM pipeline's evidence channel is Study B (forward diary).
- This closes the §5 sprint table. Post-roadmap work (growing Study B,
  a possible matrix v2 with victory/compound-event classes tested on a
  THIRD event set, magnitude de-quantization) proceeds evidence-first.
