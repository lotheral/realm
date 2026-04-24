# REALM

Parametrized swarm-simulation framework with pluggable personality inputs.

Astrology (natal charts via Kerykeion), self-report Big Five (via literature-derived
domain-trait derivation), or demographic profile (via Hofstede cultural dimensions)
can each drive the simulation's 24-trait personality space. Scenarios, news
injection, and a "what-if" comparison dashboard sit on top.

Blueprint: see [`REALM_CLAUDE.md`](./REALM_CLAUDE.md).
Memory: see [`C:/Users/loth/.claude/projects/C--Users-loth-desktop-realm/memory/`](file:///C:/Users/loth/.claude/projects/C--Users-loth-desktop-realm/memory/) for session-persistent notes.

## Current state (2026-04-24)

- **508 tests passing**, ruff clean
- 8 phases complete (Phase 1–6 + LLM + scenario panel + variance fix + input-adapter layer)
- Phase 7 (POLYLIQ/ARGUS) deferred

## Architecture at a glance

```
DemographicProfile
  │
  ▼
IInputAdapter  ──▶  TraitVector
  │
  ├─ AstrologicalAdapter  (default, wraps IPersonalityEmbedder)
  ├─ BigFiveAdapter       (OCEAN scores → literature-derived 24 traits)
  └─ DemographicAdapter   (Hofstede + religion + region as primary signal)
  │
  ▼
CulturalModifier  (applied when adapter.applies_cultural_modifier is True)
  │
  ▼
TraitCalibrator   (opt-in soft-rescale to Big Five population norms)
  │
  ▼
Agent  (profile + natal_chart | None + traits)
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Unix
pip install -e .[dev]
pytest                      # expect 508 passing
```

## Config

- `config/realm.yaml` — master seed, phase/adapter selection, LLM defaults
- `config/astrology.yaml` — bodies, aspects, orbs, rule-based dampening, calibration opt-in
- `config/trait_calibration.json` — per-trait (mean, std) for the calibrator (generated)
- `data/astro/*.json` — planet→trait and sign→trait tables (with `_excluded_by_design` blocks)
- `data/personality/big_five_derivation.json` — literature-sourced OCEAN→domain-trait coefficients

## Common entry points

```bash
python scripts/serve_dashboard.py 500              # live dashboard + scenario panel (http://127.0.0.1:8888/)
python scripts/demo_butterfly.py                   # offline butterfly-effect demonstration
python scripts/validate_phase2.py 2000             # end-to-end phase-2 smoke
python scripts/diag_variance.py 2000               # variance-compression diagnostic (2D sweep)
python scripts/validate_trait_distribution.py 10000                    # astrological path
python scripts/validate_trait_distribution.py 5000 --adapter=demographic
python scripts/check_jobs_directional.py           # Jobs chart invariance check across dampening
python scripts/build_calibration_stats.py 5000     # regenerate trait_calibration.json
python scripts/validate_phase4_llm.py              # real-LLM smoke (needs API keys in .env)
```

## Key design boundaries

- **political_spectrum** is excluded-by-design from both the astrology layer and the Big Five derivation. REALM models personality temperament, not ideological preference. See `_excluded_by_design` blocks in `data/astro/planet_trait_map.json` and `data/personality/big_five_derivation.json`.
- **Calibration is opt-in.** Default config has `trait_calibration.enabled: false`. Enable only after measuring baseline and confirming the trade-off is worth it.
- **Astrology-bound features gracefully degrade.** TransitModulator and dashboard natal-chart panel both null-guard when a non-astrological adapter produced the agent.

## Known limitations (not blockers, surface to validity-study)

- Big Five intercorrelations are near-zero in REALM (|r|<0.1) vs literature ~0.20 — mapping treats traits as roughly independent.
- Three traits carry systematic positive bias in the raw astrology mapping (empathy, persuasion_skill, social_dominance, all mean ≥ 0.85). Calibration corrects at the cost of flattening natural astrological bias.
- BigFiveAdapter has 5 domain traits with no published Big Five correlation (fallback 0.5) and 2 low-confidence derivations (contrarian_tendency, authority_compliance). Flagged in the derivation JSON.
- DemographicAdapter produces narrower variance than astrology (country→trait lookup); works best combined with per-agent variable signal.
- Scalability ceiling: ~500 agents × 10 ticks / minute on the current Python+numpy path. 10K+ agents need Cython/Rust core.
