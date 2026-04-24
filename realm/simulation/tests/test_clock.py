"""Tests for simulation.Clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from realm.simulation.clock import Clock, parse_interval


class TestParseInterval:
    def test_hour(self):
        assert parse_interval("1h") == timedelta(hours=1)

    def test_day(self):
        assert parse_interval("1d") == timedelta(days=1)

    def test_bad_value_raises(self):
        with pytest.raises(ValueError):
            parse_interval("zap")


class TestClockBasics:
    def test_default_tick_is_zero(self):
        c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                  interval=timedelta(days=1))
        assert c.tick == 0

    def test_sim_time_is_epoch_at_tick_zero(self):
        epoch = datetime(2026, 1, 1, tzinfo=UTC)
        c = Clock(epoch=epoch, interval=timedelta(days=1))
        assert c.sim_time == epoch

    def test_advance_by_one_day(self):
        epoch = datetime(2026, 1, 1, tzinfo=UTC)
        c = Clock(epoch=epoch, interval=timedelta(days=1))
        c.advance()
        assert c.tick == 1
        assert c.sim_time == epoch + timedelta(days=1)

    def test_advance_multiple(self):
        c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                  interval=timedelta(hours=4))
        c.advance(6)
        assert c.tick == 6
        assert c.sim_time.hour == 0  # 6 * 4h = 24h → next day 00:00
        assert c.sim_time.day == 2

    def test_advance_zero_raises(self):
        c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                  interval=timedelta(days=1))
        with pytest.raises(ValueError):
            c.advance(0)


class TestRNG:
    def test_rng_deterministic_within_tick(self):
        c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                  interval=timedelta(days=1), master_seed=42)
        r1 = c.rng("transits")
        # Same subsystem + same tick returns SAME generator object (cached)
        assert c.rng("transits") is r1

    def test_rng_different_subsystems_different_streams(self):
        c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                  interval=timedelta(days=1), master_seed=42)
        a = c.rng("transits").random()
        b = c.rng("decisions").random()
        assert a != b

    def test_rng_different_ticks_different_streams(self):
        c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                  interval=timedelta(days=1), master_seed=42)
        v1 = c.rng("x").random()
        c.advance()
        v2 = c.rng("x").random()
        assert v1 != v2

    def test_same_seed_reproducible_across_instances(self):
        def draw():
            c = Clock(epoch=datetime(2026, 1, 1, tzinfo=UTC),
                      interval=timedelta(days=1), master_seed=999)
            samples = []
            for _ in range(3):
                samples.append(c.rng("decisions").random())
                c.advance()
            return samples
        assert draw() == draw()


class TestFromConfig:
    def test_loads_from_realm_config(self):
        c = Clock.from_config()
        assert c.master_seed == 42
        assert c.interval == timedelta(days=1)  # realm.yaml: tick_interval=1d
        assert c.tick == 0
