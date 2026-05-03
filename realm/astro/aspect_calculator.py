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

# Pre-materialised tuple for fast iteration in hot paths (avoids dict.items()
# overhead every call). Order matches ASPECT_ANGLES insertion so tie-breaking
# behaviour is bit-exact with the legacy find_aspect.
_ASPECT_ITEMS: tuple[tuple[str, float], ...] = tuple(ASPECT_ANGLES.items())


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

    for aspect_name, exact_angle in _ASPECT_ITEMS:
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


def _is_applying_transit_natal(
    tp_lon: float, tp_speed: float, np_lon: float, exact_angle: float,
) -> bool:
    """Transit→natal applying check; natal speed is always 0.

    Inlined, allocation-free variant of ``_is_applying`` for the 10K-agent
    simulation hot path. Mathematically equivalent: current_dist uses
    ``abs(current ± exact_angle)``, future_dist advances only the transiting
    body (natal speed = 0). Tie-break condition uses tp_speed != 0 which is
    equivalent to ``rel_speed = -tp_speed != 0`` in the legacy path.
    """
    current = _signed_separation(tp_lon, np_lon)
    current_dist_pos = abs(current - exact_angle)
    current_dist_neg = abs(current + exact_angle)
    current_dist = current_dist_pos if current_dist_pos < current_dist_neg else current_dist_neg

    future = _signed_separation(tp_lon + tp_speed * 0.01, np_lon)
    future_dist_pos = abs(future - exact_angle)
    future_dist_neg = abs(future + exact_angle)
    future_dist = future_dist_pos if future_dist_pos < future_dist_neg else future_dist_neg

    return future_dist < current_dist - 1e-9 or (
        future_dist < current_dist and tp_speed != 0
    )


def find_transit_aspects(
    transiting: tuple[PlanetPosition, ...] | list[PlanetPosition],
    natal: tuple[PlanetPosition, ...] | list[PlanetPosition],
    orbs: Mapping[str, float],
) -> tuple[Aspect, ...]:
    """Aspects between transiting bodies and natal positions.

    planet1 in the returned Aspect is the transiting body, planet2 is the natal.
    Same-name aspects (e.g., transit Sun conjunct natal Sun) ARE included.

    Sprint 10 WP1 optimisation: direct pair evaluation without the
    per-pair PlanetPosition re-allocation the original implementation used to
    bypass ``find_aspect``'s same-name rejection. The ``enabled`` tuple is
    built once per call (hoisting dict lookups out of the O(N_transit ×
    N_natal) inner loop). Bit-exact with the pre-optimisation code path.
    """
    # Pre-compile (aspect_name, exact_angle, max_orb) once — the inner loop
    # runs ~1.7M times/tick at 10K agents; every dict.get() hoist matters.
    enabled: list[tuple[str, float, float]] = []
    for aspect_name, exact_angle in _ASPECT_ITEMS:
        max_orb = orbs.get(aspect_name)
        if max_orb is not None:
            enabled.append((aspect_name, exact_angle, float(max_orb)))

    aspects: list[Aspect] = []
    for tp in transiting:
        tp_lon = tp.longitude
        tp_speed = tp.speed
        tp_name = tp.name
        for np_ in natal:
            sep = _shortest_arc(tp_lon, np_.longitude)
            best_name: str | None = None
            best_exact = 0.0
            best_orb = float("inf")
            for aspect_name, exact_angle, max_orb in enabled:
                delta = sep - exact_angle
                if delta < 0.0:
                    delta = -delta
                if delta <= max_orb and delta < best_orb:
                    best_name = aspect_name
                    best_exact = exact_angle
                    best_orb = delta
            if best_name is None:
                continue
            applying = _is_applying_transit_natal(
                tp_lon, tp_speed, np_.longitude, best_exact,
            )
            aspects.append(Aspect(
                planet1=tp_name,
                planet2=np_.name,
                aspect_type=best_name,
                angle=sep,
                orb=best_orb,
                is_applying=applying,
            ))
    return tuple(aspects)
