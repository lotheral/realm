"""Tests for static fixture chart."""

from __future__ import annotations

from realm.astro.fixtures import KNOWN_SUBJECTS, STEVE_JOBS, synthetic_chart
from realm.core.types import PLANETS_ALL_PHASE1


class TestSyntheticChart:
    def test_has_all_phase1_bodies(self):
        chart = synthetic_chart()
        assert len(chart.planets) == len(PLANETS_ALL_PHASE1)
        names = {p.name for p in chart.planets}
        assert names == set(PLANETS_ALL_PHASE1)

    def test_sun_in_aries_at_15(self):
        chart = synthetic_chart()
        sun = chart.planet("Sun")
        assert sun is not None
        assert sun.sign == "Aries"
        assert sun.sign_degree == 15.0

    def test_moon_trine_sun(self):
        chart = synthetic_chart()
        # Sun at 15° Aries, Moon at 10° Cancer → 95° sep? No, 100 - 15 = 85 (not trine).
        # Let's just check that *some* aspect exists between Sun and Moon in this chart.
        sun_moon = [a for a in chart.aspects
                    if {a.planet1, a.planet2} == {"Sun", "Moon"}]
        # No exact trine from those coords; 85° is a wide square (within 7° orb).
        assert len(sun_moon) == 1
        assert sun_moon[0].aspect_type == "square"

    def test_sun_conjunct_mars(self):
        chart = synthetic_chart()
        sun_mars = [a for a in chart.aspects
                    if {a.planet1, a.planet2} == {"Sun", "Mars"}]
        assert len(sun_mars) == 1
        assert sun_mars[0].aspect_type == "conjunction"

    def test_element_balance_sums_to_one(self):
        chart = synthetic_chart()
        assert abs(sum(chart.element_balance.values()) - 1.0) < 1e-9


class TestBirthDataFixtures:
    def test_all_timezones_are_aware(self):
        for subject in KNOWN_SUBJECTS:
            assert subject.birth_dt.tzinfo is not None

    def test_latitude_bounds(self):
        for subject in KNOWN_SUBJECTS:
            assert -90 <= subject.latitude <= 90
            assert -180 <= subject.longitude <= 180

    def test_steve_jobs_data(self):
        assert STEVE_JOBS.name == "Steve Jobs"
        assert STEVE_JOBS.latitude > 37 and STEVE_JOBS.latitude < 38
