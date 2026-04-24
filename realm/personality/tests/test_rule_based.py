"""Tests for RuleBasedEmbedder.

Uses the synthetic fixture chart (Aries-heavy, Mars-exalted placement) and an
approximate Steve Jobs chart (via SkyfieldEngine) to verify that the embedder
produces plausible trait profiles.
"""

from __future__ import annotations

import pytest

from realm.astro.fixtures import STEVE_JOBS, synthetic_chart
from realm.personality.embedder import get_personality_embedder
from realm.personality.rule_based import RuleBasedEmbedder
from realm.personality.trait_vector import TraitVector


@pytest.fixture(scope="module")
def embedder() -> RuleBasedEmbedder:
    return RuleBasedEmbedder()


class TestBasicEmbedder:
    def test_embed_returns_trait_vector(self, embedder):
        chart = synthetic_chart()
        tv = embedder.embed(chart)
        assert isinstance(tv, TraitVector)

    def test_all_traits_in_unit_interval(self, embedder):
        tv = embedder.embed(synthetic_chart())
        for name, val in tv.to_dict().items():
            assert 0.0 <= val <= 1.0, f"{name}={val}"

    def test_deterministic(self, embedder):
        chart = synthetic_chart()
        tv1 = embedder.embed(chart)
        tv2 = embedder.embed(chart)
        assert tv1 == tv2

    def test_mode_is_rule_based(self, embedder):
        assert embedder.mode == "rule_based"


class TestSyntheticChartExpectations:
    """Synthetic chart: Sun/Mars conjunct in Aries → elevated risk & impulsivity.

    Fire-heavy element balance (40%) reinforces extraversion/risk. Air/earth are
    only 15% each so conscientiousness and analytical_depth should remain near
    neutral or slightly below. Saturn in Capricorn (rulership) should still
    push conscientiousness up.
    """

    def test_risk_appetite_elevated(self, embedder):
        tv = embedder.embed(synthetic_chart())
        assert tv.risk_appetite > 0.50, f"expected > 0.50, got {tv.risk_appetite:.3f}"

    def test_impulsivity_elevated(self, embedder):
        tv = embedder.embed(synthetic_chart())
        assert tv.impulsivity > 0.50

    def test_conscientiousness_moved_from_neutral(self, embedder):
        # Saturn in Capricorn (rulership) should shift conscientiousness up.
        tv = embedder.embed(synthetic_chart())
        assert tv.conscientiousness > 0.52


@pytest.mark.usefixtures("embedder")
class TestSteveJobsChart:
    """Use real ephemeris for Jobs. Verify plausible personality directions.

    Known Jobs traits (biographical consensus):
      - High risk appetite (Mars in Aries — rulership)
      - Strong financial optimism and expansiveness (Jupiter in Cancer — exaltation)
      - Charismatic/persuasive (Pluto in Leo generation)
      - Driven, intense, often abrasive (Sun Pisces but Moon Aries)
    """

    @pytest.fixture(scope="class")
    def jobs_traits(self, embedder):
        pytest.importorskip("skyfield")
        from realm.astro.skyfield_engine import SkyfieldEngine

        engine = SkyfieldEngine()
        chart = engine.calculate_natal_chart(
            STEVE_JOBS.birth_dt,
            STEVE_JOBS.latitude,
            STEVE_JOBS.longitude,
            STEVE_JOBS.timezone,
        )
        return embedder.embed(chart)

    def test_risk_appetite_above_neutral(self, jobs_traits):
        # Mars rules Aries — Jobs had Mars in Aries (strong, +0.15 sign shift)
        assert jobs_traits.risk_appetite > 0.50

    def test_financial_optimism_above_neutral(self, jobs_traits):
        # Jupiter exalted in Cancer
        assert jobs_traits.financial_optimism > 0.50

    def test_traits_in_unit_interval(self, jobs_traits):
        for name, val in jobs_traits.to_dict().items():
            assert 0.0 <= val <= 1.0, f"{name}={val}"

    def test_vector_is_dispersed_not_all_neutral(self, jobs_traits):
        # At least some traits should deviate from 0.5 by > 0.03.
        deviations = [abs(v - 0.5) for v in jobs_traits.to_dict().values()]
        assert max(deviations) > 0.03, "all traits stuck at neutral"


class TestEmbedderFactory:
    def test_get_rule_based(self):
        e = get_personality_embedder("rule_based")
        assert e.mode == "rule_based"

    def test_llm_mode_falls_back_without_key(self, monkeypatch):
        """LLM mode should produce a usable embedder even without API keys —
        it gracefully falls back to rule-based."""
        # Clear LLM credentials so no backend can initialize
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        e = get_personality_embedder("llm")
        assert e.mode == "llm"

    def test_hybrid_mode_available(self, monkeypatch):
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        e = get_personality_embedder("hybrid")
        assert e.mode == "hybrid"

    def test_unknown_mode(self):
        from realm.core.exceptions import PersonalityEmbeddingError
        with pytest.raises(PersonalityEmbeddingError):
            get_personality_embedder("quantum_telepathy")


class TestCustomTables:
    def test_empty_tables_produce_neutral(self):
        """With no trait mappings, every trait stays at 0.5."""
        embedder = RuleBasedEmbedder(
            planet_trait_map={},
            sign_modifiers={},
            aspect_weights={},
            planet_weights={},
        )
        tv = embedder.embed(synthetic_chart())
        for val in tv.to_dict().values():
            assert val == pytest.approx(0.5)

    def test_custom_planet_mapping(self):
        """A strong custom Sun→openness mapping should move openness up."""
        embedder = RuleBasedEmbedder(
            planet_trait_map={"Sun": {"openness": 1.0}},
            sign_modifiers={},
            aspect_weights={"conjunction": 0.0, "trine": 0.0, "square": 0.0,
                            "opposition": 0.0, "sextile": 0.0, "quincunx": 0.0},
            planet_weights={"Sun": 1.0},
        )
        tv = embedder.embed(synthetic_chart())
        assert tv.openness > 0.55
