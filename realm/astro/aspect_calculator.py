"""Aspect detection — pure-Python, no ephemeris dependency.

Given two planet positions (with longitudes + speeds), determine whether an
aspect exists within the configured orb, and classify applying vs separating.
"""

from __future__ import annotations

from collections.abc import Mapping

from realm.core.types import Aspect, PlanetPosition

# Exact angular separation for each recognized aspect.
ASPECT_ANGLES: Mapping[str, float] = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "quincunx": 150.0,
    "opposition": 180.0,
}


def _shortest_arc(lon1: float, lon2: float) -> float:
    """Absolute angular separation on the ecliptic, 0–180 degrees."""
    diff = (lon1 - lon2) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def _signed_separation(lon1: float, lon2: float) -> float:
    """Signed separation lon1 → lon2, range (-180, 180].

    Positive means lon2 is ahead of lon1 going prograde; negative means behind.
    Useful for applying/separating determination.
    """
    diff = (lon2 - lon1 + 180.0) % 360.0 - 180.0
    return diff


def find_aspect(
    p1: PlanetPosition,
    p2: PlanetPosition,
    orbs: Mapping[str, float],
) -> Aspect | None:
    """Return the tightest matching aspect between two planets, or None.

    Args:
        p1, p2: planet positions (must include speed for applying/separating).
        orbs: mapping of aspect name → allowed orb in degrees.
              Missing keys disable that aspect.
    """
    if p1.name == p2.name:
        return None

    sep = _shortest_arc(p1.longitude, p2.longitude)

    best: Aspect | None = None
    best_orb = float("inf")

    for aspect_name, exact_angle in ASPECT_ANGLES.items():
        max_orb = orbs.get(aspect_name)
        if max_orb is None:
            continue
        delta = abs(sep - exact_angle)
        if delta <= max_orb and delta < best_orb:
            applying = _is_applying(p1, p2, exact_angle)
            best = Aspect(
                planet1=p1.name,
                planet2=p2.name,
                aspect_type=aspect_name,
                angle=sep,
                orb=delta,
                is_applying=applying,
            )
            best_orb = delta

    return best


def _is_applying(p1: PlanetPosition, p2: PlanetPosition, exact_angle: float) -> bool:
    """Is the aspect tightening (applying) or loosening (separating)?

    Algorithm:
        - Current signed separation = (lon2 - lon1) wrapped to (-180, 180]
        - Relative speed = speed2 - speed1 (deg/day)
        - After one day, new signed separation = current + relative_speed
        - If |new - exact_angle| < |current - exact_angle| → applying.
    """
    current = _signed_separation(p1.longitude, p2.longitude)
    rel_speed = p2.speed - p1.speed

    # We check against both +exact_angle and -exact_angle (aspects are symmetric).
    candidates = (exact_angle, -exact_angle)
    current_dist = min(abs(current - c) for c in candidates)
    future = _signed_separation(
        p1.longitude + p1.speed * 0.01,
        p2.longitude + p2.speed * 0.01,
    )
    future_dist = min(abs(future - c) for c in candidates)

    # Tiny offset to break ties deterministically toward "separating".
    return future_dist < current_dist - 1e-9 or (
        future_dist < current_dist and rel_speed != 0
    )


def find_all_aspects(
    planets: tuple[PlanetPosition, ...] | list[PlanetPosition],
    orbs: Mapping[str, float],
) -> tuple[Aspect, ...]:
    """All pairwise aspects among a set of planets, deduplicated."""
    aspects: list[Aspect] = []
    seen_pairs: set[frozenset[str]] = set()
    for i, p1 in enumerate(planets):
        for p2 in planets[i + 1:]:
            pair = frozenset((p1.name, p2.name))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            aspect = find_aspect(p1, p2, orbs)
            if aspect is not None:
                aspects.append(aspect)
    return tuple(aspects)


def find_transit_aspects(
    transiting: tuple[PlanetPosition, ...] | list[PlanetPosition],
    natal: tuple[PlanetPosition, ...] | list[PlanetPosition],
    orbs: Mapping[str, float],
) -> tuple[Aspect, ...]:
    """Aspects between transiting bodies and natal positions.

    planet1 in the returned Aspect is the transiting body, planet2 is the natal.
    Same-name aspects (e.g., transit Sun conjunct natal Sun) ARE included.
    """
    aspects: list[Aspect] = []
    for tp in transiting:
        for np_ in natal:
            # Temporarily synthesize distinct names so find_aspect won't reject same-name pairs.
            transit_position = PlanetPosition(
                name=f"t_{tp.name}",
                longitude=tp.longitude,
                latitude=tp.latitude,
                sign=tp.sign,
                sign_degree=tp.sign_degree,
                house=tp.house,
                is_retrograde=tp.is_retrograde,
                speed=tp.speed,
            )
            natal_position = PlanetPosition(
                name=f"n_{np_.name}",
                longitude=np_.longitude,
                latitude=np_.latitude,
                sign=np_.sign,
                sign_degree=np_.sign_degree,
                house=np_.house,
                is_retrograde=np_.is_retrograde,
                speed=0.0,
            )
            a = find_aspect(transit_position, natal_position, orbs)
            if a is not None:
                aspects.append(
                    Aspect(
                        planet1=tp.name,
                        planet2=np_.name,
                        aspect_type=a.aspect_type,
                        angle=a.angle,
                        orb=a.orb,
                        is_applying=a.is_applying,
                    )
                )
    return tuple(aspects)
