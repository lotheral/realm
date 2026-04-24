"""Socio-economic sampling: age, gender, income, education, marginal flags."""

from __future__ import annotations

import math
import random

from .country_data import get_country
from .profession_generator import tier_for_country

# ---- Age ------------------------------------------------------------------

def sample_age(iso2: str, rng: random.Random) -> int:
    """Sample age (years) from a normal distribution centred on country median.

    Spread widens for countries with younger populations (developing have more
    spread toward lower ages). Clamped to [18, 90] — simulation agents are adults.
    """
    country = get_country(iso2)
    median = float(country.get("median_age", 32.0))

    # Sigma: wider for younger populations.
    sigma = max(12.0, 18.0 - (median - 30.0) * 0.3)
    sampled = rng.gauss(median, sigma)
    return max(18, min(90, int(round(sampled))))


# ---- Gender ---------------------------------------------------------------

def sample_gender(rng: random.Random) -> str:
    """Sample M/F/X with realistic split: 49% M / 49% F / 2% X.

    2% non-binary reflects growing self-identification in recent surveys and
    leaves room for the simulation to represent non-cis identities.
    """
    r = rng.random()
    if r < 0.49:
        return "M"
    if r < 0.98:
        return "F"
    return "X"


# ---- Income ---------------------------------------------------------------

def sample_income(
    iso2: str,
    profession_income_multiplier: float,
    rng: random.Random,
) -> float:
    """Sample annual income in USD (log-normal around country median × profession mult)."""
    country = get_country(iso2)
    median_usd = float(country.get("gdp_per_capita_usd", 10000)) * 1.0
    mu_target = median_usd * profession_income_multiplier
    if mu_target <= 0:
        return 0.0

    # Log-normal with realistic σ_ln ≈ 0.7 (income Gini ~ 0.35-0.40).
    mu_ln = math.log(mu_target)
    sigma_ln = 0.7
    sampled = rng.lognormvariate(mu_ln, sigma_ln)
    return round(sampled, 2)


# ---- Education ------------------------------------------------------------

_EDUCATION_DIST_BY_TIER: dict[str, dict[str, float]] = {
    "developed": {
        "primary": 0.03, "secondary": 0.30, "bachelor": 0.42, "graduate": 0.25,
    },
    "mid": {
        "primary": 0.12, "secondary": 0.45, "bachelor": 0.32, "graduate": 0.11,
    },
    "developing": {
        "primary": 0.35, "secondary": 0.40, "bachelor": 0.20, "graduate": 0.05,
    },
}


def sample_education(iso2: str, rng: random.Random) -> str:
    tier = tier_for_country(iso2)
    dist = _EDUCATION_DIST_BY_TIER[tier]
    return rng.choices(list(dist.keys()), weights=list(dist.values()), k=1)[0]


# ---- Marginal profile -----------------------------------------------------
# Per design decision #8: 3 expert/outlier modes. Phase 2 implementation:
#   - 2% experts (specialized high-signal agents, e.g. domain analysts)
#   - 4% outliers (unusual combinations, e.g. very young + high education)
#   - 4% influencers (high social_dominance * persuasion_skill potential)
# Remainder: 90% "ordinary".

_MARGINAL_CATEGORIES: tuple[str, ...] = ("expert", "outlier", "influencer")
_MARGINAL_PROBS: tuple[float, ...] = (0.02, 0.04, 0.04)


def sample_marginal(rng: random.Random) -> tuple[bool, str | None]:
    r = rng.random()
    cumulative = 0.0
    for cat, p in zip(_MARGINAL_CATEGORIES, _MARGINAL_PROBS, strict=True):
        cumulative += p
        if r < cumulative:
            return True, cat
    return False, None
