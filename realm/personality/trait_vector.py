"""TraitVector — 24-dimensional personality/behavior embedding.

Every dimension is in [0.0, 1.0]. 0.5 = neutral. Values outside the range are
clamped on construction via from_dict() or apply_modifier().
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True, slots=True)
class TraitVector:
    """Behavioral parameters for a REALM agent.

    Dimensions group into six families:

        Big Five:              openness, conscientiousness, extraversion,
                               agreeableness, neuroticism
        Decision making:       risk_appetite, analytical_depth, impulsivity,
                               patience
        Social dynamics:       social_dominance, herd_susceptibility,
                               authority_compliance, contrarian_tendency, empathy
        Financial behavior:    financial_optimism, loss_aversion,
                               fomo_susceptibility
        Communication:         communication_assertiveness, persuasion_skill,
                               information_sharing
        Worldview:             political_spectrum, tradition_vs_progress,
                               individualism, spirituality
    """

    # --- Big Five ---
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5

    # --- Decision making ---
    risk_appetite: float = 0.5
    analytical_depth: float = 0.5
    impulsivity: float = 0.5
    patience: float = 0.5

    # --- Social dynamics ---
    social_dominance: float = 0.5
    herd_susceptibility: float = 0.5
    authority_compliance: float = 0.5
    contrarian_tendency: float = 0.5
    empathy: float = 0.5

    # --- Financial ---
    financial_optimism: float = 0.5
    loss_aversion: float = 0.5
    fomo_susceptibility: float = 0.5

    # --- Communication ---
    communication_assertiveness: float = 0.5
    persuasion_skill: float = 0.5
    information_sharing: float = 0.5

    # --- Worldview ---
    # political_spectrum: astrological layer intentionally does NOT populate
    # this trait — see data/astro/planet_trait_map.json:_excluded_by_design.
    # Scope boundary: REALM models temperament, not ideological preference.
    # Downstream layers (demographic, questionnaire) can set it.
    political_spectrum: float = 0.5        # 0 = left, 0.5 = center, 1 = right
    tradition_vs_progress: float = 0.5     # 0 = traditionalist, 1 = progressive
    individualism: float = 0.5             # 0 = collectivist, 1 = individualist
    spirituality: float = 0.5

    # ---- Class-level helpers ----------------------------------------------

    @classmethod
    def trait_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))

    @classmethod
    def from_dict(cls, data: Mapping[str, float]) -> TraitVector:
        """Build a TraitVector from a dict, clamping values to [0, 1].

        Missing keys default to 0.5. Unknown keys are ignored.
        """
        known = {f.name for f in fields(cls)}
        clamped = {
            k: max(0.0, min(1.0, float(v)))
            for k, v in data.items()
            if k in known
        }
        return cls(**clamped)

    @classmethod
    def neutral(cls) -> TraitVector:
        return cls()

    # ---- Instance methods -------------------------------------------------

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def to_list(self) -> list[float]:
        return [getattr(self, f.name) for f in fields(self)]

    def apply_modifier(self, modifiers: Mapping[str, float]) -> TraitVector:
        """Return a new TraitVector with additive modifiers applied (clamped to [0, 1])."""
        updates = {}
        known = {f.name for f in fields(self)}
        for trait, delta in modifiers.items():
            if trait not in known:
                continue
            new_val = getattr(self, trait) + float(delta)
            updates[trait] = max(0.0, min(1.0, new_val))
        return replace(self, **updates)

    def blend(self, other: TraitVector, alpha: float) -> TraitVector:
        """Linearly interpolate: (1-alpha)*self + alpha*other. alpha in [0,1]."""
        alpha = max(0.0, min(1.0, float(alpha)))
        updates = {}
        for f in fields(self):
            s = getattr(self, f.name)
            o = getattr(other, f.name)
            updates[f.name] = (1 - alpha) * s + alpha * o
        return replace(self, **updates)

    def distance(self, other: TraitVector) -> float:
        """Euclidean distance between two trait vectors."""
        total = 0.0
        for f in fields(self):
            d = getattr(self, f.name) - getattr(other, f.name)
            total += d * d
        return math.sqrt(total)


def mean_trait_vector(vectors: Iterable[TraitVector]) -> TraitVector:
    """Average several TraitVectors dimension-wise."""
    vs = list(vectors)
    if not vs:
        return TraitVector.neutral()
    names = TraitVector.trait_names()
    totals = dict.fromkeys(names, 0.0)
    for v in vs:
        for n in names:
            totals[n] += getattr(v, n)
    avg = {n: totals[n] / len(vs) for n in names}
    return TraitVector.from_dict(avg)
