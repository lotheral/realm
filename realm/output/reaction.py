"""Reaction distribution — REALM's first-class output (Sprint 21).

Design decision #1 (2026-08-18): the product answer to "if event X happens,
how does population P react?" is a distribution — stance shares plus their
shift against the no-event baseline, broken down by segment — with any
probability number derived, not primary.

This module pools per-agent weighted trait deviations across ALL branch
sims (the api layer previously bucketed only the last branch) and derives:

* total stance shares (support / oppose / neutral),
* per-segment shares along country / region / age-band / gender,
* one global bucket threshold so segment shares stay comparable.

The four helpers at the top are the former private functions of
``realm/api/predict.py``; they moved here so the reaction math has a
single owner. ``api/predict.py`` re-imports them under the old names.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

BUCKET_MIN_THRESHOLD = 0.005  # avoids all-neutral degenerate split when σ≈0

_AGE_BANDS: tuple[tuple[int, int, str], ...] = (
    (18, 29, "18-29"),
    (30, 44, "30-44"),
    (45, 59, "45-59"),
    (60, 200, "60+"),
)

SEGMENT_DIMENSIONS = ("country", "region", "age_band", "gender")


def age_band(age: int) -> str:
    for lo, hi, label in _AGE_BANDS:
        if lo <= age <= hi:
            return label
    return _AGE_BANDS[0][2] if age < 18 else _AGE_BANDS[-1][2]


# ---- Helpers moved from realm/api/predict.py (Sprint 21) ------------------


def category_weights(category: Any) -> dict[str, float]:
    weighted: dict[str, float] = {}
    for trait in category.primary_traits:
        weighted[trait] = 2.0
    for trait in category.secondary_traits:
        weighted.setdefault(trait, 1.0)
    for trait in category.suppressed_traits:
        weighted.setdefault(trait, 0.25)
    if not weighted:
        # Pure balanced category — equal weight on every TraitVector axis so
        # the calibrator still has something to compare against.
        from realm.personality.trait_vector import TraitVector

        weighted = dict.fromkeys(TraitVector.trait_names(), 1.0)
    return weighted


def effective_traits(sim: Any, agent: Any):
    """Drift-applied trait vector when an ExperienceDriftEngine is attached,
    else the raw immutable traits."""
    eng = getattr(sim, "drift_engine", None)
    if eng is not None:
        return eng.current_traits(agent)
    return agent.traits


def per_agent_deviations(
    sim: Any, baseline_means: Mapping[str, float], weights: Mapping[str, float],
) -> list[float]:
    wsum = sum(weights.values()) or 1.0
    devs: list[float] = []
    for agent in sim.agents:
        eff = effective_traits(sim, agent)
        score = sum(
            w * (float(getattr(eff, t, 0.5)) - baseline_means.get(t, 0.5))
            for t, w in weights.items()
        ) / wsum
        devs.append(score)
    return devs


def bucket_three_way(
    devs: Sequence[float], threshold: float | None = None,
) -> tuple[float, float, float]:
    if not devs:
        return (0.34, 0.33, 0.33)
    if threshold is None:
        sigma = statistics.pstdev(devs) if len(devs) > 1 else 0.0
        threshold = max(BUCKET_MIN_THRESHOLD, 0.5 * sigma)
    sup = sum(1 for d in devs if d > threshold)
    opp = sum(1 for d in devs if d < -threshold)
    neu = len(devs) - sup - opp
    n = float(len(devs))
    return (sup / n, opp / n, neu / n)


# ---- Reaction distribution -------------------------------------------------


@dataclass(frozen=True, slots=True)
class StanceShares:
    support: float
    oppose: float
    neutral: float


@dataclass(frozen=True, slots=True)
class SegmentReaction:
    dimension: str          # "country" | "region" | "age_band" | "gender"
    segment: str            # e.g. "TR", "europe_west", "18-29", "F"
    n_agents: int           # pooled sample count (across all branches)
    shares: StanceShares
    mean_deviation: float


@dataclass(frozen=True, slots=True)
class ReactionDistribution:
    stances: StanceShares
    n_agents: int           # total pooled samples = n_branches * n_agents
    mean_deviation: float
    threshold: float        # the global bucket threshold used everywhere
    segments: tuple[SegmentReaction, ...]


def stance_shift(scenario: StanceShares, baseline: StanceShares) -> StanceShares:
    return StanceShares(
        support=scenario.support - baseline.support,
        oppose=scenario.oppose - baseline.oppose,
        neutral=scenario.neutral - baseline.neutral,
    )


def _segment_key(profile: Any, dimension: str) -> str:
    if dimension == "country":
        return str(profile.country)
    if dimension == "region":
        return str(profile.region)
    if dimension == "age_band":
        return age_band(int(profile.age_years))
    return str(profile.gender)


def compute_reaction_distribution(
    sims: Sequence[Any],
    baseline_means: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    min_segment_size: int = 5,
    max_segments_per_dimension: int = 6,
) -> ReactionDistribution:
    """Pool per-agent deviations across all branch sims into a distribution.

    One global threshold (``max(BUCKET_MIN_THRESHOLD, 0.5σ)`` of the POOLED
    deviations) is applied to the total and to every segment, so segment
    shares are directly comparable.
    """
    pooled: list[tuple[float, Any]] = []
    for sim in sims:
        devs = per_agent_deviations(sim, baseline_means, weights)
        for dev, agent in zip(devs, sim.agents, strict=True):
            pooled.append((dev, agent.profile))

    if not pooled:
        return ReactionDistribution(
            stances=StanceShares(0.34, 0.33, 0.33),
            n_agents=0, mean_deviation=0.0,
            threshold=BUCKET_MIN_THRESHOLD, segments=(),
        )

    all_devs = [d for d, _ in pooled]
    sigma = statistics.pstdev(all_devs) if len(all_devs) > 1 else 0.0
    threshold = max(BUCKET_MIN_THRESHOLD, 0.5 * sigma)
    sup, opp, neu = bucket_three_way(all_devs, threshold=threshold)

    segments: list[SegmentReaction] = []
    for dimension in SEGMENT_DIMENSIONS:
        groups: dict[str, list[float]] = {}
        for dev, profile in pooled:
            groups.setdefault(_segment_key(profile, dimension), []).append(dev)
        sized = sorted(
            ((k, v) for k, v in groups.items() if len(v) >= min_segment_size),
            key=lambda kv: (-len(kv[1]), kv[0]),
        )[:max_segments_per_dimension]
        for segment, devs in sized:
            s_sup, s_opp, s_neu = bucket_three_way(devs, threshold=threshold)
            segments.append(SegmentReaction(
                dimension=dimension, segment=segment, n_agents=len(devs),
                shares=StanceShares(s_sup, s_opp, s_neu),
                mean_deviation=statistics.mean(devs),
            ))

    return ReactionDistribution(
        stances=StanceShares(sup, opp, neu),
        n_agents=len(pooled),
        mean_deviation=statistics.mean(all_devs),
        threshold=threshold,
        segments=tuple(segments),
    )
