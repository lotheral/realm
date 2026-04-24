"""Tests for adapter-aware TraitCalibrator stats path resolution."""

from __future__ import annotations

from pathlib import Path

from realm.personality.calibration import CalibrationStats, TraitCalibrator
from realm.personality.trait_vector import TraitVector


def _write_stats(path: Path, mean: float = 0.5, std: float = 0.05) -> None:
    stats = CalibrationStats(
        per_trait=dict.fromkeys(TraitVector.trait_names(), (mean, std)),
    )
    stats.to_json(path)


class TestAdapterTypeStatsResolution:
    def test_explicit_stats_path_wins(self, tmp_path: Path):
        """If both stats_path and adapter_type provided, explicit path wins."""
        explicit = tmp_path / "explicit.json"
        _write_stats(explicit, mean=0.5, std=0.10)
        cal = TraitCalibrator(
            enabled=True, stats_path=explicit, adapter_type="big_five",
        )
        assert cal.stats_path == explicit.resolve()
        assert cal.enabled is True

    def test_adapter_type_derives_repo_relative_path(self):
        """adapter_type='astrological' resolves to config/trait_calibration_astrological.json."""
        cal = TraitCalibrator(enabled=False, adapter_type="astrological")
        assert cal.stats_path is not None
        assert cal.stats_path.name == "trait_calibration_astrological.json"
        assert cal.adapter_type == "astrological"

    def test_adapter_type_big_five_derives_correct_path(self):
        cal = TraitCalibrator(enabled=False, adapter_type="big_five")
        assert cal.stats_path is not None
        assert cal.stats_path.name == "trait_calibration_big_five.json"

    def test_unknown_adapter_type_with_enabled_falls_back_to_identity(
        self, tmp_path: Path,
    ):
        """Adapter type with no matching stats file -> calibration disabled, no crash."""
        cal = TraitCalibrator(enabled=True, adapter_type="nonexistent_adapter_xyz")
        assert cal.enabled is False
        # apply() returns input unchanged
        v = TraitVector.from_dict({"openness": 0.42})
        assert cal.apply(v).openness == 0.42

    def test_source_synthetic_matches_default_path(self):
        """source='synthetic' (default) resolves to the unsuffixed path."""
        cal = TraitCalibrator(
            enabled=False, adapter_type="big_five", source="synthetic",
        )
        assert cal.stats_path is not None
        assert cal.stats_path.name == "trait_calibration_big_five.json"
        assert cal.source == "synthetic"

    def test_source_real_derives_suffixed_path(self):
        """source='real' appends '_real' suffix to the filename."""
        cal = TraitCalibrator(
            enabled=False, adapter_type="big_five", source="real",
        )
        assert cal.stats_path is not None
        assert cal.stats_path.name == "trait_calibration_big_five_real.json"
        assert cal.source == "real"

    def test_source_real_loads_stats_when_file_present(self):
        """When the real stats file exists, TraitCalibrator(enabled=True, source='real') loads it."""
        cal = TraitCalibrator(
            enabled=True, adapter_type="big_five", source="real",
        )
        # Only assert fully if file exists (real stats are committed at
        # config/trait_calibration_big_five_real.json).
        if cal.stats_path is not None and cal.stats_path.exists():
            assert cal.enabled is True
            assert cal.source == "real"
        else:
            assert cal.enabled is False  # graceful fallback


class TestFactoryWiresAdapterType:
    def test_default_calibrator_inherits_adapter_type_from_adapter(self):
        """AgentFactory default calibrator should be aware of adapter type."""
        from realm.agents.factory import AgentFactory
        from realm.personality.adapters import BigFiveAdapter

        f = AgentFactory(adapter=BigFiveAdapter())
        # Default calibrator was created — its adapter_type matches the adapter
        assert f._calibrator.adapter_type == "big_five"
        # And resolves to the BF-specific stats file path
        assert f._calibrator.stats_path is not None
        assert f._calibrator.stats_path.name == "trait_calibration_big_five.json"

    def test_explicit_calibrator_not_overridden(self):
        """If a calibrator is passed explicitly, factory does not replace it."""
        from realm.agents.factory import AgentFactory
        from realm.personality.adapters import BigFiveAdapter

        explicit = TraitCalibrator(enabled=False)  # no adapter_type
        f = AgentFactory(adapter=BigFiveAdapter(), calibrator=explicit)
        assert f._calibrator is explicit
        assert f._calibrator.adapter_type is None
