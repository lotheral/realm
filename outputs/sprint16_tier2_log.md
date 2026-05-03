# Sprint 15 Calibration Log — 2026-05-03 18:31 UTC

Scale: 200 agents × 30 ticks × 5 branches × 10 runs/category
Wall-clock: 580.7s

## Per-category baseline probability (mean / std / range)

| category | mean | std | min | max | n |
|----------|------|-----|-----|-----|---|
| politics | 50.09% | 0.22pp | 49.71% | 50.43% | 10 |
| economics | 50.11% | 0.26pp | 49.73% | 50.53% | 10 |
| crypto | 50.50% | 0.51pp | 49.64% | 51.40% | 10 |
| sports | 51.47% | 0.55pp | 50.87% | 52.47% | 10 |
| markets | 51.50% | 0.36pp | 50.90% | 52.00% | 10 |
| culture | 51.40% | 0.46pp | 50.52% | 52.22% | 10 |
| science | 53.25% | 0.68pp | 52.23% | 54.31% | 10 |
| geopolitics | 49.98% | 0.19pp | 49.64% | 50.27% | 10 |

## Acceptance gates

- **Spread**: max(mean) − min(mean) = **3.27pp** (target ≥ 3pp) ✅
  - widest baseline: **science** 53.25%
  - narrowest baseline: **geopolitics** 49.98%

- ✅ crypto std > politics std (volatility ordering)
- ✅ geopolitics mean < 50% (status quo bias)
- ✅ science mean > 50% (progress bias)

## Per-category bucket breakdown

Average supporting / opposing / neutral % across runs:

| category | sup% | opp% | neu% |
|----------|------|------|------|
| politics | 31.8 | 29.1 | 39.1 |
| economics | 29.3 | 33.0 | 37.8 |
| crypto | 30.9 | 29.3 | 39.8 |
| sports | 34.9 | 24.9 | 40.2 |
| markets | 37.2 | 25.7 | 37.1 |
| culture | 37.4 | 25.6 | 37.1 |
| science | 39.8 | 22.9 | 37.4 |
| geopolitics | 30.9 | 32.8 | 36.3 |
