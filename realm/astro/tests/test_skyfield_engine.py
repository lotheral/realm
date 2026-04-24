"""Integration tests for SkyfieldEngine using real ephemeris (JPL DE421).

These tests verify:
  - A known birth (Steve Jobs) yields Sun in Pisces, Moon in Aries
  - Output structure has all 13 Phase 1 bodies
  - Ascendant and Midheaven are in valid range
  - Aspects list is non-empty and well-formed

Test is skipped automatically if skyfield is not installed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("skyfield")

from realm.astro.fixtures import STEVE_JOBS  # noqa: E402
from realm.astro.skyfield_engine import SkyfieldEngine  # noqa: E402
from realm.core.exceptions import AstroCalculationError  # noqa: E402
from realm.core.types import ASPECT_TYPES, PLANETS_ALL_PHASE1  # noqa: E402


@pytest.fixture(scope="module")
def engine() -> SkyfieldEngine:
    return SkyfieldEngine()


@pytest.fixture(scope="module")
def jobs_chart(engine: SkyfieldEngine):
    return engine.calculate_natal_chart(
        birth_dt=STEVE_JOBS.birth_dt,
        latitude=STEVE_JOBS.latitude,
        longitude=STEVE_JOBS.longitude,
        timezone=STEVE_JOBS.timezone,
    )


class TestJobsChart:
    def test_all_13_bodies_returned(self, jobs_chart):
        assert len(jobs_chart.planets) == len(PLANETS_ALL_PHASE1)
        names = {p.name for p in jobs_chart.planets}
        assert names == set(PLANETS_ALL_PHASE1)

    def test_sun_in_pisces(self, jobs_chart):
        sun = jobs_chart.planet("Sun")
        assert sun is not None
        assert sun.sign == "Pisces"
        # Sun ~ 336° ecliptic = Pisces 6°±1° for Feb 24 1955
        assert 5 < sun.sign_degree < 10

    def test_moon_in_aries(self, jobs_chart):
        moon = jobs_chart.planet("Moon")
        assert moon is not None
        assert moon.sign == "Aries"

    def test_jupiter_in_cancer(self, jobs_chart):
        # Well-documented: Jobs had Jupiter in Cancer.
        jupiter = jobs_chart.planet("Jupiter")
        assert jupiter is not None
        assert jupiter.sign == "Cancer"

    def test_ascendant_in_range(self, jobs_chart):
        assert 0 <= jobs_chart.ascendant < 360

    def test_midheaven_in_range(self, jobs_chart):
        assert 0 <= jobs_chart.midheaven < 360

    def test_houses_are_12(self, jobs_chart):
        assert len(jobs_chart.houses) == 12

    def test_aspects_are_well_formed(self, jobs_chart):
        assert len(jobs_chart.aspects) > 0
        for a in jobs_chart.aspects:
            assert a.aspect_type in ASPECT_TYPES
            assert a.orb >= 0
            assert a.planet1 != a.planet2

    def test_element_balance_sums_to_one(self, jobs_chart):
        s = sum(jobs_chart.element_balance.values())
        assert abs(s - 1.0) < 1e-6

    def test_modality_balance_sums_to_one(self, jobs_chart):
        s = sum(jobs_chart.modality_balance.values())
        assert abs(s - 1.0) < 1e-6


class TestEngineErrors:
    def test_naive_datetime_raises(self, engine):
        with pytest.raises(AstroCalculationError):
            engine.calculate_natal_chart(
                birth_dt=datetime(1990, 1, 1, 12, 0),  # naive
                latitude=0.0, longitude=0.0, timezone="UTC",
            )

    def test_latitude_out_of_range_raises(self, engine):
        with pytest.raises(AstroCalculationError):
            engine.calculate_natal_chart(
                birth_dt=datetime(1990, 1, 1, 12, 0, tzinfo=UTC),
                latitude=95.0, longitude=0.0, timezone="UTC",
            )


class TestTransits:
    def test_transit_snapshot_structure(self, engine, jobs_chart):
        target = datetime(2020, 1, 1, 0, 0, tzinfo=UTC)
        snap = engine.calculate_transits(jobs_chart, target)
        assert snap.timestamp == target
        assert len(snap.transiting_planets) == len(PLANETS_ALL_PHASE1)
        assert snap.moon_phase in {"new", "waxing", "full", "waning"}
        for tr in snap.active_transits:
            assert tr.aspect_type in ASPECT_TYPES

    def test_transit_range(self, engine, jobs_chart):
        start = datetime(2020, 1, 1, tzinfo=UTC)
        end = start + timedelta(days=3)
        snaps = engine.calculate_transit_range(jobs_chart, start, end, interval_hours=24)
        assert len(snaps) == 4  # days 0,1,2,3


class TestDeterminism:
    def test_same_input_same_output(self, engine):
        charts = [
            engine.calculate_natal_chart(
                STEVE_JOBS.birth_dt, STEVE_JOBS.latitude,
                STEVE_JOBS.longitude, STEVE_JOBS.timezone,
            )
            for _ in range(2)
        ]
        # Compare Sun longitudes — should be identical to double precision.
        s0 = charts[0].planet("Sun")
        s1 = charts[1].planet("Sun")
        assert s0 == s1
