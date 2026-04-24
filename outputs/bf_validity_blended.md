# BlendedAdapter validity study

N=5000, seed=42.

Blend config: big_five=0.6, astrological=0.4, σ=0.05.

## Per-trait distribution (cal OFF vs cal ON)

| trait | mean off | std off | mean on | std on | meets >0.05? |
|-------|----------|---------|---------|--------|--------------|
| openness | 0.626 | 0.118 | 0.497 | 0.174 | yes |
| conscientiousness | 0.650 | 0.119 | 0.503 | 0.173 | yes |
| extraversion | 0.651 | 0.117 | 0.504 | 0.167 | yes |
| agreeableness | 0.646 | 0.118 | 0.501 | 0.168 | yes |
| neuroticism | 0.623 | 0.115 | 0.492 | 0.171 | yes |
| risk_appetite | 0.623 | 0.085 | 0.496 | 0.168 | yes |
| analytical_depth | 0.620 | 0.081 | 0.497 | 0.174 | yes |
| impulsivity | 0.577 | 0.085 | 0.501 | 0.171 | yes |
| patience | 0.552 | 0.088 | 0.498 | 0.173 | yes |
| social_dominance | 0.663 | 0.076 | 0.499 | 0.168 | yes |
| herd_susceptibility | 0.641 | 0.063 | 0.494 | 0.173 | yes |
| authority_compliance | 0.561 | 0.074 | 0.500 | 0.174 | yes |
| contrarian_tendency | 0.586 | 0.071 | 0.500 | 0.173 | yes |
| empathy | 0.699 | 0.072 | 0.500 | 0.167 | yes |
| financial_optimism | 0.623 | 0.076 | 0.504 | 0.169 | yes |
| loss_aversion | 0.573 | 0.068 | 0.501 | 0.172 | yes |
| fomo_susceptibility | 0.499 | 0.053 | 0.504 | 0.171 | yes |
| communication_assertiveness | 0.590 | 0.074 | 0.501 | 0.170 | yes |
| persuasion_skill | 0.665 | 0.070 | 0.500 | 0.167 | yes |
| information_sharing | 0.590 | 0.071 | 0.500 | 0.174 | yes |
| political_spectrum | 0.500 | 0.050 | 0.500 | 0.170 | no |
| tradition_vs_progress | 0.539 | 0.055 | 0.495 | 0.170 | yes |
| individualism | 0.570 | 0.071 | 0.503 | 0.171 | yes |
| spirituality | 0.581 | 0.056 | 0.499 | 0.171 | yes |

## Success criteria (blended pipeline)

| # | criterion | measurement | result |
|---|-----------|-------------|--------|
| 1 | Mean trait std >= 0.14 (cal ON) | 0.171 | PASS |
| 4a | Derived 13 traits all std > 0.05 (cal OFF) | min = 0.068 | PASS |
| 4b | Derived 13 traits all std > 0.05 (cal ON) | min = 0.167 | PASS |

**3/3 criteria passed.**
