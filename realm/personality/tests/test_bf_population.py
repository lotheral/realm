"""Tests for synthetic OCEAN population sampler."""

from __future__ import annotations

import math

import pytest

from realm.personality.bf_population import (
    DEFAULT_CORRELATIONS,
    OCEAN,
    sample_bf_population,
)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


class TestSampleShape:
    def test_returns_n_dicts(self):
        out = sample_bf_population(1000, seed=1)
        assert len(out) == 1000
        assert all(isinstance(d, dict) for d in out)

    def test_each_dict_has_five_ocean_keys(self):
        out = sample_bf_population(50, seed=1)
        for d in out:
            assert set(d.keys()) == set(OCEAN)
            for v in d.values():
                assert isinstance(v, float)


class TestStatisticalRecovery:
    def test_mean_recovery(self):
        out = sample_bf_population(10_000, seed=42)
        for trait in OCEAN:
            mean = sum(d[trait] for d in out) / len(out)
            assert abs(mean - 0.50) < 0.01, f"{trait} mean drift: {mean}"

    def test_std_recovery(self):
        out = sample_bf_population(10_000, seed=42)
        for trait in OCEAN:
            values = [d[trait] for d in out]
            mu = sum(values) / len(values)
            var = sum((v - mu) ** 2 for v in values) / len(values)
            std = math.sqrt(var)
            # Clamp distorts slightly; tolerate ±0.015
            assert abs(std - 0.17) < 0.015, f"{trait} std drift: {std}"

    def test_correlation_matrix_recovery(self):
        out = sample_bf_population(10_000, seed=42)
        per_trait = {t: [d[t] for d in out] for t in OCEAN}
        for (a, b), expected_r in DEFAULT_CORRELATIONS.items():
            observed_r = _pearson(per_trait[a], per_trait[b])
            assert abs(observed_r - expected_r) < 0.03, (
                f"({a},{b}) expected r≈{expected_r:.2f}, got {observed_r:.3f}"
            )
            # Sign must match
            assert (observed_r > 0) == (expected_r > 0), (
                f"({a},{b}) sign flipped: expected {expected_r}, got {observed_r}"
            )


class TestDeterminism:
    def test_same_seed_identical_samples(self):
        a = sample_bf_population(100, seed=7)
        b = sample_bf_population(100, seed=7)
        assert a == b

    def test_different_seeds_differ(self):
        a = sample_bf_population(100, seed=42)
        b = sample_bf_population(100, seed=43)
        # Equality on 100 5-d float vectors with different seeds is essentially
        # impossible; assert they differ on at least one dict.
        assert a != b


class TestClampBounds:
    def test_no_value_outside_unit_interval(self):
        out = sample_bf_population(5000, seed=99)
        for d in out:
            for v in d.values():
                assert 0.0 <= v <= 1.0

    def test_extreme_std_triggers_clipping_but_no_overflow(self):
        out = sample_bf_population(1000, seed=1, target_std=0.45)
        for d in out:
            for v in d.values():
                assert 0.0 <= v <= 1.0


class TestCustomCorrelations:
    def test_custom_correlations_override_defaults(self):
        custom = {("openness", "neuroticism"): -0.50}
        out = sample_bf_population(8000, seed=42, correlations=custom)
        per_trait = {t: [d[t] for d in out] for t in OCEAN}
        # Custom pair should appear strongly
        r = _pearson(per_trait["openness"], per_trait["neuroticism"])
        assert -0.55 < r < -0.45, f"custom O-N r drift: {r}"
        # Default O-E should NOT appear (was 0.15 in defaults; we provided
        # custom dict which omits it, so expect ~0.0)
        r_oe = _pearson(per_trait["openness"], per_trait["extraversion"])
        assert abs(r_oe) < 0.05, f"unexpected O-E correlation: {r_oe}"

    def test_unknown_trait_raises(self):
        with pytest.raises(ValueError, match="Unknown trait"):
            sample_bf_population(10, seed=1, correlations={("openness", "foo"): 0.2})

    def test_non_psd_matrix_raises(self):
        # Forcing simultaneously strong positive correlations between three
        # pairs creates a non-PSD matrix.
        impossible = {
            ("openness", "conscientiousness"): 0.99,
            ("openness", "extraversion"): 0.99,
            ("conscientiousness", "extraversion"): -0.99,
        }
        with pytest.raises(ValueError, match="not positive semi-definite"):
            sample_bf_population(10, seed=1, correlations=impossible)


class TestEdgeCases:
    def test_small_n(self):
        out = sample_bf_population(10, seed=5)
        assert len(out) == 10
        for d in out:
            for v in d.values():
                assert 0.0 <= v <= 1.0

    def test_n_one(self):
        out = sample_bf_population(1, seed=5)
        assert len(out) == 1

    def test_n_zero_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            sample_bf_population(0, seed=1)

    def test_negative_std_raises(self):
        with pytest.raises(ValueError, match="positive"):
            sample_bf_population(10, seed=1, target_std=-0.1)
