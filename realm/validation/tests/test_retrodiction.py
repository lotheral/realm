"""Tests for pure-python retrodiction metrics (Sprint 22)."""

from types import SimpleNamespace

import pytest

from realm.validation.retrodiction import (
    DirectionalResult,
    binomial_p_one_sided,
    breakdown,
    directional_accuracy,
    spearman_rho,
)


class TestDirectionalAccuracy:
    def test_all_correct(self):
        r = directional_accuracy([1.0, -2.0, 3.0, -0.5], [4.0, -1.0, 0.2, -9.0])
        assert isinstance(r, DirectionalResult)
        assert (r.hits, r.misses, r.zero_predictions, r.n) == (4, 0, 0, 4)
        assert r.accuracy == 1.0
        assert r.p_value_one_sided == pytest.approx(0.5 ** 4)

    def test_half_correct(self):
        r = directional_accuracy([1.0, 1.0, -1.0, -1.0], [1.0, -1.0, -1.0, 1.0])
        assert (r.hits, r.misses) == (2, 2)
        assert r.accuracy == 0.5

    def test_zero_prediction_counts_as_miss(self):
        r = directional_accuracy([0.0, 1.0], [3.0, 3.0])
        assert (r.hits, r.misses, r.zero_predictions, r.n) == (1, 1, 1, 2)
        assert r.accuracy == 0.5

    def test_empty_inputs(self):
        r = directional_accuracy([], [])
        assert (r.hits, r.n, r.accuracy) == (0, 0, 0.0)
        assert r.p_value_one_sided == 1.0


class TestBinomial:
    def test_exact_value_8_of_10(self):
        # (C(10,8)+C(10,9)+C(10,10)) / 2^10 = 56/1024
        assert binomial_p_one_sided(8, 10) == pytest.approx(56 / 1024)

    def test_zero_hits_is_certain(self):
        assert binomial_p_one_sided(0, 10) == pytest.approx(1.0)


class TestSpearman:
    def test_perfect_monotone(self):
        assert spearman_rho([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)

    def test_perfect_inverse(self):
        assert spearman_rho([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)

    def test_ties_use_average_ranks(self):
        rho = spearman_rho([1, 2, 2, 3], [1, 2, 3, 4])
        assert rho == pytest.approx(0.9487, abs=1e-3)

    def test_too_few_points_returns_zero(self):
        assert spearman_rho([1, 2], [2, 1]) == 0.0

    def test_zero_variance_returns_zero(self):
        assert spearman_rho([5, 5, 5, 5], [1, 2, 3, 4]) == 0.0


class TestBreakdown:
    def test_groups_by_key(self):
        events = [
            SimpleNamespace(confidence="high"),
            SimpleNamespace(confidence="high"),
            SimpleNamespace(confidence="low"),
        ]
        groups = breakdown(events, [1.0, -1.0, 1.0], [1.0, 1.0, -1.0])
        assert set(groups) == {"high", "low"}
        assert groups["high"].hits == 1 and groups["high"].n == 2
        assert groups["low"].hits == 0 and groups["low"].n == 1
