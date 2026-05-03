# Sprint 15 Calibration Log — 2026-05-03 20:28 UTC

Scale: 200 agents × 30 ticks × 5 branches × 10 runs/category
Wall-clock: 752.8s

## Per-category baseline probability (mean / std / range)

| category | mean | std | min | max | n |
|----------|------|-----|-----|-----|---|
| politics | 50.00% | 0.22pp | 49.61% | 50.34% | 10 |
| economics | 49.90% | 0.26pp | 49.52% | 50.33% | 10 |
| crypto | 50.96% | 0.52pp | 50.08% | 51.84% | 10 |
| sports | 51.72% | 0.56pp | 51.10% | 52.72% | 10 |
| markets | 51.83% | 0.37pp | 51.22% | 52.36% | 10 |
| culture | 51.84% | 0.47pp | 50.93% | 52.67% | 10 |
| science | 53.34% | 0.68pp | 52.32% | 54.39% | 10 |
| geopolitics | 49.20% | 0.19pp | 48.85% | 49.49% | 10 |

## Acceptance gates

- **Spread**: max(mean) − min(mean) = **4.14pp** (target ≥ 3pp) ✅
  - widest baseline: **science** 53.34%
  - narrowest baseline: **geopolitics** 49.20%

- ✅ crypto std > politics std (volatility ordering)
- ✅ geopolitics mean < 50% (status quo bias)
- ✅ science mean > 50% (progress bias)

## Per-category bucket breakdown

Average supporting / opposing / neutral % across runs:

| category | sup% | opp% | neu% |
|----------|------|------|------|
| politics | 30.8 | 30.7 | 38.5 |
| economics | 27.5 | 35.0 | 37.5 |
| crypto | 32.2 | 27.7 | 40.0 |
| sports | 35.8 | 24.3 | 39.9 |
| markets | 39.1 | 23.6 | 37.3 |
| culture | 39.4 | 23.8 | 36.8 |
| science | 40.2 | 22.5 | 37.2 |
| geopolitics | 28.2 | 35.8 | 36.0 |
