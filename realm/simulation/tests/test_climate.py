"""Tests for ClimateEngine and the Phase 5 collective modifier layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("skyfield")

from realm.astro.factory import get_astro_engine
from realm.simulation.climate import (
    ClimateEngine,
    compute_moon_phase,
    detect_eclipse,
)
from realm.simulation.transit_modulator import TransitModulator


@pytest.fixture(scope="module")
def modulator():
    return TransitModulator.from_config(get_astro_engine("auto"))


@pytest.fixture(scope="module")
def climate(modulator):
    return ClimateEngine(modulator=modulator)


class TestMoonPhase:
    def test_new_moon_near_zero(self):
        assert compute_moon_phase(0.0, 10.0) == "new"
        assert compute_moon_phase(0.0, 350.0) == "new"

    def test_waxing_quadrant(self):
        assert compute_moon_phase(0.0, 90.0) == "waxing"

    def test_full_moon_near_180(self):
        assert compute_moon_phase(0.0, 180.0) == "full"
        assert compute_moon_phase(0.0, 200.0) == "full"

    def test_waning_quadrant(self):
        assert compute_moon_phase(0.0, 270.0) == "waning"


class TestClimateCompute:
    def test_returns_dict_of_trait_modifiers(self, climate):
        sim_time = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
        mods = climate.compute(sim_time)
        assert isinstance(mods, dict)
        from realm.personality.trait_vector import TraitVector
        valid = set(TraitVector.trait_names())
        for trait in mods:
            assert trait in valid

    def test_modifiers_stay_small(self, climate):
        """Even at maxed-out configuration, no single trait should move > 0.20
        from climate alone (clip + dampening). Lets natal dominance remain."""
        sim_time = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
        mods = climate.compute(sim_time)
        for trait, delta in mods.items():
            assert abs(delta) < 0.25, f"{trait}={delta}"

    def test_deterministic(self, climate):
        sim_time = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
        a = climate.compute(sim_time)
        b = climate.compute(sim_time)
        assert a == b

    def test_differs_across_years(self, climate):
        """Outer planet signs change over decades — 2026 vs 1985 climates should
        produce measurably different modifier dicts."""
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(1985, 1, 1, tzinfo=UTC)
        climate.modulator.reset_cache()
        m1 = climate.compute(t1)
        climate.modulator.reset_cache()
        m2 = climate.compute(t2)
        assert m1 != m2


class TestFeatureToggles:
    def test_disable_outer_planets(self, modulator):
        ce = ClimateEngine(
            modulator=modulator,
            include_outer_planets=False,
            include_retrogrades=False,
            include_eclipses=False,
        )
        sim_time = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
        mods = ce.compute(sim_time)
        # Only moon phase is active — it produces at most 4 traits.
        assert len(mods) <= 4

    def test_everything_off_returns_empty(self, modulator):
        ce = ClimateEngine(
            modulator=modulator,
            include_outer_planets=False,
            include_moon_phase=False,
            include_eclipses=False,
            include_retrogrades=False,
        )
        mods = ce.compute(datetime(2026, 4, 23, tzinfo=UTC))
        assert mods == {}


class TestDescribe:
    def test_describe_returns_structured_snapshot(self, climate):
        sim_time = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
        snap = climate.describe(sim_time)
        assert "outer_planets" in snap
        assert "moon_phase" in snap
        assert snap["moon_phase"] in {"new", "waxing", "full", "waning"}
        assert "retrograde" in snap
        assert "eclipse" in snap

    def test_outer_planets_include_pluto(self, climate):
        snap = climate.describe(datetime(2026, 4, 23, tzinfo=UTC))
        assert "Pluto" in snap["outer_planets"]


class TestEclipseDetection:
    def test_conjunction_near_node_is_solar(self):
        # Synthesize positions: Sun & Moon at 10°, North Node at 10°
        from realm.core.types import PlanetPosition
        def mk(name, lon):
            return PlanetPosition(
                name=name, longitude=lon, latitude=0, sign="Aries",
                sign_degree=lon, house=1, is_retrograde=False, speed=1.0,
            )
        positions = (
            mk("Sun", 10.0),
            mk("Moon", 12.0),
            mk("North_Node", 11.0),
        )
        assert detect_eclipse(positions) == "solar"

    def test_opposition_near_node_is_lunar(self):
        from realm.core.types import PlanetPosition
        def mk(name, lon):
            return PlanetPosition(
                name=name, longitude=lon, latitude=0, sign="Aries",
                sign_degree=lon, house=1, is_retrograde=False, speed=1.0,
            )
        positions = (
            mk("Sun", 0.0),
            mk("Moon", 180.0),
            mk("North_Node", 178.0),
        )
        assert detect_eclipse(positions) == "lunar"

    def test_no_node_alignment_returns_none(self):
        from realm.core.types import PlanetPosition
        def mk(name, lon):
            return PlanetPosition(
                name=name, longitude=lon, latitude=0, sign="Aries",
                sign_degree=lon, house=1, is_retrograde=False, speed=1.0,
            )
        positions = (
            mk("Sun", 0.0),
            mk("Moon", 5.0),
            mk("North_Node", 90.0),   # nowhere near Sun/Moon
        )
        assert detect_eclipse(positions) is None


class TestSimulationIntegration:
    def test_engine_with_climate(self, modulator):
        from realm.agents.factory import AgentFactory
        from realm.demographics.world_generator import WorldGenerator
        from realm.simulation.clock import Clock
        from realm.simulation.engine import SimulationEngine
        from realm.simulation.network import NetworkConfig, NetworkTopology
        from realm.simulation.platforms.social_media import SocialMediaPlatform

        agents = AgentFactory().build_batch(
            WorldGenerator(master_seed=42).generate(20)
        )
        clock = Clock.from_config()
        net = NetworkTopology(agents, NetworkConfig(local_k=4))
        net.build(clock.rng("network"))
        sim = SimulationEngine(
            agents=agents, network=net, modulator=modulator,
            platforms=[SocialMediaPlatform()], clock=clock,
            climate=ClimateEngine(modulator),
        )
        sim.run(3)
        assert len(sim.history) == 3

    def test_climate_shifts_effective_traits(self, modulator):
        """Engine applies collective modifier before individual transits; agent's
        effective traits in a climate-enabled run differ from natal baseline."""
        from realm.agents.factory import AgentFactory
        from realm.demographics.world_generator import WorldGenerator

        agent = AgentFactory().build_batch(
            WorldGenerator(master_seed=42).generate(1)
        )[0]
        sim_time = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)

        climate = ClimateEngine(modulator)
        collective = climate.compute(sim_time)
        assert collective, "expected non-empty collective modifier"

        baseline = agent.traits
        after_climate = baseline.apply_modifier(collective)
        # At least one trait should differ from baseline (bounded but measurable)
        diffs = [
            abs(getattr(after_climate, n) - getattr(baseline, n))
            for n in baseline.trait_names()
        ]
        assert max(diffs) > 0.005, "climate produced no measurable trait shift"
