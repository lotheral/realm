"""Tests for aspect_calculator — pure-math aspect detection."""

from __future__ import annotations

from realm.astro.aspect_calculator import (
    ASPECT_ANGLES,
    _is_applying,
    _shortest_arc,
    _signed_separation,
    find_all_aspects,
    find_aspect,
    find_transit_aspects,
)
from realm.core.types import PlanetPosition


def _p(name: str, lon: float, speed: float = 1.0) -> PlanetPosition:
    """Build a minimal PlanetPosition for testing."""
    return PlanetPosition(
        name=name, longitude=lon % 360.0, latitude=0.0,
        sign="Aries", sign_degree=0.0, house=1,
        is_retrograde=speed < 0, speed=speed,
    )


ORBS = {
    "conjunction": 8.0, "opposition": 8.0, "trine": 7.0,
    "square": 7.0, "sextile": 5.0, "quincunx": 3.0,
}


class TestArcHelpers:
    def test_shortest_arc_is_symmetric(self):
        assert _shortest_arc(10, 190) == 180
        assert _shortest_arc(190, 10) == 180

    def test_shortest_arc_wraps_correctly(self):
        assert _shortest_arc(350, 10) == 20
        assert _shortest_arc(10, 350) == 20

    def test_signed_separation_positive_when_b_ahead(self):
        assert _signed_separation(10, 30) == 20

    def test_signed_separation_negative_when_b_behind(self):
        assert _signed_separation(30, 10) == -20

    def test_signed_separation_wraps_at_180(self):
        # Just under 180 is +, just over 180 wraps to negative.
        assert _signed_separation(0, 179) == 179
        assert abs(_signed_separation(0, 181) - (-179)) < 1e-9


class TestFindAspectBasic:
    def test_exact_conjunction_detected(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 0.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "conjunction"
        assert a.orb == 0.0

    def test_exact_opposition_detected(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 180.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "opposition"

    def test_exact_trine_detected(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 120.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "trine"

    def test_exact_square_detected(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 90.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "square"

    def test_exact_sextile_detected(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 60.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "sextile"

    def test_exact_quincunx_detected(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 150.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "quincunx"


class TestFindAspectOrbs:
    def test_within_orb(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 124.0)  # 4° wide trine, orb=7
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "trine"
        assert abs(a.orb - 4.0) < 1e-9

    def test_outside_orb_returns_none(self):
        p1, p2 = _p("Sun", 0.0), _p("Moon", 130.0)  # 10° wide from trine, orb=7
        a = find_aspect(p1, p2, ORBS)
        assert a is None

    def test_tightest_aspect_wins(self):
        # 119° is closer to 120° (trine) than to 90° (square) — clear trine.
        p1, p2 = _p("Sun", 0.0), _p("Moon", 119.0)
        a = find_aspect(p1, p2, ORBS)
        assert a is not None
        assert a.aspect_type == "trine"

    def test_missing_aspect_in_orbs_disables_it(self):
        orbs_no_trine = {k: v for k, v in ORBS.items() if k != "trine"}
        p1, p2 = _p("Sun", 0.0), _p("Moon", 120.0)
        a = find_aspect(p1, p2, orbs_no_trine)
        # Should not find trine; nothing else is close.
        assert a is None or a.aspect_type != "trine"

    def test_same_name_returns_none(self):
        p1, p2 = _p("Sun", 0.0), _p("Sun", 0.0)
        assert find_aspect(p1, p2, ORBS) is None


class TestApplyingSeparating:
    def test_faster_planet_approaching_means_applying(self):
        # Moon at 110°, speed 13°/day; Sun at 0°, speed 1°/day.
        # Moon is ahead of Sun by 110°; one step later: Moon 110.13, Sun 0.01 → sep=110.12 → moving toward 120° → applying.
        sun = _p("Sun", 0.0, speed=1.0)
        moon = _p("Moon", 110.0, speed=13.0)
        assert _is_applying(sun, moon, ASPECT_ANGLES["trine"]) is True

    def test_separating_after_exact(self):
        # Moon at 121° past Sun at 0°; moon still faster — it's moving away from 120°.
        sun = _p("Sun", 0.0, speed=1.0)
        moon = _p("Moon", 121.0, speed=13.0)
        assert _is_applying(sun, moon, ASPECT_ANGLES["trine"]) is False


class TestFindAllAspects:
    def test_no_duplicate_pairs(self):
        ps = [_p("A", 0.0), _p("B", 120.0), _p("C", 60.0)]
        aspects = find_all_aspects(ps, ORBS)
        # Should be A-B trine, A-C sextile, B-C sextile = 3 aspects
        pair_set = {frozenset((a.planet1, a.planet2)) for a in aspects}
        assert len(pair_set) == 3

    def test_empty_list(self):
        assert find_all_aspects([], ORBS) == ()

    def test_single_planet(self):
        assert find_all_aspects([_p("Sun", 0.0)], ORBS) == ()


class TestFindTransitAspects:
    def test_transit_conjunct_natal_same_name(self):
        # Transit Sun at 10° conjunct natal Sun at 11° (within orb 8°)
        transit_sun = _p("Sun", 10.0, speed=1.0)
        natal_sun = _p("Sun", 11.0, speed=0.0)
        aspects = find_transit_aspects([transit_sun], [natal_sun], ORBS)
        assert len(aspects) == 1
        assert aspects[0].aspect_type == "conjunction"
        assert aspects[0].planet1 == "Sun"
        assert aspects[0].planet2 == "Sun"
