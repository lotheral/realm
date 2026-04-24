"""AgentFactory routing tests — verify adapter type drives the right pipeline.

- BigFiveAdapter path: skips astro engine, requires profile.big_five_scores
- DemographicAdapter path: skips astro AND skips CulturalModifier
- AstrologicalAdapter path (default): behavior unchanged, natal_chart populated
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from realm.agents.factory import AgentFactory
from realm.astro.factory import get_astro_engine
from realm.core.exceptions import PersonalityEmbeddingError
from realm.culture.modifier import CulturalModifier
from realm.demographics.interfaces import DemographicProfile
from realm.personality.adapters import (
    AstrologicalAdapter,
    BigFiveAdapter,
    DemographicAdapter,
)
from realm.personality.rule_based import RuleBasedEmbedder


def _profile(big_five=None) -> DemographicProfile:
    return DemographicProfile(
        agent_id="test-rt-1",
        name_first="Routing", name_last="Test",
        gender="X",
        country="US", city="San Francisco",
        birth_datetime=datetime(1985, 6, 15, 12, 0, tzinfo=UTC),
        birth_latitude=37.77, birth_longitude=-122.42,
        birth_timezone="America/Los_Angeles",
        age_years=40,
        profession_code="2-T", profession_name="software engineer",
        income_annual_usd=120000.0,
        education_level="bachelor",
        marginal_flag=False, marginal_category=None,
        primary_religion="non-religious", region="americas",
        big_five_scores=big_five,
    )


class _CountingAstroEngine:
    """Wraps real astro engine, counts calculate_natal_chart calls."""

    def __init__(self):
        self._inner = get_astro_engine("auto")
        self.call_count = 0

    @property
    def backend_name(self) -> str:
        return self._inner.backend_name

    def calculate_natal_chart(self, **kwargs):
        self.call_count += 1
        return self._inner.calculate_natal_chart(**kwargs)


class _CountingCulturalModifier:
    """Wraps real CulturalModifier, counts apply() calls."""

    def __init__(self):
        self._inner = CulturalModifier()
        self.call_count = 0

    def apply(self, traits, profile):
        self.call_count += 1
        return self._inner.apply(traits, profile)


class TestAstrologicalPath:
    def test_default_adapter_computes_chart(self):
        """Without specifying adapter, AstrologicalAdapter is default — chart built."""
        counting = _CountingAstroEngine()
        factory = AgentFactory(astro_engine=counting)
        agent = factory.build(_profile())
        assert counting.call_count == 1
        assert agent.natal_chart is not None
        assert len(agent.natal_chart.planets) > 0

    def test_explicit_astrological_adapter_computes_chart(self):
        counting = _CountingAstroEngine()
        factory = AgentFactory(
            astro_engine=counting,
            adapter=AstrologicalAdapter(RuleBasedEmbedder()),
        )
        agent = factory.build(_profile())
        assert counting.call_count == 1
        assert agent.natal_chart is not None


class TestBigFivePath:
    def test_builds_without_astro_call(self):
        counting = _CountingAstroEngine()
        factory = AgentFactory(astro_engine=counting, adapter=BigFiveAdapter())
        bf = {"openness": 0.8, "conscientiousness": 0.7, "extraversion": 0.6,
              "agreeableness": 0.5, "neuroticism": 0.4}
        agent = factory.build(_profile(big_five=bf))
        assert counting.call_count == 0, "BigFive path must NOT call astro engine"
        assert agent.natal_chart is None

    def test_raises_when_profile_lacks_big_five_scores(self):
        factory = AgentFactory(adapter=BigFiveAdapter())
        with pytest.raises(PersonalityEmbeddingError,
                           match="big_five_scores"):
            factory.build(_profile(big_five=None))

    def test_big_five_values_reach_agent_traits(self):
        """When no cultural modifier or calibration distorts, BF values survive."""
        from realm.personality.calibration import TraitCalibrator
        factory = AgentFactory(
            adapter=BigFiveAdapter(),
            calibrator=TraitCalibrator(enabled=False),
        )
        bf = {"openness": 0.82, "conscientiousness": 0.71, "extraversion": 0.63,
              "agreeableness": 0.55, "neuroticism": 0.34}
        agent = factory.build(_profile(big_five=bf))
        # Cultural modifier still applies (blend_ratio=0.3) so values shift a bit.
        # Use a loose sanity range that proves the openness input reached the pipeline.
        assert 0.70 < agent.traits.openness < 0.95


class TestDemographicPath:
    def test_skips_astro_and_cultural_modifier(self):
        counting_astro = _CountingAstroEngine()
        counting_culture = _CountingCulturalModifier()
        factory = AgentFactory(
            astro_engine=counting_astro,
            cultural_modifier=counting_culture,
            adapter=DemographicAdapter(),
        )
        agent = factory.build(_profile())
        assert counting_astro.call_count == 0, \
            "Demographic path must NOT call astro engine"
        assert counting_culture.call_count == 0, \
            "Demographic path must NOT apply CulturalModifier (double-count risk)"
        assert agent.natal_chart is None

    def test_traits_are_populated(self):
        factory = AgentFactory(adapter=DemographicAdapter())
        agent = factory.build(_profile())
        # At least some traits should be shifted from 0.5 by Hofstede
        shifts = sum(
            1 for n in agent.traits.to_dict()
            if abs(agent.traits.to_dict()[n] - 0.5) > 1e-4
        )
        assert shifts > 0
