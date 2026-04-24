"""Tests for BlendedAdapter — weighted blend of multiple InputAdapters."""

from __future__ import annotations

import statistics

import pytest

from realm.core.exceptions import PersonalityEmbeddingError
from realm.personality.adapters import (
    BigFiveAdapter,
    BlendedAdapter,
    BlendedComponent,
    BlendedInput,
    get_input_adapter,
)
from realm.personality.adapters.big_five import BIG_FIVE_KEYS
from realm.personality.adapters.blended import _COMPONENT_FIELD
from realm.personality.adapters.interfaces import IInputAdapter
from realm.personality.trait_vector import TraitVector


def _neutral_scores() -> dict[str, float]:
    return dict.fromkeys(BIG_FIVE_KEYS, 0.5)


class _FakeAdapter(IInputAdapter):
    """Returns a preconfigured TraitVector regardless of input.

    Uses adapter_type="big_five" so BlendedAdapter will route
    big_five_scores to it via _COMPONENT_FIELD.
    """

    def __init__(self, vector: TraitVector, adapter_type: str = "big_five") -> None:
        self._v = vector
        self._type = adapter_type

    def build(self, input_data):
        return self._v

    @property
    def adapter_type(self) -> str:
        return self._type


class TestBlendedAdapterInterface:
    def test_adapter_type_is_blended(self):
        a = BlendedAdapter(
            components=[
                BlendedComponent(adapter=BigFiveAdapter(), weight=1.0),
            ],
            noise_sigma=0.0,
        )
        assert a.adapter_type == "blended"

    def test_rejects_non_blended_input(self):
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=BigFiveAdapter(), weight=1.0)],
            noise_sigma=0.0,
        )
        with pytest.raises(PersonalityEmbeddingError, match="BlendedInput"):
            a.build({"not": "blended-input"})

    def test_rejects_empty_components(self):
        with pytest.raises(PersonalityEmbeddingError, match="at least one"):
            BlendedAdapter(components=[], noise_sigma=0.0)

    def test_rejects_non_positive_weight(self):
        with pytest.raises(PersonalityEmbeddingError, match="non-positive weight"):
            BlendedAdapter(
                components=[BlendedComponent(adapter=BigFiveAdapter(), weight=0.0)],
                noise_sigma=0.0,
            )

    def test_rejects_unroutable_component(self):
        class _Other(IInputAdapter):
            def build(self, input_data):  # pragma: no cover
                return TraitVector.neutral()

            @property
            def adapter_type(self) -> str:
                return "other"

        with pytest.raises(PersonalityEmbeddingError, match="route input"):
            BlendedAdapter(
                components=[BlendedComponent(adapter=_Other(), weight=1.0)],
                noise_sigma=0.0,
            )

    def test_rejects_input_with_all_fields_none(self):
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=BigFiveAdapter(), weight=1.0)],
            noise_sigma=0.0,
        )
        with pytest.raises(PersonalityEmbeddingError, match="no populated"):
            a.build(BlendedInput())


class TestBlendedAdapterBehavior:
    def test_weighted_blend_correctness(self):
        """Two-component blend with known child outputs → exact weighted average."""
        tv_a = TraitVector.from_dict({"openness": 1.0, "neuroticism": 0.0})
        tv_b = TraitVector.from_dict({"openness": 0.0, "neuroticism": 1.0})
        a = BlendedAdapter(
            components=[
                BlendedComponent(
                    adapter=_FakeAdapter(tv_a, "big_five"),
                    weight=0.75,
                ),
                BlendedComponent(
                    adapter=_FakeAdapter(tv_b, "astrological"),
                    weight=0.25,
                ),
            ],
            noise_sigma=0.0,
        )
        out = a.build(BlendedInput(
            big_five_scores=_neutral_scores(),
            natal_chart="sentinel",  # _FakeAdapter ignores it
        ))
        # openness = 0.75*1.0 + 0.25*0.0 = 0.75
        # neuroticism = 0.75*0.0 + 0.25*1.0 = 0.25
        assert abs(out.openness - 0.75) < 1e-9
        assert abs(out.neuroticism - 0.25) < 1e-9

    def test_degenerate_single_component(self):
        """One component, weight=1.0, no noise → identical to that adapter."""
        bf = BigFiveAdapter()
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=bf, weight=1.0)],
            noise_sigma=0.0,
        )
        scores = {"openness": 0.7, "conscientiousness": 0.3,
                  "extraversion": 0.8, "agreeableness": 0.4,
                  "neuroticism": 0.2}
        bf_out = bf.build(scores)
        blend_out = a.build(BlendedInput(big_five_scores=scores))
        assert bf_out == blend_out

    def test_missing_component_input_renormalizes(self):
        """If one component's input field is None, remaining components scale to 1.0."""
        tv_bf = TraitVector.from_dict({"openness": 1.0})
        tv_astro = TraitVector.from_dict({"openness": 0.0})
        a = BlendedAdapter(
            components=[
                BlendedComponent(
                    adapter=_FakeAdapter(tv_bf, "big_five"),
                    weight=0.6,
                ),
                BlendedComponent(
                    adapter=_FakeAdapter(tv_astro, "astrological"),
                    weight=0.4,
                ),
            ],
            noise_sigma=0.0,
        )
        # Only big_five present → BF should dominate fully (weight normalizes to 1.0)
        out = a.build(BlendedInput(big_five_scores=_neutral_scores()))
        assert abs(out.openness - 1.0) < 1e-9

    def test_output_values_clamped_to_unit_interval(self):
        """Extreme blend + large noise → all traits still in [0, 1]."""
        tv_hi = TraitVector.from_dict(dict.fromkeys(TraitVector.trait_names(), 1.0))
        a = BlendedAdapter(
            components=[
                BlendedComponent(adapter=_FakeAdapter(tv_hi, "big_five"), weight=1.0),
            ],
            noise_sigma=5.0,  # Absurdly large
        )
        out = a.build(BlendedInput(
            big_five_scores=_neutral_scores(),
            agent_seed=42,
        ))
        for trait in TraitVector.trait_names():
            v = getattr(out, trait)
            assert 0.0 <= v <= 1.0, f"{trait}={v} out of range"


class TestBlendedAdapterDeterminism:
    def test_no_noise_is_deterministic_across_seeds(self):
        """σ=0 → output does not depend on agent_seed."""
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=BigFiveAdapter(), weight=1.0)],
            noise_sigma=0.0,
        )
        out1 = a.build(BlendedInput(big_five_scores=_neutral_scores(), agent_seed=1))
        out2 = a.build(BlendedInput(big_five_scores=_neutral_scores(), agent_seed=999))
        assert out1 == out2

    def test_same_seed_same_output(self):
        """Bit-exact determinism with noise when seed is fixed."""
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=BigFiveAdapter(), weight=1.0)],
            noise_sigma=0.1,
        )
        inp = BlendedInput(big_five_scores=_neutral_scores(), agent_seed=42)
        outs = [a.build(inp) for _ in range(3)]
        assert outs[0] == outs[1] == outs[2]

    def test_different_seeds_different_outputs(self):
        """With noise, different seeds produce different outputs."""
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=BigFiveAdapter(), weight=1.0)],
            noise_sigma=0.1,
        )
        out1 = a.build(BlendedInput(big_five_scores=_neutral_scores(), agent_seed=1))
        out2 = a.build(BlendedInput(big_five_scores=_neutral_scores(), agent_seed=2))
        assert out1 != out2

    def test_noise_magnitude_matches_sigma(self):
        """Across many seeds, empirical std of each trait ~ noise_sigma
        (before [0,1] clamping dominates — centered at 0.5 with small σ it won't)."""
        sigma = 0.05
        a = BlendedAdapter(
            components=[BlendedComponent(adapter=BigFiveAdapter(), weight=1.0)],
            noise_sigma=sigma,
        )
        # BigFive at neutral → all traits 0.5; only noise drives variance.
        outs = [
            a.build(BlendedInput(big_five_scores=_neutral_scores(), agent_seed=i))
            for i in range(500)
        ]
        for trait in ("openness", "conscientiousness", "extraversion"):
            vals = [getattr(o, trait) for o in outs]
            s = statistics.stdev(vals)
            # Allow wide tolerance; sampling variance at N=500, σ=0.05 is large.
            assert 0.03 < s < 0.08, f"{trait} std={s:.3f}"


class TestBlendedAdapterCulturalModifier:
    def test_applies_cultural_modifier_true_when_all_components_apply(self):
        a = BlendedAdapter(
            components=[
                BlendedComponent(adapter=BigFiveAdapter(), weight=1.0),  # True
            ],
            noise_sigma=0.0,
        )
        assert a.applies_cultural_modifier is True

    def test_applies_cultural_modifier_false_if_any_component_opts_out(self):
        from realm.personality.adapters import DemographicAdapter
        a = BlendedAdapter(
            components=[
                BlendedComponent(adapter=BigFiveAdapter(), weight=0.5),
                BlendedComponent(adapter=DemographicAdapter(), weight=0.5),
            ],
            noise_sigma=0.0,
        )
        assert a.applies_cultural_modifier is False


class TestBlendedAdapterConfigFactory:
    def test_factory_builds_blended_from_config(self):
        a = get_input_adapter("blended")
        assert a.adapter_type == "blended"
        # Default config: 2 components (big_five, astrological).
        types = sorted(c.adapter_type for c in a.components)
        assert "big_five" in types
        assert "astrological" in types


def test_component_field_table_matches_adapter_types():
    """_COMPONENT_FIELD must cover every leaf adapter_type."""
    assert set(_COMPONENT_FIELD.keys()) == {"astrological", "big_five", "demographic"}
