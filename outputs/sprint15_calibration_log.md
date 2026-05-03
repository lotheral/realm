# Sprint 15 Calibration Log — 2026-04-25 22:10 UTC

Scale: 200 agents × 30 ticks × 5 branches × 5 runs/category
Wall-clock: 518.8s

## Per-category baseline probability (mean / std / range)

| category | mean | std | min | max | n |
|----------|------|-----|-----|-----|---|
| politics | 50.21% | 0.24pp | 49.89% | 50.59% | 5 |
| economics | 50.50% | 0.21pp | 50.24% | 50.76% | 5 |
| crypto | 50.76% | 0.60pp | 49.96% | 51.73% | 5 |
| sports | 51.79% | 0.58pp | 51.28% | 52.88% | 5 |
| markets | 52.20% | 0.35pp | 51.70% | 52.63% | 5 |
| culture | 51.56% | 0.62pp | 50.67% | 52.39% | 5 |
| science | 54.21% | 0.42pp | 53.56% | 54.86% | 5 |
| geopolitics | 50.10% | 0.19pp | 49.81% | 50.32% | 5 |

## Acceptance gates

- **Spread**: max(mean) − min(mean) = **4.11pp** (target ≥ 3pp) ✅
  - widest baseline: **science** 54.21%
  - narrowest baseline: **geopolitics** 50.10%

- ✅ crypto std > politics std (volatility ordering)
- ⚠️ geopolitics mean 50.10% ≥ 50% — asymmetry not biting
- ✅ science mean > 50% (progress bias)

## Per-category bucket breakdown

Average supporting / opposing / neutral % across runs:

| category | sup% | opp% | neu% |
|----------|------|------|------|
| politics | 35.2 | 27.1 | 37.7 |
| economics | 33.5 | 27.2 | 39.3 |
| crypto | 32.9 | 27.5 | 39.6 |
| sports | 37.3 | 22.2 | 40.5 |
| markets | 44.2 | 20.5 | 35.3 |
| culture | 40.1 | 24.6 | 35.3 |
| science | 44.9 | 19.5 | 35.6 |
| geopolitics | 33.5 | 28.9 | 37.6 |
