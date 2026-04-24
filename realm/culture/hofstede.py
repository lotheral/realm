"""Hofstede → TraitVector shift mapping.

Each Hofstede dimension (pdi, idv, mas, uai, lto, ivr) is normalized to [-1, 1]
(centered on 50) and then projected onto a set of trait axes with weighted
coefficients. Total shift per trait is summed and typically lies in [-0.25,
+0.25].

Example: PDI=90 (very hierarchical) → centered +0.8 → boosts authority_compliance
by +0.8 * 0.20 = +0.16; reduces contrarian_tendency by -0.8 * 0.12 = -0.096.
"""

from __future__ import annotations

from collections.abc import Mapping


def _centered(score: float) -> float:
    """Map 0-100 Hofstede score to [-1, +1]."""
    return (score - 50.0) / 50.0


# Coefficient table: [dimension][trait] = weight in [-0.3, +0.3].
# Positive weight: higher Hofstede score → higher trait.
# Derived from cross-cultural psychology literature (Hofstede 2010, Minkov 2018).

_HOFSTEDE_COEFFICIENTS: dict[str, dict[str, float]] = {
    "pdi": {  # Power Distance — hierarchical vs egalitarian
        "authority_compliance": 0.20,
        "contrarian_tendency": -0.12,
        "social_dominance": 0.08,
        "communication_assertiveness": -0.08,
        "individualism": -0.05,
    },
    "idv": {  # Individualism — vs collectivism
        "individualism": 0.25,
        "herd_susceptibility": -0.18,
        "empathy": -0.05,
        "authority_compliance": -0.08,
        "contrarian_tendency": 0.08,
    },
    "mas": {  # Masculinity — achievement/competition vs care/cooperation
        "social_dominance": 0.15,
        "agreeableness": -0.12,
        "risk_appetite": 0.08,
        "empathy": -0.10,
        "communication_assertiveness": 0.10,
        "financial_optimism": 0.06,
    },
    "uai": {  # Uncertainty Avoidance — rules/structure preference
        "conscientiousness": 0.12,
        "loss_aversion": 0.18,
        "risk_appetite": -0.18,
        "patience": 0.06,
        "openness": -0.10,
        "tradition_vs_progress": -0.12,
    },
    "lto": {  # Long-Term Orientation — planning/pragmatism
        "patience": 0.18,
        "conscientiousness": 0.10,
        "impulsivity": -0.15,
        "analytical_depth": 0.08,
        "fomo_susceptibility": -0.10,
    },
    "ivr": {  # Indulgence — gratification vs restraint
        "openness": 0.10,
        "impulsivity": 0.12,
        "financial_optimism": 0.08,
        "extraversion": 0.10,
        "loss_aversion": -0.10,
        "patience": -0.08,
    },
}


def hofstede_to_modifiers(scores: Mapping[str, int | float]) -> dict[str, float]:
    """Return additive trait modifiers {trait: delta} from Hofstede 6D scores.

    Delta is a raw (unblended) shift; the CulturalModifier applies a blend ratio
    before mutating the trait vector.
    """
    modifiers: dict[str, float] = {}
    for dim, coefficients in _HOFSTEDE_COEFFICIENTS.items():
        raw = scores.get(dim)
        if raw is None:
            continue
        centered = _centered(float(raw))
        for trait, weight in coefficients.items():
            modifiers[trait] = modifiers.get(trait, 0.0) + centered * weight
    return modifiers
