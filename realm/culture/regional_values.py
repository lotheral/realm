"""Region-level value modifiers.

A fallback/supplementary layer for traits that Hofstede doesn't capture cleanly
at a regional level. Example: 'mena' region carries a tradition-weighted bias
beyond what UAI/PDI already provide.
"""

from __future__ import annotations

_REGIONAL_MODIFIERS: dict[str, dict[str, float]] = {
    "asia_east": {
        "patience": 0.04,
        "conscientiousness": 0.03,
        "analytical_depth": 0.03,
    },
    "asia_south": {
        "spirituality": 0.04,
        "herd_susceptibility": 0.03,
    },
    "asia_southeast": {
        "agreeableness": 0.03,
        "patience": 0.03,
    },
    "america_north": {
        "individualism": 0.04,
        "communication_assertiveness": 0.04,
    },
    "america_south": {
        "extraversion": 0.04,
        "agreeableness": 0.03,
    },
    "europe_west": {
        "analytical_depth": 0.03,
        "conscientiousness": 0.03,
    },
    "europe_east": {
        "conscientiousness": 0.03,
        "loss_aversion": 0.04,
    },
    "mena": {
        "tradition_vs_progress": -0.05,
        "authority_compliance": 0.04,
        "spirituality": 0.04,
    },
    "africa_west": {
        "extraversion": 0.04,
        "agreeableness": 0.03,
    },
    "africa_east": {
        "empathy": 0.04,
        "herd_susceptibility": 0.03,
    },
    "africa_central": {
        "empathy": 0.04,
        "herd_susceptibility": 0.03,
    },
    "africa_south": {
        "individualism": 0.03,
    },
}


def region_to_modifiers(region: str) -> dict[str, float]:
    return dict(_REGIONAL_MODIFIERS.get(region, {}))
