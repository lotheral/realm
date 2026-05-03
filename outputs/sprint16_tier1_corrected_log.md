# Sprint 15 Calibration Log — 2026-05-03 18:47 UTC

Scale: 200 agents × 30 ticks × 5 branches × 10 runs/category
Wall-clock: 638.8s

## Per-category baseline probability (mean / std / range)

| category | mean | std | min | max | n |
|----------|------|-----|-----|-----|---|
| politics | 50.08% | 0.22pp | 49.70% | 50.42% | 10 |
| economics | 50.08% | 0.26pp | 49.70% | 50.51% | 10 |
| crypto | 51.27% | 0.52pp | 50.39% | 52.16% | 10 |
| sports | 51.91% | 0.56pp | 51.30% | 52.92% | 10 |
| markets | 51.94% | 0.38pp | 51.33% | 52.47% | 10 |
| culture | 51.85% | 0.47pp | 50.94% | 52.67% | 10 |
| science | 53.38% | 0.68pp | 52.37% | 54.44% | 10 |
| geopolitics | 49.92% | 0.19pp | 49.57% | 50.20% | 10 |

## Acceptance gates

- **Spread**: max(mean) − min(mean) = **3.47pp** (target ≥ 3pp) ✅
  - widest baseline: **science** 53.38%
  - narrowest baseline: **geopolitics** 49.92%

- ✅ crypto std > politics std (volatility ordering)
- ✅ geopolitics mean < 50% (status quo bias)
- ✅ science mean > 50% (progress bias)

## Per-category bucket breakdown

Average supporting / opposing / neutral % across runs:

| category | sup% | opp% | neu% |
|----------|------|------|------|
| politics | 31.8 | 29.4 | 38.8 |
| economics | 29.0 | 33.0 | 38.0 |
| crypto | 33.6 | 26.8 | 39.6 |
| sports | 36.5 | 23.5 | 40.0 |
| markets | 39.8 | 23.2 | 37.0 |
| culture | 39.3 | 23.8 | 36.9 |
| science | 40.4 | 22.2 | 37.3 |
| geopolitics | 29.9 | 33.5 | 36.5 |
