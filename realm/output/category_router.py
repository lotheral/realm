"""Prediction category routing for question-driven trait weighting.

Routes a free-text prediction question into one of nine categories defined in
``config/prediction_categories.json``. Each category carries primary / secondary
/ suppressed trait lists, used by ``observe_category_consensus`` in
``realm.output.predictor`` to compute a weighted multi-trait population mean
per simulation branch.

Routing strategy (Sprint 17 — LLM-first):
    1. If an ``ILLMBackend`` is wired, ask the LLM to classify the question
       (3-second timeout, in-process cache for repeated questions). Use the
       result when ``confidence > 0.5`` and the returned category id is valid.
    2. Otherwise (no LLM, LLM timeout/error, low confidence, invalid id):
       fall back to keyword matching — best ≥ 2 hits AND best ≥ 2× second-best
       returns immediately, single-hit returns as low-confidence match,
       no hits at all → balanced fallback.

The keyword path is bit-for-bit the pre-Sprint-17 behavior — when the LLM
backend is None (default in tests, default when the env var
``REALM_LLM_CATEGORY_BACKEND`` is unset), routing decisions are unchanged
from Sprint 16.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_split_prompt
from realm.llm.router import TASK_CATEGORY, LLMRouter, is_llm_configured
from realm.personality.trait_vector import TraitVector

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "prediction_categories.json"
_BALANCED_ID = "balanced"
_LLM_ENABLE_ENV = "REALM_LLM_CATEGORY_BACKEND"
_AMBIGUITY_RATIO = 2.0
_MIN_CONFIDENT_HITS = 2

# Sprint 17: LLM-first routing constants.
# Per-call timeout for the classifier — most modern chat models return in
# 1-3s for a short JSON response, so 3s catches genuine hangs while still
# allowing typical latency. On timeout the router falls back to keywords
# without surfacing the slowness to the API caller.
_LLM_ROUTE_TIMEOUT_SEC = 3.0
# Confidence floor below which the LLM result is treated as low-quality
# and the keyword path is consulted as a tiebreaker / fallback.
_LLM_ROUTE_CONFIDENCE_FLOOR = 0.5

# Sprint 14 WP1 / Sprint 16: the 15 canonical drift event identifiers from
# config/drift_events.json. Every category's drift_event_weights map MUST
# cover all 15 (no zeros — even unlikely events stay sampleable). Sprint 16
# added regime_consolidation, diplomatic_stalemate, sanctions_pressure to
# fix the geopolitics structural positive bias.
_DRIFT_EVENT_TYPES: tuple[str, ...] = (
    "positive_social", "negative_social",
    "successful_risk", "failed_risk",
    "knowledge_acquisition", "stress_crisis",
    "leadership_act", "group_conformity", "group_dissent",
    "financial_loss", "financial_gain", "cultural_experience",
    "regime_consolidation", "diplomatic_stalemate", "sanctions_pressure",
)

# Sprint 14 WP2: zero-sum tolerance and per-trait magnitude cap on offsets.
_SEED_OFFSET_SUM_TOLERANCE = 0.01
_SEED_OFFSET_MAX_MAGNITUDE = 0.05

# Sprint 15 WP1: validation ranges for the new differentiation fields.
# v0.15.1 hotfix: widened _ASYMMETRY_RANGE 0.5-1.5 → 0.3-1.7 so domains with
# strong status-quo bias (geopolitics) can push below 50%; the original tight
# range saturated the geopolitics calibration at 50.43% (target was <50%).
_DRIFT_VOLATILITY_RANGE = (0.5, 2.0)
_ASYMMETRY_RANGE = (0.3, 1.7)
_SIGMOID_SENS_MULT_RANGE = (0.5, 2.0)

# Sprint 16 WP2: per-category last-mile probability offset applied after
# sigmoid + clamp in realm/api/predict.py. Bounded so it stays a fine-tuning
# knob (cannot dominate the underlying drift signal); use only when the
# drift mechanics alone cannot reach a category's calibration target.
_OFFSET_RANGE = (-0.05, 0.05)

# Sprint 17 WP2: per-category blend weight for the LLM prior vs the
# simulation probability. Final probability when both are available is
#   final = (1 - w) * sim_prob + w * llm_prior.
# Higher w (e.g. 0.7 for science / economics) leans on the LLM's factual
# context; lower w (e.g. 0.3 for crypto) keeps the swarm-sentiment signal
# dominant. Defaults to 0.5 if not configured. When llm_prior is None
# (no LLM, analyzer failed) the simulation probability is used directly.
_LLM_BLEND_RANGE = (0.0, 1.0)


@dataclass(frozen=True)
class CategoryMatch:
    """The result of routing a question to a category."""

    category_id: str
    label: str
    confidence: float
    matched_keywords: tuple[str, ...]
    primary_traits: tuple[str, ...]
    secondary_traits: tuple[str, ...]
    suppressed_traits: tuple[str, ...]
    default_horizon_ticks: int
    subcategory: str | None = None
    fallback: bool = False
    llm_used: bool = False
    # Sprint 14 WP1: relative weights for the 12 drift event types,
    # consumed by DriftEventBridge weighted sampling.
    drift_event_weights: tuple[tuple[str, float], ...] = ()
    # Sprint 14 WP2: zero-sum trait offsets applied at agent-build time
    # so the starting population reflects the question's domain emphasis.
    trait_seed_offsets: tuple[tuple[str, float], ...] = ()
    # Sprint 15 WP1-WP4: per-category baseline differentiation knobs.
    # drift_volatility scales ExperienceDriftEngine.max_drift_ratio (0.10
    # by default → 0.10 × volatility). drift_asymmetry scales per-trait
    # deltas by sign (positive deltas × pos_mul, negative × neg_mul).
    # sigmoid_sensitivity_multiplier scales the predict.py sigmoid base
    # (8.0 by default). All three default to 1.0 (Sprint 14 behavior).
    drift_volatility: float = 1.0
    drift_asymmetry_positive: float = 1.0
    drift_asymmetry_negative: float = 1.0
    sigmoid_sensitivity_multiplier: float = 1.0
    # Sprint 16 WP2: last-mile probability offset added to the sigmoid
    # output (see realm/api/predict.py). Defaults to 0.0 (no offset).
    baseline_probability_offset: float = 0.0
    # Sprint 17 WP2 / Sprint 19 WP1: LLM weight in the BASELINE
    # probability blend (scenario_feed not provided). Sprint 19 raised
    # baseline weights to 0.85-0.95 across all categories after Sprint 18
    # backtesting showed sim adds negative value to baseline predictions.
    # final = (1-w)*sim + w*llm_prior, clamped [0.05, 0.95].
    llm_blend_weight: float = 0.5
    # Sprint 19 WP1: separate LLM weight for SCENARIO predictions.
    # Defaults to 0.4 (sim 0.6) — scenario analysis is REALM's unique
    # value: agent perturbation, drift dynamics, trait clustering. The
    # LLM adjusts qualitative interpretation but the quantitative delta
    # comes from the simulation. Science overrides this to 0.5
    # (evidence still matters in scenarios for that category).
    scenario_llm_blend_weight: float = 0.4
    # Sprint 18 WP3: secondary categories with weights for cross-domain
    # questions. Empty tuple = single-category routing (today's path).
    # Populated only by the LLM router when it returns the multi-category
    # JSON form. Sum of secondary weights + primary's implied weight = 1.0.
    # Downstream (predict.py) blends drift_event_weights across the set
    # so cross-domain questions like "Strait of Hormuz traffic" pull
    # event physics from geopolitics + economics + markets simultaneously
    # rather than collapsing to "balanced".
    secondary_categories: tuple[tuple[str, float], ...] = ()


def _validate_categories(payload: Mapping[str, object]) -> tuple[dict, ...]:
    """Validate the prediction-categories JSON. Raises ValueError on bad data."""
    if not isinstance(payload, Mapping):
        raise ValueError("prediction_categories payload must be a mapping")
    cats = payload.get("categories")
    if not isinstance(cats, list) or not cats:
        raise ValueError("prediction_categories.categories must be a non-empty list")

    valid_traits = set(TraitVector.trait_names())
    seen_ids: set[str] = set()
    out: list[dict] = []
    for idx, cat in enumerate(cats):
        if not isinstance(cat, Mapping):
            raise ValueError(f"category #{idx} is not a mapping")
        cid = cat.get("id")
        if not isinstance(cid, str) or not cid:
            raise ValueError(f"category #{idx} has missing/invalid id")
        if cid in seen_ids:
            raise ValueError(f"duplicate category id: {cid!r}")
        seen_ids.add(cid)
        weights = cat.get("trait_weights") or {}
        for bucket_name in ("primary", "secondary", "suppressed"):
            bucket = weights.get(bucket_name) or []
            if not isinstance(bucket, list):
                raise ValueError(f"{cid}.trait_weights.{bucket_name} must be a list")
            unknown = [t for t in bucket if t not in valid_traits]
            if unknown:
                raise ValueError(
                    f"{cid}.trait_weights.{bucket_name} contains unknown traits: {unknown}"
                )
        if cid != _BALANCED_ID and not weights.get("primary"):
            raise ValueError(
                f"category {cid!r} must declare at least one primary trait"
            )

        # Sprint 14 WP1: validate drift_event_weights when present.
        dew = cat.get("drift_event_weights")
        if dew is not None:
            if not isinstance(dew, Mapping):
                raise ValueError(f"{cid}.drift_event_weights must be a mapping")
            missing = [e for e in _DRIFT_EVENT_TYPES if e not in dew]
            if missing:
                raise ValueError(
                    f"{cid}.drift_event_weights missing event types: {missing}"
                )
            unknown_events = [k for k in dew if k not in _DRIFT_EVENT_TYPES]
            if unknown_events:
                raise ValueError(
                    f"{cid}.drift_event_weights has unknown event types: {unknown_events}"
                )
            for ev, w in dew.items():
                if not isinstance(w, (int, float)) or w <= 0.0:
                    raise ValueError(
                        f"{cid}.drift_event_weights[{ev!r}]={w!r} must be a positive number"
                    )

        # Sprint 14 WP2: validate trait_seed_offsets when present.
        tso = cat.get("trait_seed_offsets")
        if tso is not None:
            if not isinstance(tso, Mapping):
                raise ValueError(f"{cid}.trait_seed_offsets must be a mapping")
            unknown_traits = [t for t in tso if t not in valid_traits]
            if unknown_traits:
                raise ValueError(
                    f"{cid}.trait_seed_offsets has unknown traits: {unknown_traits}"
                )
            for t, off in tso.items():
                if not isinstance(off, (int, float)):
                    raise ValueError(
                        f"{cid}.trait_seed_offsets[{t!r}]={off!r} must be numeric"
                    )
                if abs(float(off)) > _SEED_OFFSET_MAX_MAGNITUDE:
                    raise ValueError(
                        f"{cid}.trait_seed_offsets[{t!r}]={off!r} exceeds magnitude cap "
                        f"{_SEED_OFFSET_MAX_MAGNITUDE}"
                    )
            offset_sum = float(sum(tso.values()))
            if abs(offset_sum) > _SEED_OFFSET_SUM_TOLERANCE:
                raise ValueError(
                    f"{cid}.trait_seed_offsets is not zero-sum (sum={offset_sum:.4f}, "
                    f"tolerance={_SEED_OFFSET_SUM_TOLERANCE})"
                )

        # Sprint 15 WP1: validate per-category differentiation knobs.
        if "drift_volatility" in cat:
            v = cat["drift_volatility"]
            if not isinstance(v, (int, float)) or not (
                _DRIFT_VOLATILITY_RANGE[0] <= float(v) <= _DRIFT_VOLATILITY_RANGE[1]
            ):
                raise ValueError(
                    f"{cid}.drift_volatility={v!r} must be a number in "
                    f"{_DRIFT_VOLATILITY_RANGE}"
                )
        if "drift_asymmetry" in cat:
            asym = cat["drift_asymmetry"]
            if not isinstance(asym, Mapping):
                raise ValueError(f"{cid}.drift_asymmetry must be a mapping")
            for key in ("positive_multiplier", "negative_multiplier"):
                if key not in asym:
                    raise ValueError(f"{cid}.drift_asymmetry missing {key!r}")
                v = asym[key]
                if not isinstance(v, (int, float)) or not (
                    _ASYMMETRY_RANGE[0] <= float(v) <= _ASYMMETRY_RANGE[1]
                ):
                    raise ValueError(
                        f"{cid}.drift_asymmetry.{key}={v!r} must be in "
                        f"{_ASYMMETRY_RANGE}"
                    )
        if "sigmoid_sensitivity_multiplier" in cat:
            v = cat["sigmoid_sensitivity_multiplier"]
            if not isinstance(v, (int, float)) or not (
                _SIGMOID_SENS_MULT_RANGE[0] <= float(v) <= _SIGMOID_SENS_MULT_RANGE[1]
            ):
                raise ValueError(
                    f"{cid}.sigmoid_sensitivity_multiplier={v!r} must be in "
                    f"{_SIGMOID_SENS_MULT_RANGE}"
                )

        # Sprint 16 WP2: validate baseline_probability_offset when present.
        if "baseline_probability_offset" in cat:
            v = cat["baseline_probability_offset"]
            if not isinstance(v, (int, float)) or not (
                _OFFSET_RANGE[0] <= float(v) <= _OFFSET_RANGE[1]
            ):
                raise ValueError(
                    f"{cid}.baseline_probability_offset={v!r} must be in "
                    f"{_OFFSET_RANGE}"
                )

        # Sprint 17 WP2: validate llm_blend_weight when present.
        if "llm_blend_weight" in cat:
            v = cat["llm_blend_weight"]
            if not isinstance(v, (int, float)) or not (
                _LLM_BLEND_RANGE[0] <= float(v) <= _LLM_BLEND_RANGE[1]
            ):
                raise ValueError(
                    f"{cid}.llm_blend_weight={v!r} must be in {_LLM_BLEND_RANGE}"
                )

        # Sprint 19 WP1: validate scenario_llm_blend_weight when present.
        if "scenario_llm_blend_weight" in cat:
            v = cat["scenario_llm_blend_weight"]
            if not isinstance(v, (int, float)) or not (
                _LLM_BLEND_RANGE[0] <= float(v) <= _LLM_BLEND_RANGE[1]
            ):
                raise ValueError(
                    f"{cid}.scenario_llm_blend_weight={v!r} must be in {_LLM_BLEND_RANGE}"
                )

        out.append(dict(cat))

    if out[-1].get("id") != _BALANCED_ID:
        raise ValueError(
            f"the last category must be the {_BALANCED_ID!r} fallback (got {out[-1].get('id')!r})"
        )
    return tuple(out)


def load_categories(path: Path | None = None) -> tuple[dict, ...]:
    p = path or _DEFAULT_PATH
    payload = json.loads(p.read_text(encoding="utf-8"))
    return _validate_categories(payload)


_TOKEN_SPLIT = re.compile(r"[^a-z0-9$&\-]+")


def _normalize_question(text: str) -> str:
    return text.lower().strip()


_KEYWORD_CACHE: dict[str, re.Pattern[str]] = {}


def _keyword_pattern(kw: str) -> re.Pattern[str]:
    cached = _KEYWORD_CACHE.get(kw)
    if cached is not None:
        return cached
    # Word-boundary match avoids 'un' matching inside 'country', 'ai' inside
    # 'said', 'dow' inside 'downward', etc. Multi-word keywords (e.g. 'interest
    # rate') are handled correctly because re.escape preserves the space.
    # Optional trailing 's' so 'oscar' matches 'oscars', 'election' matches
    # 'elections', etc. — covers regular plural forms without per-keyword work.
    pattern = re.compile(r"\b" + re.escape(kw.lower()) + r"s?\b")
    _KEYWORD_CACHE[kw] = pattern
    return pattern


def _count_keyword_hits(question: str, keywords: Sequence[str]) -> tuple[int, tuple[str, ...]]:
    matched: list[str] = []
    for kw in keywords:
        if not kw:
            continue
        if _keyword_pattern(kw).search(question):
            matched.append(kw)
    return len(matched), tuple(matched)


def _detect_subcategory(question: str, subcategories: Sequence[str]) -> str | None:
    for sub in subcategories:
        if not sub:
            continue
        if sub.lower().replace("_", " ") in question or sub.lower() in question:
            return sub
    return None


def _build_match(
    cat: Mapping[str, object],
    *,
    confidence: float,
    matched: Sequence[str],
    subcategory: str | None,
    fallback: bool = False,
    llm_used: bool = False,
    secondary_categories: tuple[tuple[str, float], ...] = (),
) -> CategoryMatch:
    weights = cat.get("trait_weights") or {}
    dew = cat.get("drift_event_weights") or {}
    tso = cat.get("trait_seed_offsets") or {}
    asym = cat.get("drift_asymmetry") or {}
    return CategoryMatch(
        category_id=str(cat["id"]),
        label=str(cat.get("label", cat["id"])),
        confidence=confidence,
        matched_keywords=tuple(matched),
        primary_traits=tuple(weights.get("primary", []) or ()),
        secondary_traits=tuple(weights.get("secondary", []) or ()),
        suppressed_traits=tuple(weights.get("suppressed", []) or ()),
        default_horizon_ticks=int(cat.get("default_horizon_ticks", 30)),
        subcategory=subcategory,
        fallback=fallback,
        llm_used=llm_used,
        drift_event_weights=tuple((str(k), float(v)) for k, v in dew.items()),
        trait_seed_offsets=tuple((str(k), float(v)) for k, v in tso.items()),
        drift_volatility=float(cat.get("drift_volatility", 1.0)),
        drift_asymmetry_positive=float(asym.get("positive_multiplier", 1.0)),
        drift_asymmetry_negative=float(asym.get("negative_multiplier", 1.0)),
        sigmoid_sensitivity_multiplier=float(
            cat.get("sigmoid_sensitivity_multiplier", 1.0)
        ),
        baseline_probability_offset=float(
            cat.get("baseline_probability_offset", 0.0)
        ),
        llm_blend_weight=float(cat.get("llm_blend_weight", 0.5)),
        scenario_llm_blend_weight=float(
            cat.get("scenario_llm_blend_weight", 0.4)
        ),
        secondary_categories=secondary_categories,
    )


def _parse_multi_categories(
    raw: list, by_id: Mapping[str, dict],
) -> tuple[str, tuple[tuple[str, float], ...]] | None:
    """Sprint 18 WP3: parse the LLM's multi-category response.

    Input shape::

        [{"id": "geopolitics", "weight": 0.6},
         {"id": "economics",   "weight": 0.25},
         {"id": "markets",     "weight": 0.15}]

    Returns ``(primary_id, secondary)`` where:
    - ``primary_id`` is the highest-weight category in the list
    - ``secondary`` is a tuple of (id, weight) for the remaining
      categories — the primary's weight is implicit (1 - sum(secondary))

    Returns None if any entry has an unknown id, weights don't roughly
    sum to 1.0 (±0.05), or the list is empty after sanitization.
    """
    parsed: list[tuple[str, float]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        cid = str(entry.get("id", "")).strip()
        try:
            w = float(entry.get("weight", 0.0))
        except (TypeError, ValueError):
            continue
        if not cid or cid not in by_id or w <= 0.0:
            continue
        parsed.append((cid, w))
    if not parsed:
        return None

    # Sort by weight descending so primary is first
    parsed.sort(key=lambda x: x[1], reverse=True)

    total = sum(w for _, w in parsed)
    if not (0.95 <= total <= 1.05):
        # Weights should sum to ~1.0; rejecting a malformed list is
        # safer than silently re-normalizing.
        return None

    primary_id = parsed[0][0]
    secondary = tuple(parsed[1:])  # everything below the top weight
    return primary_id, secondary


def blend_category_parameters(
    primary_match: CategoryMatch,
    secondary_categories_data: Mapping[str, Mapping],
) -> dict:
    """Sprint 19 WP3: blend ALL category-dependent simulation parameters
    across the primary + secondary categories.

    Returns a dict with the same keys the predict_endpoint reads off
    ``category``: ``drift_event_weights`` (tuple of (id, weight)),
    ``drift_volatility``, ``drift_asymmetry_positive``,
    ``drift_asymmetry_negative``, ``sigmoid_sensitivity_multiplier``,
    ``baseline_probability_offset``.

    When ``secondary_categories`` is empty (single-category routing) the
    return values match the primary match exactly — predict_endpoint
    can call this unconditionally.
    """
    if not primary_match.secondary_categories:
        return {
            "drift_event_weights": primary_match.drift_event_weights,
            "drift_volatility": primary_match.drift_volatility,
            "drift_asymmetry_positive": primary_match.drift_asymmetry_positive,
            "drift_asymmetry_negative": primary_match.drift_asymmetry_negative,
            "sigmoid_sensitivity_multiplier": primary_match.sigmoid_sensitivity_multiplier,
            "baseline_probability_offset": primary_match.baseline_probability_offset,
        }

    secondary_weight_total = sum(w for _, w in primary_match.secondary_categories)
    primary_weight = max(0.0, 1.0 - secondary_weight_total)

    # Drift event weights (delegate to existing helper)
    blended_dew = dict(blend_drift_event_weights(primary_match, secondary_categories_data))

    # Scalar params: weighted average across primary + secondaries
    def _accum(get_from_match, get_from_dict):
        acc = primary_weight * get_from_match(primary_match)
        for cat_id, w in primary_match.secondary_categories:
            cat_data = secondary_categories_data.get(cat_id)
            if cat_data is None:
                continue
            try:
                acc += w * get_from_dict(cat_data)
            except (TypeError, ValueError, KeyError):
                continue
        return acc

    asym = lambda d: d.get("drift_asymmetry") or {}  # noqa: E731

    return {
        "drift_event_weights": tuple(blended_dew.items()),
        "drift_volatility": _accum(
            lambda m: m.drift_volatility,
            lambda d: float(d.get("drift_volatility", 1.0)),
        ),
        "drift_asymmetry_positive": _accum(
            lambda m: m.drift_asymmetry_positive,
            lambda d: float(asym(d).get("positive_multiplier", 1.0)),
        ),
        "drift_asymmetry_negative": _accum(
            lambda m: m.drift_asymmetry_negative,
            lambda d: float(asym(d).get("negative_multiplier", 1.0)),
        ),
        "sigmoid_sensitivity_multiplier": _accum(
            lambda m: m.sigmoid_sensitivity_multiplier,
            lambda d: float(d.get("sigmoid_sensitivity_multiplier", 1.0)),
        ),
        "baseline_probability_offset": _accum(
            lambda m: m.baseline_probability_offset,
            lambda d: float(d.get("baseline_probability_offset", 0.0)),
        ),
    }


def blend_drift_event_weights(
    primary_match: CategoryMatch,
    secondary_categories_data: Mapping[str, Mapping],
) -> tuple[tuple[str, float], ...]:
    """Sprint 18 WP3: blend ``drift_event_weights`` across the primary
    category and any secondary categories declared on the ``CategoryMatch``.

    Math: ``blended[event] = primary_weight * primary_event_weight +
    Σ secondary_weight * secondary_event_weight``.

    The primary's implicit weight is ``1.0 - Σ(secondary weights)``,
    matching the LLM router's parsing convention.

    When ``secondary_categories`` is empty (single-category routing) this
    function returns ``primary_match.drift_event_weights`` unchanged.
    """
    if not primary_match.secondary_categories:
        return primary_match.drift_event_weights

    secondary_weight_total = sum(w for _, w in primary_match.secondary_categories)
    primary_weight = max(0.0, 1.0 - secondary_weight_total)

    blended: dict[str, float] = {}
    for event, weight in primary_match.drift_event_weights:
        blended[event] = blended.get(event, 0.0) + primary_weight * weight

    for cat_id, cat_weight in primary_match.secondary_categories:
        cat_data = secondary_categories_data.get(cat_id)
        if cat_data is None:
            continue
        dew = cat_data.get("drift_event_weights") or {}
        for event, weight in dew.items():
            try:
                wf = float(weight)
            except (TypeError, ValueError):
                continue
            blended[event] = blended.get(event, 0.0) + cat_weight * wf

    return tuple(blended.items())


class CategoryRouter:
    """Routes free-text questions to prediction categories."""

    def __init__(
        self,
        categories: Sequence[Mapping[str, object]] | None = None,
        *,
        categories_path: Path | None = None,
        llm_backend: ILLMBackend | None = None,
    ) -> None:
        if categories is None:
            self._categories = load_categories(categories_path)
        else:
            self._categories = _validate_categories({"categories": list(categories)})
        self._by_id = {str(c["id"]): c for c in self._categories}
        if _BALANCED_ID not in self._by_id:
            raise ValueError("router requires a 'balanced' fallback category")
        self._llm = llm_backend
        # Sprint 17: in-process per-question LRU-style cache. Keyed by the
        # normalized question string; deterministic LLM calls (temperature
        # 0.1) make this safe and saves the network round-trip for repeated
        # dashboard requests. The backend's own InMemoryCache also caches
        # by (system, user, model) but storing the resolved CategoryMatch
        # avoids re-doing the JSON parse + lookup on every hit. Bounded
        # by manual eviction at 512 entries — production dashboards never
        # repeat 512 distinct questions per process.
        self._llm_route_cache: dict[str, CategoryMatch] = {}

    @property
    def categories(self) -> tuple[dict, ...]:
        return self._categories

    @property
    def category_ids(self) -> tuple[str, ...]:
        return tuple(self._by_id.keys())

    def route(self, question: str) -> CategoryMatch:
        """Sprint 17: LLM-first routing with keyword fallback.

        When ``self._llm`` is wired, the LLM classifier is consulted first.
        On valid result with confidence ≥ ``_LLM_ROUTE_CONFIDENCE_FLOOR``
        the LLM choice wins (regardless of what keywords would say). On
        timeout / error / low confidence / invalid id, the keyword path
        runs unchanged from Sprint 16.
        """
        q = _normalize_question(question)
        if not q:
            return self._fallback()

        # 1. LLM-first path — only when backend is wired
        if self._llm is not None:
            llm_match = self._route_with_llm(q, question)
            if llm_match is not None:
                return llm_match
            # Falls through to keyword on None (timeout, error, low confidence,
            # invalid category id, or schema mismatch). Already logged by
            # _route_with_llm — no extra warning here to avoid duplicate noise.

        # 2. Keyword path — Sprint 16 logic, unchanged.
        return self._keyword_route(q)

    def _keyword_route(self, q: str) -> CategoryMatch:
        """Pre-Sprint-17 keyword matching extracted as a helper. Reused
        as the fallback path when LLM is unavailable / inconclusive."""
        scores: list[tuple[int, tuple[str, ...], dict]] = []
        for cat in self._categories:
            if cat["id"] == _BALANCED_ID:
                continue
            keywords = cat.get("keywords") or []
            hits, matched = _count_keyword_hits(q, keywords)
            scores.append((hits, matched, cat))
        scores.sort(key=lambda x: x[0], reverse=True)

        best_hits, best_matched, best_cat = scores[0]
        second_hits = scores[1][0] if len(scores) > 1 else 0

        ambiguous = best_hits < _MIN_CONFIDENT_HITS or (
            second_hits > 0 and best_hits < _AMBIGUITY_RATIO * second_hits
        )

        if not ambiguous:
            confidence = best_hits / max(1, best_hits + second_hits)
            sub = _detect_subcategory(q, best_cat.get("subcategories", []) or ())
            return _build_match(
                best_cat, confidence=confidence, matched=best_matched, subcategory=sub
            )

        if best_hits >= 1:
            confidence = best_hits / max(1, best_hits + second_hits + 1)
            sub = _detect_subcategory(q, best_cat.get("subcategories", []) or ())
            return _build_match(
                best_cat,
                confidence=confidence,
                matched=best_matched,
                subcategory=sub,
                fallback=False,
            )

        return self._fallback()

    def _fallback(self) -> CategoryMatch:
        cat = self._by_id[_BALANCED_ID]
        return _build_match(
            cat, confidence=0.0, matched=(), subcategory=None, fallback=True
        )

    def _route_with_llm(self, q_normalized: str, question_raw: str) -> CategoryMatch | None:
        """Sprint 17: LLM-first classifier. Returns None on any failure
        path so the caller can degrade to keyword routing.

        Failure paths (all return None, all logged as WARNING):
            - Cache miss + LLM call exceeds ``_LLM_ROUTE_TIMEOUT_SEC``
            - LLM raises any exception (network, JSON parse, etc.)
            - JSON missing ``category`` key
            - Returned category id is not in the configured set
            - Confidence < ``_LLM_ROUTE_CONFIDENCE_FLOOR``
        """
        assert self._llm is not None

        # In-process cache — deterministic LLM (temp=0.1) over same prompt
        # yields the same answer; storing the resolved CategoryMatch saves
        # the JSON parse + dict lookup on every dashboard repeat.
        cached = self._llm_route_cache.get(q_normalized)
        if cached is not None:
            return cached

        prompt = load_split_prompt("category/route")
        user = prompt.render_user(question=question_raw)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(
                    self._llm.complete_json,
                    prompt.system, user, temperature=0.1,
                )
                data = fut.result(timeout=_LLM_ROUTE_TIMEOUT_SEC)
        except concurrent.futures.TimeoutError:
            logger.warning(
                "LLM category routing timed out after %.1fs; falling back to keywords",
                _LLM_ROUTE_TIMEOUT_SEC,
            )
            return None
        except (LLMBackendError, ValueError, KeyError) as e:
            logger.warning("LLM category routing failed (%s); falling back to keywords", e)
            return None

        if not isinstance(data, Mapping):
            logger.warning("LLM category routing returned non-mapping; falling back")
            return None

        # Sprint 18 WP3: parse multi-category response when present.
        # Spec: either {"category": "id"} (single) or {"categories": [{"id":..., "weight":...}, ...]}.
        # Multi-category form populates secondary_categories; primary
        # is the highest-weight entry.
        categories_raw = data.get("categories")
        if isinstance(categories_raw, list) and categories_raw:
            multi = _parse_multi_categories(categories_raw, self._by_id)
            if multi is None:
                # Schema mismatch in multi-cat form → fall back to keyword path
                return None
            picked_id, secondary = multi
        else:
            picked_id = str(data.get("category", "")).strip()
            secondary = ()

        confidence_raw = data.get("confidence", 1.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 1.0  # Backward-compat: old prompt didn't emit confidence
        sub_raw = data.get("subcategory")
        reasoning = str(data.get("reasoning", "")).strip()

        if picked_id not in self._by_id:
            logger.warning(
                "LLM returned unknown category id %r (reasoning: %s); falling back",
                picked_id, reasoning or "none",
            )
            return None

        if confidence < _LLM_ROUTE_CONFIDENCE_FLOOR:
            logger.info(
                "LLM confidence %.2f below floor %.2f for category %r; falling back to keywords",
                confidence, _LLM_ROUTE_CONFIDENCE_FLOOR, picked_id,
            )
            return None

        cat = self._by_id[picked_id]
        # Subcategory either from LLM (if listed in config.subcategories) or
        # from heuristic detection.
        sub = None
        if isinstance(sub_raw, str) and sub_raw and sub_raw in (
            cat.get("subcategories") or []
        ):
            sub = sub_raw
        else:
            sub = _detect_subcategory(q_normalized, cat.get("subcategories", []) or ())

        match = _build_match(
            cat,
            confidence=confidence,
            matched=(),
            subcategory=sub,
            llm_used=True,
            secondary_categories=secondary,
        )
        # Bounded cache — drop oldest if we exceed 512 distinct questions.
        if len(self._llm_route_cache) >= 512:
            # Cheap eviction: clear the whole cache (production dashboards
            # rarely hit this; unit tests bypass entirely with mocks).
            self._llm_route_cache.clear()
        self._llm_route_cache[q_normalized] = match
        if reasoning:
            logger.debug("LLM route: %s → %s (%s)", picked_id, confidence, reasoning)
        return match


def default_router(categories_path: Path | None = None) -> CategoryRouter:
    """Construct a CategoryRouter; wire LLM only when explicitly enabled.

    The LLM backend is loaded only when both:
        - environment variable ``REALM_LLM_CATEGORY_BACKEND`` is set to a
          truthy value (e.g. "1", "true"), AND
        - ``realm.llm.router.is_llm_configured()`` reports a usable backend.

    This keeps the test suite hermetic by default — no live LLM calls unless
    explicitly opted in.
    """
    backend: ILLMBackend | None = None
    enable = os.environ.get(_LLM_ENABLE_ENV, "").strip().lower()
    if enable in ("1", "true", "yes", "on") and is_llm_configured():
        try:
            backend = LLMRouter().for_task(TASK_CATEGORY)
        except Exception:
            backend = None
    return CategoryRouter(categories_path=categories_path, llm_backend=backend)
