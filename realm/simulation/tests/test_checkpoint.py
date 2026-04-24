"""Round-trip tests for checkpoint save/load/restore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.simulation import checkpoint as ckpt
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


def _build_sim(master_seed: int = 42, n_agents: int = 20) -> SimulationEngine:
    agents = AgentFactory().build_batch(
        WorldGenerator(master_seed=master_seed).generate(n_agents)
    )
    clock = Clock(
        epoch=datetime(2026, 1, 1, tzinfo=UTC),
        interval=timedelta(days=1), master_seed=master_seed,
    )
    net = NetworkTopology(agents, NetworkConfig(local_k=4, rewire_p=0.1))
    net.build(clock.rng("network"))
    mod = TransitModulator.from_config(get_astro_engine("auto"))
    plat = SocialMediaPlatform(memory_ticks=3)
    return SimulationEngine(agents, net, mod, [plat], clock)


class TestSaveLoad:
    def test_round_trip_preserves_tick(self, tmp_path):
        sim = _build_sim()
        sim.run(5)
        path = tmp_path / "ckpt.bin"
        ckpt.save(sim, path)
        payload = ckpt.load(path)
        assert payload.tick == sim.clock.tick
        assert payload.master_seed == 42
        assert len(payload.history) == 5

    def test_version_check(self, tmp_path):
        sim = _build_sim()
        sim.run(2)
        path = ckpt.save(sim, tmp_path / "ckpt.bin")
        payload = ckpt.load(path)
        assert payload.version == ckpt.CHECKPOINT_VERSION


class TestRestoreEquivalence:
    def test_continuation_equals_single_run(self, tmp_path):
        """run(10) should produce same final state as run(5) → checkpoint → resume → run(5)."""
        # Single run
        sim_a = _build_sim()
        sim_a.run(10)
        final_a = (
            sim_a.clock.tick,
            sim_a.aggregate_stats(),
            sim_a.platforms[0].total_posts(),
            sim_a.platforms[0].total_engagements(),
        )

        # Checkpoint + resume
        sim_b = _build_sim()
        sim_b.run(5)
        path = ckpt.save(sim_b, tmp_path / "ckpt.bin")

        sim_c = _build_sim()
        ckpt.restore_into(sim_c, ckpt.load(path))
        sim_c.run(5)
        final_c = (
            sim_c.clock.tick,
            sim_c.aggregate_stats(),
            sim_c.platforms[0].total_posts(),
            sim_c.platforms[0].total_engagements(),
        )

        assert final_a == final_c


class TestValidation:
    def test_master_seed_mismatch_rejects(self, tmp_path):
        sim_a = _build_sim(master_seed=42)
        sim_a.run(2)
        path = ckpt.save(sim_a, tmp_path / "ckpt.bin")

        sim_b = _build_sim(master_seed=999)
        with pytest.raises(ValueError, match="master_seed"):
            ckpt.restore_into(sim_b, ckpt.load(path))

    def test_agent_count_mismatch_rejects(self, tmp_path):
        sim_a = _build_sim(n_agents=20)
        sim_a.run(2)
        path = ckpt.save(sim_a, tmp_path / "ckpt.bin")

        sim_b = _build_sim(n_agents=10)
        with pytest.raises(ValueError, match="agent count"):
            ckpt.restore_into(sim_b, ckpt.load(path))
