"""Tests for TransitModulator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from realm.astro.factory import get_astro_engine
from realm.astro.fixtures import STEVE_JOBS
from realm.simulation.transit_modulator import TransitModulator


@pytest.fixture(scope="module")
def jobs_natal():
    engine = get_astro_engine("auto")
    return engine.calculate_natal_chart(
        STEVE_JOBS.birth_dt, STEVE_JOBS.latitude,
        STEVE_JOBS.longitude, STEVE_JOBS.timezone,
    )


@pytest.fixture(scope="module")
def modulator():
    return TransitModulator.from_config(get_astro_engine("auto"))


class TestBasic:
    def test_transit_positions_returns_bodies(self, modulator):
        sim_time = datetime(2020, 6, 15, 12, 0, tzinfo=UTC)
        positions = modulator.transit_positions(sim_time)
        names = {p.name for p in positions}
        # Should include at least the 10 classic bodies
        classics = {"Sun", "Moon", "Mercury", "Venus", "Mars",
                    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
        assert classics <= names

    def test_cache_returns_same_object_on_repeat(self, modulator):
        modulator.reset_cache()
        sim_time = datetime(2020, 6, 15, tzinfo=UTC)
        p1 = modulator.transit_positions(sim_time)
        p2 = modulator.transit_positions(sim_time)
        # Identity check — cache should return the exact same tuple
        assert p1 is p2

    def test_cache_invalidated_on_different_time(self, modulator):
        modulator.reset_cache()
        a = modulator.transit_positions(datetime(2020, 1, 1, tzinfo=UTC))
        b = modulator.transit_positions(datetime(2020, 7, 1, tzinfo=UTC))
        assert a is not b


class TestModifierComputation:
    def test_modifiers_are_bounded(self, modulator, jobs_natal):
        sim_time = datetime(2020, 6, 15, tzinfo=UTC)
        mods = modulator.compute_modifiers(jobs_natal, sim_time)
        # No single modifier should exceed ±0.15 (soft bound from dampening)
        for trait, delta in mods.items():
            assert abs(delta) <= 0.20, f"{trait}={delta}"

    def test_some_aspects_produce_modifiers(self, modulator, jobs_natal):
        """In any given month, some transit aspects should exist."""
        sim_time = datetime(2020, 6, 15, tzinfo=UTC)
        mods = modulator.compute_modifiers(jobs_natal, sim_time)
        # Should be non-empty for a populous moment
        assert len(mods) > 0

    def test_deterministic_same_inputs(self, modulator, jobs_natal):
        sim_time = datetime(2020, 6, 15, tzinfo=UTC)
        a = modulator.compute_modifiers(jobs_natal, sim_time)
        b = modulator.compute_modifiers(jobs_natal, sim_time)
        assert a == b


class TestApplyTo:
    def test_apply_returns_bounded_vector(self, modulator, jobs_natal):
        from realm.personality.embedder import get_personality_embedder
        embedder = get_personality_embedder("rule_based")
        base = embedder.embed(jobs_natal)

        sim_time = datetime(2020, 6, 15, tzinfo=UTC)
        modulated = modulator.apply_to(base, jobs_natal, sim_time)

        for name, val in modulated.to_dict().items():
            assert 0.0 <= val <= 1.0, f"{name}={val}"


class TestPerformanceDecoupling:
    """Verify one ephemeris call is shared across many agents (the whole point of decoupling)."""

    def test_multiple_calls_same_time_cached(self, modulator, jobs_natal):
        modulator.reset_cache()
        sim_time = datetime(2020, 6, 15, tzinfo=UTC)
        # Call compute_modifiers many times — should only hit ephemeris once.
        call_count = 0
        orig = modulator.astro_engine.calculate_natal_chart

        def counting_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return orig(*args, **kwargs)

        modulator.astro_engine.calculate_natal_chart = counting_call  # type: ignore
        try:
            for _ in range(20):
                modulator.compute_modifiers(jobs_natal, sim_time)
        finally:
            modulator.astro_engine.calculate_natal_chart = orig  # type: ignore

        assert call_count == 1, f"expected 1 ephemeris call, got {call_count}"


class TestOverTime:
    def test_modifiers_drift_over_months(self, modulator, jobs_natal):
        """Modifiers should change as transits move."""
        modulator.reset_cache()
        t0 = datetime(2020, 1, 1, tzinfo=UTC)
        t1 = t0 + timedelta(days=180)  # 6 months later
        m0 = modulator.compute_modifiers(jobs_natal, t0)
        m1 = modulator.compute_modifiers(jobs_natal, t1)
        assert m0 != m1
