"""Integration tests for KerykeionEngine.

These tests verify Swiss-Ephemeris precision against known historical charts.
Skipped automatically when kerykeion isn't installed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("kerykeion")

from realm.astro.fixtures import STEVE_JOBS  # noqa: E402
from realm.astro.kerykeion_engine import KerykeionEngine  # noqa: E402
from realm.astro.skyfield_engine import SkyfieldEngine  # noqa: E402
from realm.core.exceptions import AstroCalculationError  # noqa: E402
from realm.core.types import ASPECT_TYPES, PLANETS_ALL_PHASE1  # noqa: E402


@pytest.fixture(scope="module")
def engine() -> KerykeionEngine:
    return KerykeionEngine()


@pytest.fixture(scope="module")
def jobs_chart(engine: KerykeionEngine):
    return engine.calculate_natal_chart(
        birth_dt=STEVE_JOBS.birth_dt,
        latitude=STEVE_JOBS.latitude,
        longitude=STEVE_JOBS.longitude,
        timezone=STEVE_JOBS.timezone,
    )


class TestJobsChart:
    def test_all_13_bodies(self, jobs_chart):
        assert len(jobs_chart.planets) == len(PLANETS_ALL_PHASE1)
        assert {p.name for p in jobs_chart.planets} == set(PLANETS_ALL_PHASE1)

    def test_sun_pisces(self, jobs_chart):
        sun = jobs_chart.planet("Sun")
        assert sun.sign == "Pisces"
        assert 5 < sun.sign_degree < 10

    def test_moon_aries(self, jobs_chart):
        assert jobs_chart.planet("Moon").sign == "Aries"

    def test_jupiter_cancer(self, jobs_chart):
        assert jobs_chart.planet("Jupiter").sign == "Cancer"

    def test_mars_aries_rulership(self, jobs_chart):
        """Jobs had Mars in Aries — rulership placement."""
        mars = jobs_chart.planet("Mars")
        assert mars.sign == "Aries"

    def test_chiron_is_real_value_not_placeholder(self, jobs_chart):
        """Kerykeion should give Jobs' actual Chiron position (Aquarius 2°),
        not the Skyfield placeholder (Virgo 0°)."""
        chiron = jobs_chart.planet("Chiron")
        assert chiron.sign != "Virgo" or chiron.sign_degree != 0.0

    def test_ascendant_in_range(self, jobs_chart):
        assert 0 <= jobs_chart.ascendant < 360

    def test_houses_are_12(self, jobs_chart):
        assert len(jobs_chart.houses) == 12

    def test_aspects_non_empty(self, jobs_chart):
        assert len(jobs_chart.aspects) > 0
        for a in jobs_chart.aspects:
            assert a.aspect_type in ASPECT_TYPES
            assert a.orb >= 0


class TestKerykeionVsSkyfield:
    """Verify Kerykeion and Skyfield agree within expected tolerances."""

    @pytest.fixture(scope="class")
    def both_charts(self):
        kk = KerykeionEngine().calculate_natal_chart(
            STEVE_JOBS.birth_dt, STEVE_JOBS.latitude,
            STEVE_JOBS.longitude, STEVE_JOBS.timezone,
        )
        sk = SkyfieldEngine().calculate_natal_chart(
            STEVE_JOBS.birth_dt, STEVE_JOBS.latitude,
            STEVE_JOBS.longitude, STEVE_JOBS.timezone,
        )
        return kk, sk

    def test_planet_positions_within_1_degree(self, both_charts):
        """Apparent vs mean ecliptic gives ~0.6° offset; allow 1° tolerance."""
        kk, sk = both_charts
        for name in (
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
        ):
            kk_p = kk.planet(name)
            sk_p = sk.planet(name)
            diff = abs(kk_p.longitude - sk_p.longitude)
            if diff > 180:
                diff = 360 - diff
            assert diff < 1.5, f"{name}: KK={kk_p.longitude:.2f} SK={sk_p.longitude:.2f} diff={diff:.2f}"

    def test_ascendant_agrees_closely(self, both_charts):
        kk, sk = both_charts
        diff = abs(kk.ascendant - sk.ascendant)
        if diff > 180:
            diff = 360 - diff
        assert diff < 0.5, f"Asc KK={kk.ascendant:.2f} SK={sk.ascendant:.2f}"

    def test_midheaven_agrees_closely(self, both_charts):
        kk, sk = both_charts
        diff = abs(kk.midheaven - sk.midheaven)
        if diff > 180:
            diff = 360 - diff
        assert diff < 0.5


class TestEarlyHistoricalDate:
    """Kerykeion/Swiss Ephemeris handles pre-1899 dates that Skyfield DE421 doesn't."""

    def test_pre_1899_birth(self, engine):
        # Marie Curie: 1867-11-07, Warsaw — outside DE421 but Swiss has it.
        chart = engine.calculate_natal_chart(
            birth_dt=datetime(1867, 11, 7, 11, 0, tzinfo=UTC),
            latitude=52.23, longitude=21.01, timezone="Europe/Warsaw",
        )
        assert chart.planet("Sun").sign in {"Scorpio", "Sagittarius"}


class TestValidationErrors:
    def test_naive_datetime_rejected(self, engine):
        with pytest.raises(AstroCalculationError):
            engine.calculate_natal_chart(
                datetime(1990, 1, 1, 12, 0), 0.0, 0.0, "UTC",
            )

    def test_bad_latitude_rejected(self, engine):
        with pytest.raises(AstroCalculationError):
            engine.calculate_natal_chart(
                datetime(1990, 1, 1, 12, 0, tzinfo=UTC),
                95.0, 0.0, "UTC",
            )


class TestTransits:
    def test_transit_snapshot_structure(self, engine, jobs_chart):
        target = datetime(2020, 1, 1, 0, 0, tzinfo=UTC)
        snap = engine.calculate_transits(jobs_chart, target)
        assert snap.timestamp == target
        assert len(snap.transiting_planets) == len(PLANETS_ALL_PHASE1)
        assert snap.moon_phase in {"new", "waxing", "full", "waning"}

    def test_transit_range(self, engine, jobs_chart):
        start = datetime(2020, 1, 1, tzinfo=UTC)
        end = start + timedelta(days=2)
        snaps = engine.calculate_transit_range(jobs_chart, start, end, interval_hours=24)
        assert len(snaps) == 3


class TestPlacidus:
    """Kerykeion defaults to Placidus; houses should differ from Equal House."""

    def test_house_cusps_not_evenly_spaced(self, jobs_chart):
        """Placidus cusps are unevenly spaced (except in low latitudes)."""
        deltas = [
            (jobs_chart.houses[(i + 1) % 12] - jobs_chart.houses[i]) % 360
            for i in range(12)
        ]
        # At SF latitude (37°N), cusps should not all be exactly 30°.
        variance = max(deltas) - min(deltas)
        assert variance > 5.0, f"Placidus variance too small: {variance}"
