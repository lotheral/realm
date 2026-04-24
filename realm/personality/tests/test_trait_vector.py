"""Tests for TraitVector."""

from __future__ import annotations

import math

import pytest

from realm.personality.trait_vector import TraitVector, mean_trait_vector


class TestConstruction:
    def test_default_is_neutral(self):
        tv = TraitVector()
        for val in tv.to_dict().values():
            assert val == 0.5

    def test_neutral_classmethod(self):
        assert TraitVector.neutral() == TraitVector()

    def test_from_dict_clamps_above_one(self):
        tv = TraitVector.from_dict({"openness": 2.0})
        assert tv.openness == 1.0

    def test_from_dict_clamps_below_zero(self):
        tv = TraitVector.from_dict({"openness": -0.5})
        assert tv.openness == 0.0

    def test_from_dict_ignores_unknown_keys(self):
        tv = TraitVector.from_dict({"bogus_key": 0.9, "openness": 0.8})
        assert tv.openness == 0.8
        assert not hasattr(tv, "bogus_key")

    def test_has_twentyfour_dimensions(self):
        assert len(TraitVector.trait_names()) == 24


class TestApplyModifier:
    def test_positive_modifier_raises_value(self):
        tv = TraitVector(openness=0.3)
        tv2 = tv.apply_modifier({"openness": 0.2})
        assert tv2.openness == pytest.approx(0.5)

    def test_clamps_on_upper_bound(self):
        tv = TraitVector(openness=0.9)
        tv2 = tv.apply_modifier({"openness": 0.5})
        assert tv2.openness == 1.0

    def test_ignores_unknown_modifier(self):
        tv = TraitVector()
        tv2 = tv.apply_modifier({"bogus": 0.5})
        assert tv == tv2

    def test_returns_new_instance(self):
        tv = TraitVector()
        tv2 = tv.apply_modifier({"openness": 0.1})
        assert tv is not tv2


class TestBlend:
    def test_alpha_zero_returns_self(self):
        a = TraitVector(openness=0.8)
        b = TraitVector(openness=0.2)
        assert a.blend(b, 0.0).openness == pytest.approx(0.8)

    def test_alpha_one_returns_other(self):
        a = TraitVector(openness=0.8)
        b = TraitVector(openness=0.2)
        assert a.blend(b, 1.0).openness == pytest.approx(0.2)

    def test_alpha_half_averages(self):
        a = TraitVector(openness=0.8)
        b = TraitVector(openness=0.2)
        assert a.blend(b, 0.5).openness == pytest.approx(0.5)

    def test_alpha_out_of_range_is_clamped(self):
        a = TraitVector(openness=0.8)
        b = TraitVector(openness=0.2)
        assert a.blend(b, 2.0).openness == pytest.approx(0.2)
        assert a.blend(b, -1.0).openness == pytest.approx(0.8)


class TestDistance:
    def test_self_distance_is_zero(self):
        tv = TraitVector(openness=0.7, neuroticism=0.3)
        assert tv.distance(tv) == 0.0

    def test_symmetric(self):
        a = TraitVector(openness=0.8)
        b = TraitVector(openness=0.2)
        assert a.distance(b) == b.distance(a)

    def test_known_distance(self):
        a = TraitVector(openness=1.0)
        b = TraitVector(openness=0.0)
        # Only one trait differs, by 1.0. All others are 0.5 vs 0.5 → 0.
        assert a.distance(b) == pytest.approx(1.0)

    def test_max_distance_bounded(self):
        a = TraitVector.from_dict(dict.fromkeys(TraitVector.trait_names(), 1.0))
        b = TraitVector.from_dict(dict.fromkeys(TraitVector.trait_names(), 0.0))
        # 24 dimensions of magnitude 1 → sqrt(24)
        assert a.distance(b) == pytest.approx(math.sqrt(24))


class TestMeanVector:
    def test_empty_returns_neutral(self):
        assert mean_trait_vector([]) == TraitVector.neutral()

    def test_mean_of_two(self):
        a = TraitVector(openness=0.8)
        b = TraitVector(openness=0.2)
        m = mean_trait_vector([a, b])
        assert m.openness == pytest.approx(0.5)

    def test_single_vector_returns_same(self):
        a = TraitVector(openness=0.7, extraversion=0.3)
        assert mean_trait_vector([a]) == a


class TestImmutability:
    def test_frozen(self):
        tv = TraitVector()
        with pytest.raises((AttributeError, Exception)):
            tv.openness = 0.9  # type: ignore[misc]
