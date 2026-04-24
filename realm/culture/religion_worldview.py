"""Religion/worldview → trait modifier.

Primary religion classifications from countries.json shift several traits
modestly. These are cross-cultural averages, not individual predictions — they
capture aggregate cultural patterns (e.g., Confucian-influenced societies tend
toward higher patience and authority_compliance).
"""

from __future__ import annotations

# Modifier deltas by primary_religion tag. Values are additive shifts applied
# AFTER Hofstede mapping; kept small (max ±0.08) to respect natal dominance.
_RELIGION_MODIFIERS: dict[str, dict[str, float]] = {
    "christian": {
        "agreeableness": 0.04,
        "empathy": 0.05,
        "spirituality": 0.08,
    },
    "christian_orthodox": {
        "tradition_vs_progress": -0.08,
        "spirituality": 0.10,
        "authority_compliance": 0.04,
    },
    "muslim": {
        "authority_compliance": 0.06,
        "spirituality": 0.10,
        "tradition_vs_progress": -0.06,
        "agreeableness": 0.03,
    },
    "christian_muslim": {
        "spirituality": 0.08,
        "tradition_vs_progress": -0.05,
    },
    "christian_buddhist": {
        "spirituality": 0.07,
        "empathy": 0.04,
    },
    "hindu": {
        "spirituality": 0.10,
        "patience": 0.05,
        "tradition_vs_progress": -0.05,
    },
    "buddhist": {
        "spirituality": 0.08,
        "patience": 0.08,
        "empathy": 0.06,
        "impulsivity": -0.05,
    },
    "folk_buddhist": {
        "spirituality": 0.06,
        "patience": 0.05,
        "herd_susceptibility": 0.03,
    },
    "shinto_buddhist": {
        "patience": 0.06,
        "spirituality": 0.05,
        "conscientiousness": 0.05,
    },
}


def religion_to_modifiers(religion: str) -> dict[str, float]:
    return dict(_RELIGION_MODIFIERS.get(religion, {}))
