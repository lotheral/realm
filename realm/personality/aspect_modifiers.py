"""Per-planet aspect amplification.

Given a planet position and the chart's aspect list, return a multiplier that
scales up the planet's trait contribution. Tight aspects matter more; challenging
aspects (square/opposition) still count because they create strong trait expression.
"""

from __future__ import annotations

from collections.abc import Mapping

from realm.core.types import Aspect


def orb_tightness(orb: float, max_orb: float = 8.0) -> float:
    """Map orb (0 = exact) to tightness (1 = exact, 0 = at max orb)."""
    if max_orb <= 0:
        return 1.0
    return max(0.0, 1.0 - orb / max_orb)


def planet_aspect_multiplier(
    planet_name: str,
    aspects: tuple[Aspect, ...] | list[Aspect],
    aspect_weights: Mapping[str, float],
    max_orb: float = 8.0,
) -> float:
    """Return 1.0 + Σ(aspect_weight * tightness) over all aspects touching this planet.

    Multiplier is typically in [1.0, 1.5]. Used as a per-planet scale factor on
    the planet's base trait contribution.
    """
    boost = 0.0
    for a in aspects:
        if planet_name not in (a.planet1, a.planet2):
            continue
        w = aspect_weights.get(a.aspect_type, 0.0)
        boost += w * orb_tightness(a.orb, max_orb)
    return 1.0 + boost
