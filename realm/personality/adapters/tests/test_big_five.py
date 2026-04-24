"""Tests for BigFiveAdapter — OCEAN scores → 24-trait vector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from realm.core.exceptions import PersonalityEmbeddingError
from realm.personality.adapters import BigFiveAdapter
from realm.personality.adapters.big_five import BIG_FIVE_KEYS
from realm.personality.trait_vector import TraitVector


def _neutral_scores() -> dict[str, float]:
    return dict.fromkeys(BIG_FIVE_KEYS, 0.5)


class TestBigFiveAdapterInterface:
    def test_adapter_type(self):
        assert BigFiveAdapter().adapter_type == "big_five"

    def test_applies_cultural_modifier_true(self):
        """Big Five is self-report; cultural context is orthogonal overlay."""
        assert BigFiveAdapter().applies_cultural_modifier is True

    def test_rejects_non_mapping_input(self):
        a = BigFiveAdapter()
        with pytest.raises(PersonalityEmbeddingError, match="Mapping"):
            a.build("not a dict")

    def test_rejects_missing_big_five_key(self):
        a = BigFiveAdapter()
        incomplete = {"openness": 0.6, "extraversion": 0.7}  # missing C, A, N
        with pytest.raises(PersonalityEmbeddingError, match="missing required"):
            a.build(incomplete)


class TestBigFiveAdapterBehavior:
    def test_neutral_input_produces_neutral_output(self):
        """All Big Five at 0.5 → every derived trait at 0.5."""
        a = BigFiveAdapter()
        tv = a.build(_neutral_scores())
        for trait in TraitVector.trait_names():
            assert abs(getattr(tv, trait) - 0.5) < 1e-9

    def test_big_five_values_copied_directly(self):
        a = BigFiveAdapter()
        scores = {
            "openness": 0.82, "conscientiousness": 0.71, "extraversion": 0.63,
            "agreeableness": 0.55, "neuroticism": 0.34,
        }
        tv = a.build(scores)
        assert abs(tv.openness - 0.82) < 1e-9
        assert abs(tv.conscientiousness - 0.71) < 1e-9
        assert abs(tv.extraversion - 0.63) < 1e-9
        assert abs(tv.agreeableness - 0.55) < 1e-9
        assert abs(tv.neuroticism - 0.34) < 1e-9

    def test_output_clamped_to_unit_interval(self):
        """Even with extreme derivation, output stays [0, 1]."""
        a = BigFiveAdapter()
        for k in BIG_FIVE_KEYS:
            scores = _neutral_scores()
            scores[k] = 1.0
            tv = a.build(scores)
            for trait in TraitVector.trait_names():
                assert 0.0 <= getattr(tv, trait) <= 1.0

    def test_deterministic(self):
        a = BigFiveAdapter()
        scores = {"openness": 0.7, "conscientiousness": 0.4,
                  "extraversion": 0.8, "agreeableness": 0.3,
                  "neuroticism": 0.6}
        tv1 = a.build(scores)
        tv2 = a.build(scores)
        assert tv1 == tv2


class TestBigFiveAdapterDerivation:
    def test_custom_derivation_path_loads(self, tmp_path: Path):
        """Adapter should honor an explicit derivation file path."""
        custom = {
            "_comment": "test fixture",
            "traits": {
                "risk_appetite": {
                    "coefficients": {"extraversion": 0.4, "neuroticism": -0.3},
                    "source": "test_source",
                    "confidence": "high",
                },
            },
        }
        p = tmp_path / "bf.json"
        p.write_text(json.dumps(custom))
        a = BigFiveAdapter(derivation_path=p)
        scores = {"openness": 0.5, "conscientiousness": 0.5,
                  "extraversion": 1.0, "agreeableness": 0.5,
                  "neuroticism": 0.0}
        # risk = 0.5 + 0.4*(1.0-0.5) + (-0.3)*(0.0-0.5) = 0.5 + 0.2 + 0.15 = 0.85
        tv = a.build(scores)
        assert abs(tv.risk_appetite - 0.85) < 1e-9

    def test_unsourced_traits_list(self, tmp_path: Path):
        """Traits absent from derivation fall back to 0.5."""
        p = tmp_path / "partial.json"
        p.write_text(json.dumps({
            "_comment": "partial",
            "traits": {
                "risk_appetite": {
                    "coefficients": {"extraversion": 0.3},
                    "source": "x", "confidence": "moderate",
                },
            },
        }))
        a = BigFiveAdapter(derivation_path=p)
        unsourced = a.unsourced_traits
        assert "risk_appetite" not in unsourced
        # Traits NOT in the file should be in unsourced
        assert "patience" in unsourced
        assert a.derived_trait_count == 1

    def test_missing_derivation_file_all_fallback(self, tmp_path: Path):
        """No file → every domain trait falls back to 0.5."""
        missing = tmp_path / "does_not_exist.json"
        a = BigFiveAdapter(derivation_path=missing)
        assert a.derived_trait_count == 0
        scores = {"openness": 0.9, "conscientiousness": 0.1,
                  "extraversion": 0.9, "agreeableness": 0.1,
                  "neuroticism": 0.5}
        tv = a.build(scores)
        # All 19 domain traits should be 0.5 (no derivation applied)
        for trait in TraitVector.trait_names():
            if trait in BIG_FIVE_KEYS:
                continue
            assert abs(getattr(tv, trait) - 0.5) < 1e-9


class TestBigFiveAdapterFacetMode:
    """Facet-level derivation path (use_facets=True)."""

    def test_use_facets_defaults_from_config(self):
        a = BigFiveAdapter()
        # With realm.yaml default (false), facet mode is off
        assert a.use_facets is False

    def test_use_facets_constructor_override(self):
        a = BigFiveAdapter(use_facets=True)
        assert a.use_facets is True

    def test_facet_enabled_trait_count_matches_table(self):
        a = BigFiveAdapter()
        # After Sprint 6 all 13 sourced traits have facet_coefficients
        assert a.facet_enabled_trait_count == 13

    def test_facet_mode_uses_facet_formula_when_all_facets_present(self):
        """With use_facets=True and all required facets provided, facet
        coefficients drive the result instead of the domain formula."""
        a = BigFiveAdapter(use_facets=True)
        # Empathy has facet_coefficients {A3: 0.20, A6: 0.25, N3: 0.10}
        # and domain {agreeableness: 0.45, neuroticism: 0.10}
        neutral_ocean = dict.fromkeys(BIG_FIVE_KEYS, 0.5)
        # Set A3 high, A6 neutral, N3 neutral → empathy should rise via A3 only
        facet_input = {
            **neutral_ocean,
            "A3": 1.0, "A6": 0.5, "N3": 0.5,
        }
        tv = a.build(facet_input)
        # expected = 0.5 + 0.20*(1.0-0.5) + 0.25*(0.5-0.5) + 0.10*(0.5-0.5) = 0.6
        assert abs(tv.empathy - 0.6) < 1e-9

    def test_facet_mode_falls_back_to_domain_when_facets_missing(self):
        """If any facet in the trait's facet_coefficients is absent from
        input, fall back to domain formula for that trait."""
        a = BigFiveAdapter(use_facets=True)
        # empathy needs A3, A6, N3. Provide only A3 and A6; miss N3.
        input_partial = {
            **dict.fromkeys(BIG_FIVE_KEYS, 0.5),
            "A3": 1.0, "A6": 1.0,  # no N3
            "agreeableness": 1.0,  # override domain for fallback check
        }
        tv = a.build(input_partial)
        # Domain formula: 0.5 + 0.45 * (1.0 - 0.5) + 0.10 * (0.5 - 0.5) = 0.725
        assert abs(tv.empathy - 0.725) < 1e-9

    def test_facet_mode_disabled_ignores_facet_keys(self):
        """With use_facets=False, extra facet keys are silently ignored."""
        a = BigFiveAdapter(use_facets=False)
        neutral_ocean = dict.fromkeys(BIG_FIVE_KEYS, 0.5)
        with_extreme_facets = {**neutral_ocean, "A3": 1.0, "A6": 1.0, "N3": 1.0}
        tv = a.build(with_extreme_facets)
        # Domain formula on neutral OCEAN → empathy should be 0.5
        assert abs(tv.empathy - 0.5) < 1e-9

    def test_facet_mode_correct_direction_impulsivity(self):
        """impulsivity should rise with high N5 (Impulsiveness facet)."""
        a = BigFiveAdapter(use_facets=True)
        neutral_ocean = dict.fromkeys(BIG_FIVE_KEYS, 0.5)
        # N5 high, E5 neutral, C6 neutral → only N5 raises impulsivity
        input_hi_n5 = {**neutral_ocean, "N5": 1.0, "E5": 0.5, "C6": 0.5}
        tv = a.build(input_hi_n5)
        assert tv.impulsivity > 0.5  # N5=+0.35 coefficient → 0.675

    def test_facet_mode_risk_appetite_e5_drives(self):
        """High E5 (Excitement-Seeking) should raise risk_appetite even with
        neutral OCEAN domains."""
        a = BigFiveAdapter(use_facets=True)
        neutral_ocean = dict.fromkeys(BIG_FIVE_KEYS, 0.5)
        # Need all 6 facets cited: O5, E5, N1, N5, C6, A2
        input_hi_e5 = {
            **neutral_ocean,
            "O5": 0.5, "E5": 1.0, "N1": 0.5, "N5": 0.5, "C6": 0.5, "A2": 0.5,
        }
        tv = a.build(input_hi_e5)
        # expected = 0.5 + 0.20*(1.0-0.5) = 0.6
        assert abs(tv.risk_appetite - 0.6) < 1e-9

    def test_facet_and_domain_agree_on_neutral_input(self):
        """Both modes produce 0.5 for every trait when all inputs are neutral."""
        domain_only = BigFiveAdapter(use_facets=False)
        facet_mode = BigFiveAdapter(use_facets=True)
        neutral_ocean = dict.fromkeys(BIG_FIVE_KEYS, 0.5)
        neutral_facets = {f"{d}{i}": 0.5 for d in "OCEAN" for i in range(1, 7)}
        combined = {**neutral_ocean, **neutral_facets}
        tv_d = domain_only.build(neutral_ocean)
        tv_f = facet_mode.build(combined)
        for trait in TraitVector.trait_names():
            assert abs(getattr(tv_d, trait) - 0.5) < 1e-9
            assert abs(getattr(tv_f, trait) - 0.5) < 1e-9
