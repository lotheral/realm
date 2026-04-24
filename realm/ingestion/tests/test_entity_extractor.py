"""Tests for entity / topic / sentiment extraction."""

from __future__ import annotations

from datetime import UTC, datetime

from realm.ingestion.entity_extractor import (
    EnrichingProcessor,
    classify_topic,
    detect_geography,
    extract_entities,
    score_sentiment,
)
from realm.ingestion.interfaces import SeedEvent


class TestTopicClassification:
    def test_politics(self):
        text = "The Senate voted on a new treaty after the president's announcement"
        assert classify_topic(text) == "politics"

    def test_tech(self):
        text = "OpenAI released a new GPU-accelerated LLM for machine learning applications"
        assert classify_topic(text) == "tech"

    def test_finance(self):
        text = "Stock market plunged as inflation concerns drove the federal reserve to raise interest rates"
        assert classify_topic(text) == "finance"

    def test_defaults_to_news(self):
        assert classify_topic("") == "news"
        assert classify_topic("xyz random words") == "news"


class TestSentiment:
    def test_positive(self):
        s = score_sentiment("A wonderful breakthrough and great success for the team")
        assert s > 0.5

    def test_negative(self):
        s = score_sentiment("Disaster and crisis: many dead after the attack and collapse")
        assert s < -0.5

    def test_neutral_on_empty(self):
        assert score_sentiment("") == 0.0

    def test_neutral_no_keywords(self):
        assert score_sentiment("The cat sat on the mat") == 0.0

    def test_negation_flips(self):
        # Without negation: positive. With "not": sentiment should be negative.
        pos = score_sentiment("a great success")
        neg = score_sentiment("not a great success")
        assert pos > 0
        assert neg < pos


class TestEntityExtraction:
    def test_extracts_proper_nouns(self):
        text = "Apple and Microsoft announced a partnership in Silicon Valley"
        entities = extract_entities(text)
        joined = " | ".join(entities)
        assert "Apple" in joined
        assert "Microsoft" in joined
        assert "Silicon Valley" in joined

    def test_drops_sentence_start_false_positives(self):
        # "The quick brown fox" — "The" is lowercased at sentence start
        entities = extract_entities("The quick brown fox jumped")
        assert "The" not in entities

    def test_ignores_common_stopwords(self):
        entities = extract_entities("Monday is a new day")
        assert "Monday" not in entities

    def test_max_entities_limit(self):
        text = " ".join(f"Entity{i}" for i in range(20))
        result = extract_entities(text, max_entities=5)
        assert len(result) <= 5

    def test_empty_input(self):
        assert extract_entities("") == ()


class TestGeographyDetection:
    def test_known_country(self):
        # "China" should map to CN
        assert detect_geography("Chinese officials visited the region") == "CN" or \
               detect_geography("Talks about China economic policy") == "CN"

    def test_unknown_returns_none(self):
        assert detect_geography("No countries here") is None


class TestEnrichingProcessor:
    def test_fills_missing_fields(self):
        proc = EnrichingProcessor()
        e = SeedEvent(
            event_id="e1", source="t",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            headline="Apple stock crashed on bad inflation news",
            body="Markets plunged after the federal reserve announcement",
        )
        out = proc.process([e])
        assert len(out) == 1
        enriched = out[0]
        assert enriched.topic == "finance"
        assert enriched.sentiment < 0
        assert any("Apple" in ent for ent in enriched.entities)

    def test_preserves_existing_fields(self):
        proc = EnrichingProcessor()
        e = SeedEvent(
            event_id="e1", source="t",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            headline="something",
            topic="tech",                  # already set
            sentiment=0.7,                 # already set
            entities=("Preset",),          # already set
            geography="TR",                # already set
        )
        out = proc.process([e])[0]
        assert out.topic == "tech"
        assert out.sentiment == 0.7
        assert out.entities == ("Preset",)
        assert out.geography == "TR"
