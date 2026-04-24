"""House system calculations.

Phase 1 implements Equal House (simplest, robust) as the baseline. Placidus
(the REALM_CLAUDE.md default) requires precise sidereal time and iterative
latitude-dependent calculations — deferred to the Kerykeion backend.

Concrete engines may override by supplying their own house cusps.
"""

from __future__ import annotations

from realm.core.types import SIGNS


def equal_house_cusps(ascendant: float) -> tuple[float, ...]:
    """Return 12 house cusps for Equal House system.

    House 1 cusp = Ascendant, each subsequent cusp is 30° later.
    """
    return tuple((ascendant + 30.0 * i) % 360.0 for i in range(12))


def house_for_longitude(longitude: float, cusps: tuple[float, ...]) -> int:
    """Return the 1-indexed house containing the given ecliptic longitude.

    Handles the wrap-around case (e.g., cusp 12 at 340° and cusp 1 at 10°).
    """
    if len(cusps) != 12:
        raise ValueError(f"Expected 12 house cusps, got {len(cusps)}")
    longitude = longitude % 360.0
    for i in range(12):
        start = cusps[i] % 360.0
        end = cusps[(i + 1) % 12] % 360.0
        if start <= end:
            if start <= longitude < end:
                return i + 1
        else:
            # Wraps around 0°
            if longitude >= start or longitude < end:
                return i + 1
    # Fallback (should not reach here for a well-formed cusp set)
    return 12


def sign_from_longitude(longitude: float) -> tuple[str, float]:
    """Return (sign_name, sign_degree_0_to_30) for an ecliptic longitude."""
    lon = longitude % 360.0
    idx = int(lon // 30)
    return SIGNS[idx], lon - idx * 30.0
