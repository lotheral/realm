"""Tests for soft-rescale trait calibration."""

from __future__ import annotations

import json
from pathlib import Path

from realm.personality.calibration import CalibrationStats, calibrate
from realm.personality.trait_vector import TraitVector


def _uniform_stats(
    mean: float = 0.5, std: float = 0.05
) -> CalibrationStats:
    return CalibrationStats(
        per_trait=dict.fromkeys(TraitVector.trait_names(), (mean, std)),
    )


class TestCalibrate:
    def test_identity_when_obs_matches_target(self):
        """Stretching by 1.0x leaves values unchanged."""
        stats = _uniform_stats(mean=0.5, std=0.17)
        v = TraitVector.from_dict(dict.fromkeys(TraitVector.trait_names(), 0.6))
        out = calibrate(v, stats, target_mean=0.5, target_std=0.17)
        for n in TraitVector.trait_names():
            assert abs(getattr(out, n) - 0.6) < 1e-9

    def test_stretches_variance_toward_target(self):
        """Observed std=0.05, target 0.17 → 3.4x stretch."""
        stats = _uniform_stats(mean=0.5, std=0.05)
        v = TraitVector.from_dict(dict.fromkeys(TraitVector.trait_names(), 0.55))
        out = calibrate(v, stats, target_mean=0.5, target_std=0.17)
        # (0.55 - 0.5) * (0.17 / 0.05) = 0.17 → 0.5 + 0.17 = 0.67
        for n in TraitVector.trait_names():
            assert abs(getattr(out, n) - 0.67) < 1e-6

    def test_preserves_ordering(self):
        """Two traits in the same distribution keep their rank after calibration."""
        stats = _uniform_stats(mean=0.5, std=0.05)
        v = TraitVector.from_dict({"openness": 0.55, "neuroticism": 0.45,
                                   "extraversion": 0.50})
        out = calibrate(v, stats, target_mean=0.5, target_std=0.17)
        assert out.openness > out.extraversion > out.neuroticism

    def test_clamps_when_stretch_overshoots(self):
        """Outlier value + large stretch should clip at [0, 1]."""
        stats = _uniform_stats(mean=0.5, std=0.05)
        v = TraitVector.from_dict({"openness": 0.80})
        out = calibrate(v, stats, target_mean=0.5, target_std=0.17)
        # (0.80 - 0.5) * 3.4 = 1.02 + 0.5 = 1.52 → clamped to 1.0
        assert out.openness == 1.0

    def test_degenerate_std_leaves_value_unchanged(self):
        stats = CalibrationStats(
            per_trait={"openness": (0.5, 0.0), "neuroticism": (0.5, 0.17)},
        )
        v = TraitVector.from_dict({"openness": 0.77, "neuroticism": 0.6})
        out = calibrate(v, stats, target_mean=0.5, target_std=0.17)
        assert out.openness == 0.77  # unchanged (std < min_obs_std)
        # neuroticism: (0.6-0.5) * 1.0 + 0.5 = 0.6
        assert abs(out.neuroticism - 0.6) < 1e-9

    def test_missing_trait_in_stats_leaves_value_unchanged(self):
        stats = CalibrationStats(per_trait={"openness": (0.5, 0.05)})
        v = TraitVector.from_dict({"openness": 0.55, "neuroticism": 0.42})
        out = calibrate(v, stats, target_mean=0.5, target_std=0.17)
        assert out.neuroticism == 0.42

    def test_roundtrip_json(self, tmp_path: Path):
        src = CalibrationStats(
            per_trait={"openness": (0.51, 0.066), "neuroticism": (0.49, 0.072)},
        )
        f = tmp_path / "stats.json"
        src.to_json(f)
        round = CalibrationStats.from_json(f)
        assert round.per_trait["openness"] == (0.51, 0.066)
        assert round.per_trait["neuroticism"] == (0.49, 0.072)
        # schema sanity
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "per_trait" in data
        assert "_note" in data
