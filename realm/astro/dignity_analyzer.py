"""Essential dignity analysis.

Each classical planet has a preferred sign (rulership), an exalted sign, a sign
where it's in detriment, and one where it's in fall. These map to a strength
multiplier that modifies the planet's contribution to a trait vector.
"""

from __future__ import annotations

from realm.core.types import DIGNITY_SCORE, PLANET_DIGNITY, PlanetPosition


def get_dignity_state(planet_name: str, sign: str) -> str:
    """Return the dignity state: 'rulership', 'exaltation', 'detriment', 'fall', or 'neutral'.

    Non-classical bodies (nodes, Chiron, asteroids) always return 'neutral' as
    they don't have traditional essential dignities.
    """
    dignities = PLANET_DIGNITY.get(planet_name)
    if dignities is None:
        return "neutral"
    for state, dignified_sign in dignities.items():
        if dignified_sign == sign:
            return state
    return "neutral"


def get_dignity_score(planet_name: str, sign: str) -> float:
    """Multiplier applied to a planet's effective strength given its sign placement.

    Range: 0.5 (fall) to 1.5 (rulership). 1.0 = neutral.
    """
    return DIGNITY_SCORE[get_dignity_state(planet_name, sign)]


def planet_strength(position: PlanetPosition) -> float:
    """Overall strength of a single planet position.

    Phase 1: dignity only. Retrograde reduces strength by 10%. Future phases will
    incorporate angular house placement, mutual reception, and sect.
    """
    score = get_dignity_score(position.name, position.sign)
    if position.is_retrograde:
        score *= 0.9
    return score
