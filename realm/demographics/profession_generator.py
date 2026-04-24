"""Profession sampling with country-tier adjustments.

Each country is tagged 'developed' | 'mid' | 'developing'. Base weights live in
professions.json; `country_adjustments` override specific categories for the
tagged tiers. 'mid' tier blends 50/50.
"""

from __future__ import annotations

import random
from functools import lru_cache
from typing import Any

from .country_data import load_professions


@lru_cache(maxsize=64)
def _weights_for_tier(tier: str) -> dict[str, float]:
    """Merge base profession weights with tier-specific overrides.

    Returns {category_code: weight} ready for weighted sampling.
    """
    data = load_professions()
    base = {c["code"]: float(c["weight"]) for c in data["categories"]}
    overrides = data.get("country_adjustments", {}).get(tier)

    if overrides:
        for code, w in overrides.items():
            if code in base:
                base[code] = float(w)

    if tier == "mid":
        # 50/50 blend of developed + developing overrides
        dev = data.get("country_adjustments", {}).get("developed", {})
        ing = data.get("country_adjustments", {}).get("developing", {})
        for code in set(dev) | set(ing):
            if code in base:
                d = float(dev.get(code, base[code]))
                i = float(ing.get(code, base[code]))
                base[code] = (d + i) / 2.0

    # Re-normalize so weights sum to 1
    total = sum(base.values())
    if total <= 0:
        raise ValueError("Profession weights sum to zero")
    return {k: v / total for k, v in base.items()}


@lru_cache(maxsize=1)
def _category_names() -> dict[str, str]:
    data = load_professions()
    return {c["code"]: c["name"] for c in data["categories"]}


@lru_cache(maxsize=1)
def _income_multipliers() -> dict[str, float]:
    data = load_professions()
    return {c["code"]: float(c["typical_income_multiplier"]) for c in data["categories"]}


def tier_for_country(iso2: str) -> str:
    data = load_professions()
    return data.get("country_tier", {}).get(iso2, "mid")


def sample_profession(
    iso2: str,
    rng: random.Random,
    age_years: int,
) -> dict[str, Any]:
    """Sample a profession code for one agent.

    Age gates:
        < 22  → 60% chance 'student'
        > 65  → 70% chance 'retired' (developed), 30% (developing)
        22–65 → full distribution

    Returns dict with {code, name, income_multiplier}.
    """
    tier = tier_for_country(iso2)

    # Age gating
    if age_years < 22 and rng.random() < 0.6:
        code = "student"
    elif age_years > 65 and rng.random() < (0.7 if tier == "developed" else 0.3):
        code = "retired"
    else:
        weights = _weights_for_tier(tier)
        codes = list(weights.keys())
        probs = [weights[c] for c in codes]
        code = rng.choices(codes, weights=probs, k=1)[0]

    return {
        "code": code,
        "name": _category_names().get(code, code),
        "income_multiplier": _income_multipliers().get(code, 1.0),
    }
