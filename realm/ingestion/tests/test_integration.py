"""End-to-end integration test: ingestion → simulation → agents."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("skyfield")

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.demographics.world_generator import WorldGenerator
from realm.ingestion.entity_extractor import EnrichingProcessor
from realm.ingestion.interfaces import SeedEvent
from realm.ingestion.knowledge_graph import KnowledgeGraph
from realm.ingestion.manager import IngestionManager
from realm.ingestion.sources.manual_upload import ManualUploadSource
from realm.simulation.clock import Clock
from realm.simulation.engine import SimulationEngine
from realm.simulation.network import NetworkConfig, NetworkTopology
from realm.simulation.platforms.news_channel import NewsChannelPlatform
from realm.simulation.platforms.social_media import SocialMediaPlatform
from realm.simulation.transit_modulator import TransitModulator


class TestIngestionManager:
    def test_pull_pipes_through_processors_and_sinks(self):
        src = ManualUploadSource(source_id="test")
        src.enqueue_many([
            SeedEvent(
                event_id="e1", source="test",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline="OpenAI shipped a new LLM that boosted developer productivity",
            ),
            SeedEvent(
                event_id="e2", source="test",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline="Financial crisis deepens as banks fail across Europe",
            ),
        ])
        kg = KnowledgeGraph()
        news = NewsChannelPlatform(memory_ticks=3)
        mgr = IngestionManager(
            sources=[src],
            processors=[EnrichingProcessor()],
            knowledge_graph=kg,
            news_channel=news,
        )
        events = mgr.pull(tick=0)
        assert len(events) == 2
        # Topic enrichment worked
        topics = {e.topic for e in events}
        assert "tech" in topics
        assert "finance" in topics
        # KG populated
        nodes, _ = kg.size()
        assert nodes > 0
        # News channel has 2 posts queued for tick 0
        news.advance(0)
        assert len(news.current_tick_posts()) == 2


class TestNewsChannelFeed:
    def test_country_gated_visibility(self):
        nc = NewsChannelPlatform(memory_ticks=3)
        nc.advance(0)
        nc.publish_events([
            SeedEvent(
                event_id="g1", source="t",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline="Global news", geography=None,
            ),
            SeedEvent(
                event_id="g2", source="t",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline="Tr-local news", geography="TR",
            ),
            SeedEvent(
                event_id="g3", source="t",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline="US-local news", geography="US",
            ),
        ], tick=0)

        tr_feed = nc.visible_for("TR")
        us_feed = nc.visible_for("US")
        # TR sees Global + TR
        assert len(tr_feed) == 2
        # US sees Global + US
        assert len(us_feed) == 2
        # Neither sees the other's local news
        tr_ids = {p.post_id for p in tr_feed}
        us_ids = {p.post_id for p in us_feed}
        assert tr_ids & us_ids  # Global post is in both
        assert tr_ids != us_ids


class TestSimulationWithNews:
    def test_news_injected_into_tick(self):
        """Run a mini simulation with news injection and verify agents engage with news."""
        gen = WorldGenerator(master_seed=42)
        factory = AgentFactory()
        agents = factory.build_batch(gen.generate(30))

        clock = Clock.from_config()
        network = NetworkTopology(agents, NetworkConfig(local_k=6))
        network.build(clock.rng("network"))
        modulator = TransitModulator.from_config(get_astro_engine("auto"))
        social = SocialMediaPlatform(memory_ticks=5)
        news = NewsChannelPlatform(memory_ticks=5)

        # Preload news events
        src = ManualUploadSource()
        src.enqueue_many([
            SeedEvent(
                event_id=f"news_{i}", source="test",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline=f"Breaking story #{i}",
                topic="news", sentiment=-0.5, virality=3.0,
                entities=("Apple", "China") if i % 2 == 0 else ("Jobs", "Tim"),
            )
            for i in range(5)
        ])
        kg = KnowledgeGraph()
        mgr = IngestionManager(
            sources=[src], processors=[], knowledge_graph=kg, news_channel=news,
        )

        sim = SimulationEngine(
            agents=agents, network=network, modulator=modulator,
            platforms=[social, news], clock=clock,
            pre_tick_hooks=[lambda t: mgr.pull(t)],
        )
        sim.run(3)

        # News channel should have received the 5 events at tick 0
        assert news.total_posts() == 5
        # Some news posts should have engagement after 3 ticks
        engaged = [p for p in news.top_posts(10) if p.engagement > 0]
        assert len(engaged) > 0

    def test_determinism_with_news(self):
        def run():
            gen = WorldGenerator(master_seed=7)
            factory = AgentFactory()
            agents = factory.build_batch(gen.generate(20))
            clock = Clock.from_config()
            clock.master_seed = 7
            net = NetworkTopology(agents, NetworkConfig(local_k=4))
            net.build(clock.rng("network"))
            mod = TransitModulator.from_config(get_astro_engine("auto"))
            social = SocialMediaPlatform()
            news = NewsChannelPlatform()
            src = ManualUploadSource()
            src.enqueue(SeedEvent(
                event_id="same", source="test",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                headline="same story", sentiment=-0.3, virality=2.0,
            ))
            mgr = IngestionManager(
                sources=[src], processors=[], knowledge_graph=None, news_channel=news,
            )
            sim = SimulationEngine(
                agents=agents, network=net, modulator=mod,
                platforms=[social, news], clock=clock,
                pre_tick_hooks=[lambda t: mgr.pull(t)],
            )
            sim.run(3)
            return [(s.tick, s.posts, s.engagements) for s in sim.history]

        assert run() == run()
