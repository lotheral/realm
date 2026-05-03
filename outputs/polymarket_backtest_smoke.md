# REALM Polymarket Backtest Report — 2026-05-03 21:49 UTC

Markets evaluated: **5**  ·  Scale: 50 agents × 10 ticks × 3 branches  ·  Wall-clock: 90.0s (18.0s/market)

## Brier scores (lower is better; perfect = 0, worst = 1)

| Method          | Mean   | Median | Std    | n  |
|-----------------|--------|--------|--------|----|
| Polymarket      | 0.0000 | 0.0000 | 0.0000 |  5 |
| REALM (LLM+sim) | 0.1649 | 0.1527 | 0.0390 |  5 |
| LLM only        | 0.1168 | 0.0784 | 0.0609 |  5 |
| Sim only        | 0.2471 | 0.2482 | 0.0083 |  5 |

## Does the simulation add value?

**Brier(LLM+sim) − Brier(LLM-only) = +0.0481**

❌ Simulation HURTS — LLM-only would be more accurate.

## Worst REALM predictions (highest Brier)

- (YES) realm=0.54 poly=1.00  brier=0.211  "How many confirmed Coronavirus cases will there be at EOY in the USA?"
- (NO) realm=0.46 poly=0.00  brier=0.211  "Will Trump win the 2020 U.S. presidential election?"
- (NO) realm=0.39 poly=0.00  brier=0.153  "Will Kim Kardashian and Kanye West divorce before Jan 1, 2021?"
- (NO) realm=0.36 poly=0.00  brier=0.129  "Will there be a federal charge filed against Hunter Biden before 2021?"
- (NO) realm=0.35 poly=0.00  brier=0.121  "Will Coinbase begin publicly trading before Jan 1, 2021?"

## Best REALM predictions (lowest Brier)

- (NO) realm=0.35 poly=0.00  brier=0.121  "Will Coinbase begin publicly trading before Jan 1, 2021?"
- (NO) realm=0.36 poly=0.00  brier=0.129  "Will there be a federal charge filed against Hunter Biden before 2021?"
- (NO) realm=0.39 poly=0.00  brier=0.153  "Will Kim Kardashian and Kanye West divorce before Jan 1, 2021?"
- (NO) realm=0.46 poly=0.00  brier=0.211  "Will Trump win the 2020 U.S. presidential election?"
- (YES) realm=0.54 poly=1.00  brier=0.211  "How many confirmed Coronavirus cases will there be at EOY in the USA?"

## Per-market detail

| outcome | realm | llm | sim | poly | question |
|--------|-------|-----|-----|------|----------|
| NO | 0.39 | 0.28 | 0.50 | 0.00 | Will Kim Kardashian and Kanye West divorce before Jan 1, 2021? |
| NO | 0.35 | 0.28 | 0.51 | 0.00 | Will Coinbase begin publicly trading before Jan 1, 2021? |
| NO | 0.46 | 0.42 | 0.50 | 0.00 | Will Trump win the 2020 U.S. presidential election? |
| YES | 0.54 | 0.55 | 0.52 | 1.00 | How many confirmed Coronavirus cases will there be at EOY in the USA? |
| NO | 0.36 | 0.22 | 0.50 | 0.00 | Will there be a federal charge filed against Hunter Biden before 2021? |
