# Facet-Level Validation Report

Audit of facet-specific citations embedded in `data/personality/big_five_derivation.json` against the Johnson IPIP-NEO-120 dataset (N=612,595 respondents, from 619,150 parsed).

**Source of facet scoring:** [data/personality/ipip_neo_120_scoring_key.json](../data/personality/ipip_neo_120_scoring_key.json)

## Criteria per cited facet

- **Variance:** std(facet) >= 0.05 on the Johnson sample.
- **Domain loading:** Pearson r(facet, parent_domain) >= 0.50 — facet actually loads on its claimed parent domain.
- **Direction:** sign of REALM's coefficient on the parent domain agrees with sign of corr(facet, REALM's synthetic trait output).

## Summary: 13 PASS, 0 WARN, 0 FAIL across 13 derived traits.

## Per-trait results

| trait | cited facets | overall | notes |
|-------|--------------|---------|-------|
| risk_appetite | C6, E5, N1, N5 | **PASS** | C6:PASS, E5:PASS, N1:PASS, N5:PASS |
| analytical_depth | C6, O5 | **PASS** | C6:PASS, O5:PASS |
| impulsivity | C6, E5, N5 | **PASS** | C6:PASS, E5:PASS, N5:PASS |
| patience | C5, N5 | **PASS** | C5:PASS, N5:PASS |
| social_dominance | A4, E3 | **PASS** | A4:PASS, E3:PASS |
| empathy | A3, A6 | **PASS** | A3:PASS, A6:PASS |
| loss_aversion | C6, E5, N1, N3 | **PASS** | C6:PASS, E5:PASS, N1:PASS, N3:PASS |
| financial_optimism | E6, N3 | **PASS** | E6:PASS, N3:PASS |
| communication_assertiveness | E3 | **PASS** | E3:PASS |
| persuasion_skill | E1, E3, E6 | **PASS** | E1:PASS, E3:PASS, E6:PASS |
| information_sharing | E2, O5 | **PASS** | E2:PASS, O5:PASS |
| contrarian_tendency | A4 | **PASS** | A4:PASS |
| authority_compliance | A4, C3, O6 | **PASS** | A4:PASS, C3:PASS, O6:PASS |

## Detailed facet checks

### risk_appetite — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| C6 | 0.259 | +0.686 | -0.15 | -0.174 | match | PASS |
| E5 | 0.212 | +0.556 | +0.20 | +0.536 | match | PASS |
| N1 | 0.236 | +0.825 | -0.25 | -0.535 | match | PASS |
| N5 | 0.210 | +0.501 | -0.25 | -0.059 | match | PASS |

### analytical_depth — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| C6 | 0.259 | +0.686 | +0.30 | +0.427 | match | PASS |
| O5 | 0.223 | +0.689 | +0.40 | +0.606 | match | PASS |

### impulsivity — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| C6 | 0.259 | +0.686 | -0.30 | -0.679 | match | PASS |
| E5 | 0.212 | +0.556 | +0.20 | +0.362 | match | PASS |
| N5 | 0.210 | +0.501 | +0.35 | +0.593 | match | PASS |

### patience — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| C5 | 0.201 | +0.814 | +0.40 | +0.753 | match | PASS |
| N5 | 0.210 | +0.501 | -0.25 | -0.555 | match | PASS |

### social_dominance — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| A4 | 0.230 | +0.713 | -0.25 | -0.409 | match | PASS |
| E3 | 0.218 | +0.620 | +0.40 | +0.613 | match | PASS |

### empathy — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| A3 | 0.166 | +0.720 | +0.45 | +0.697 | match | PASS |
| A6 | 0.195 | +0.662 | +0.45 | +0.669 | match | PASS |

### loss_aversion — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| C6 | 0.259 | +0.686 | +0.15 | +0.009 | match | PASS |
| E5 | 0.212 | +0.556 | -0.10 | -0.337 | match | PASS |
| N1 | 0.236 | +0.825 | +0.30 | +0.762 | match | PASS |
| N3 | 0.245 | +0.782 | +0.30 | +0.715 | match | PASS |

### financial_optimism — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| E6 | 0.204 | +0.729 | +0.30 | +0.726 | match | PASS |
| N3 | 0.245 | +0.782 | -0.30 | -0.733 | match | PASS |

### communication_assertiveness — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| E3 | 0.218 | +0.620 | +0.40 | +0.636 | match | PASS |

### persuasion_skill — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| E1 | 0.224 | +0.813 | +0.35 | +0.790 | match | PASS |
| E3 | 0.218 | +0.620 | +0.35 | +0.517 | match | PASS |
| E6 | 0.204 | +0.729 | +0.35 | +0.726 | match | PASS |

### information_sharing — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| E2 | 0.252 | +0.809 | +0.25 | +0.635 | match | PASS |
| O5 | 0.223 | +0.689 | +0.20 | +0.387 | match | PASS |

### contrarian_tendency — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| A4 | 0.230 | +0.713 | -0.30 | -0.676 | match | PASS |

### authority_compliance — overall **PASS**

| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |
|-------|-----|------------------|-------------|-----------------|-----------|--------|
| A4 | 0.230 | +0.713 | +0.25 | +0.626 | match | PASS |
| C3 | 0.168 | +0.679 | +0.20 | +0.696 | match | PASS |
| O6 | 0.214 | +0.523 | -0.15 | -0.281 | match | PASS |

## Honest limitations

- IPIP-NEO-120 has only 4 items per facet. Short facet scales are noisier than the full 10-item IPIP-NEO-300 versions, so direction-check failures on small REALM coefficients (|β|<0.15) should be read as WARN not FAIL.
- REALM's `BigFiveAdapter` derives traits from domain scores only; the facet→trait correlation is therefore a proxy for whether the cited facet would add information above its parent domain if REALM switched to facet-level inputs. Near-zero direction r reflects the single-domain derivation, not an error in citation.
- Facet citations that survive all three checks here are candidates for promotion to per-facet coefficients in a follow-up sprint. See `data/personality/big_five_derivation_facets_draft.json` for the draft proposal emitted by `scripts/draft_facet_coefficients.py`.
