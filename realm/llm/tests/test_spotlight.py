"""Tests for SpotlightAnnotator (mocked backend)."""

from __future__ import annotations

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.llm.interfaces import ILLMBackend, LLMResponse
from realm.llm.spotlight import SpotlightAnnotator, get_post_body
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


class CannedBackend(ILLMBackend):
    def __init__(self, body: str = "A fascinating day for tech enthusiasts everywhere."):
        self._body = body
        self.call_count = 0

    @property
    def backend_name(self): return "canned"
    @property
    def model(self): return "canned-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        self.call_count += 1
        return LLMResponse(content=self._body, model=self.model)


@pytest.fixture
def sim_with_posts():
    agents = AgentFactory().build_batch(
        WorldGenerator(master_seed=42).generate(40)
    )
    clock = Clock.from_config()
    net = NetworkTopology(agents, NetworkConfig(local_k=4))
    net.build(clock.rng("network"))
    modulator = TransitModulator.from_config(get_astro_engine("auto"))
    sim = SimulationEngine(
        agents=agents, network=net, modulator=modulator,
        platforms=[SocialMediaPlatform(memory_ticks=5, virality_threshold=1.3)],
        clock=clock,
    )
    sim.run(3)
    return sim


class TestSpotlight:
    def test_annotates_top_posts(self, sim_with_posts):
        backend = CannedBackend()
        annotator = SpotlightAnnotator(
            backend=backend, ratio=0.3, max_posts_per_tick=3, min_virality=0.0,
        )
        updated = annotator.annotate_tick(sim_with_posts)
        assert len(updated) > 0
        assert backend.call_count == len(updated)
        # Bodies attached via sidecar
        platform = sim_with_posts.platforms[0]
        for post in updated:
            body = get_post_body(platform, post.post_id)
            assert body == backend._body

    def test_no_backend_is_noop(self, sim_with_posts):
        annotator = SpotlightAnnotator(
            backend=None, router=_NullRouter(), ratio=0.3,
        )
        assert not annotator.is_enabled()
        assert annotator.annotate_tick(sim_with_posts) == []

    def test_idempotent_per_post(self, sim_with_posts):
        """Re-running annotate_tick on the same posts doesn't re-call the LLM."""
        backend = CannedBackend()
        annotator = SpotlightAnnotator(
            backend=backend, ratio=0.5, max_posts_per_tick=5, min_virality=0.0,
        )
        annotator.annotate_tick(sim_with_posts)
        before = backend.call_count
        second = annotator.annotate_tick(sim_with_posts)
        assert backend.call_count == before   # no extra calls
        assert len(second) == 0


class _NullRouter:
    def for_task(self, task):
        from realm.llm.interfaces import LLMBackendError
        raise LLMBackendError("no llm")
