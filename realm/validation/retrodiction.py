"""Pure-python retrodiction metrics for Study A (Sprint 22, design §4.1).

No scipy dependency — the binomial test is exact via ``math.comb`` and
Spearman is Pearson-on-average-ranks, both trivial at Study A's N (15-30).

Metric semantics (locked in the Sprint 22 plan):

* a directional HIT is ``sign(predicted) == sign(observed)`` with both
  nonzero;
* a zero prediction carries no direction → counted as a miss AND
  reported separately in ``zero_predictions`` (the model refusing to
  move must not be hidden inside the accuracy number);
* the binomial p-value is one-sided vs the 50% coin-flip null:
  ``P(X >= hits | n, p=0.5)``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DirectionalResult:
    hits: int
    misses: int
    zero_predictions: int
    n: int
    accuracy: float
    p_value_one_sided: float


def binomial_p_one_sided(hits: int, n: int) -> float:
    """Exact P(X >= hits) for X ~ Binomial(n, 0.5)."""
    if n <= 0:
        return 1.0
    total = sum(math.comb(n, k) for k in range(hits, n + 1))
    return total / (2 ** n)


def directional_accuracy(
    predicted: Sequence[float], observed: Sequence[float],
) -> DirectionalResult:
    if len(predicted) != len(observed):
        raise ValueError("predicted and observed must have equal length")
    hits = misses = zeros = 0
    for pred, obs in zip(predicted, observed, strict=True):
        if pred == 0.0:
            zeros += 1
            misses += 1
        elif obs != 0.0 and (pred > 0) == (obs > 0):
            hits += 1
        else:
            misses += 1
    n = len(predicted)
    return DirectionalResult(
        hits=hits,
        misses=misses,
        zero_predictions=zeros,
        n=n,
        accuracy=(hits / n) if n else 0.0,
        p_value_one_sided=binomial_p_one_sided(hits, n),
    )


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation with average ranks on ties.

    Returns 0.0 when n < 3 or either side has zero rank variance —
    an honest "no measurable monotone relation" rather than NaN.
    """
    if len(xs) != len(ys):
        raise ValueError("xs and ys must have equal length")
    n = len(xs)
    if n < 3:
        return 0.0
    rx = _average_ranks(xs)
    ry = _average_ranks(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


def breakdown(
    events: Sequence[Any],
    predicted: Sequence[float],
    observed: Sequence[float],
    key: Callable[[Any], str] = lambda e: e.confidence,
) -> dict[str, DirectionalResult]:
    """Directional accuracy per group (default: authorship confidence)."""
    groups: dict[str, tuple[list[float], list[float]]] = {}
    for event, pred, obs in zip(events, predicted, observed, strict=True):
        bucket = groups.setdefault(key(event), ([], []))
        bucket[0].append(pred)
        bucket[1].append(obs)
    return {
        name: directional_accuracy(preds, obss)
        for name, (preds, obss) in groups.items()
    }
