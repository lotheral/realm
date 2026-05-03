"""Tests for Sprint 7 astrological validity study.

Covers:
- celebrity_profiles.json schema integrity
- validate_astro_study math (directional accuracy, extreme filter)
- generate_celebrity_astro_profiles script module-level import smoke
- outputs/astro_validity_metrics.json structure (if the study has been run)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from realm.personality.trait_vector import TraitVector  # noqa: E402  # isort: skip


CELEBRITY_PROFILES_PATH = ROOT / "data" / "validation" / "celebrity_profiles.json"
METRICS_PATH = ROOT / "outputs" / "astro_validity_metrics.json"

EXPECTED_FIGURE_COUNT = 22
VALIDATED_TRAIT_COUNT = 23  # 24 - political_spectrum


def _load_profiles() -> dict:
    with CELEBRITY_PROFILES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class TestCelebrityProfilesSchema:
    """Structure and content integrity of celebrity_profiles.json."""

    def test_file_exists_and_loads(self) -> None:
        assert CELEBRITY_PROFILES_PATH.exists()
        _load_profiles()  # JSON validity

    def test_figure_count(self) -> None:
        d = _load_profiles()
        assert len(d["figures"]) == EXPECTED_FIGURE_COUNT, \
            f"Expected {EXPECTED_FIGURE_COUNT} figures, got {len(d['figures'])}"

    def test_every_figure_has_23_traits(self) -> None:
        d = _load_profiles()
        for fid, fig in d["figures"].items():
            assert len(fig["expected_traits"]) == VALIDATED_TRAIT_COUNT, \
                f"{fid}: expected {VALIDATED_TRAIT_COUNT} traits, got {len(fig['expected_traits'])}"

    def test_political_spectrum_never_present(self) -> None:
        d = _load_profiles()
        for fid, fig in d["figures"].items():
            assert "political_spectrum" not in fig["expected_traits"], \
                f"{fid} should not include political_spectrum (astro-excluded trait)"

    def test_trait_values_in_unit_interval(self) -> None:
        d = _load_profiles()
        for fid, fig in d["figures"].items():
            for trait, entry in fig["expected_traits"].items():
                val = entry["value"]
                assert 0.0 <= val <= 1.0, f"{fid}.{trait}: {val} outside [0,1]"

    def test_confidence_is_valid_tier(self) -> None:
        d = _load_profiles()
        valid_tiers = {"high", "medium", "low"}
        for fid, fig in d["figures"].items():
            for trait, entry in fig["expected_traits"].items():
                assert entry["confidence"] in valid_tiers, \
                    f"{fid}.{trait}: confidence {entry['confidence']!r} not in {valid_tiers}"

    def test_every_trait_has_rationale(self) -> None:
        d = _load_profiles()
        for fid, fig in d["figures"].items():
            for trait, entry in fig["expected_traits"].items():
                assert entry.get("rationale"), \
                    f"{fid}.{trait}: missing or empty rationale"

    def test_all_validated_traits_are_known(self) -> None:
        d = _load_profiles()
        known = set(TraitVector.trait_names()) - {"political_spectrum"}
        for fid, fig in d["figures"].items():
            for trait in fig["expected_traits"]:
                assert trait in known, f"{fid}: unknown trait {trait!r}"

    def test_birth_data_fields(self) -> None:
        d = _load_profiles()
        required = {"local_iso", "timezone", "latitude", "longitude"}
        for fid, fig in d["figures"].items():
            b = fig["birth"]
            missing = required - b.keys()
            assert not missing, f"{fid}: birth missing {missing}"
            assert -90.0 <= b["latitude"] <= 90.0, f"{fid}: lat {b['latitude']} out of range"
            assert -180.0 <= b["longitude"] <= 180.0, f"{fid}: lon {b['longitude']} out of range"


class TestValidateAstroStudyMath:
    """Direct unit tests on the validate_astro_study computations."""

    @pytest.fixture
    def module(self):
        spec = importlib.util.spec_from_file_location(
            "validate_astro_study",
            ROOT / "scripts" / "validate_astro_study.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_directional_hit_same_high(self, module) -> None:
        assert module._directional_hit(0.8, 0.7) is True

    def test_directional_hit_same_low(self, module) -> None:
        assert module._directional_hit(0.2, 0.3) is True

    def test_directional_hit_opposite(self, module) -> None:
        assert module._directional_hit(0.8, 0.3) is False
        assert module._directional_hit(0.2, 0.7) is False

    def test_directional_hit_neutral_expected_skips(self, module) -> None:
        assert module._directional_hit(0.5, 0.8) is None

    def test_pearson_identical(self, module) -> None:
        xs = [0.1, 0.3, 0.5, 0.7, 0.9]
        r = module._pearson(xs, xs)
        assert abs(r - 1.0) < 1e-9

    def test_pearson_anti(self, module) -> None:
        xs = [0.1, 0.3, 0.5, 0.7, 0.9]
        ys = [0.9, 0.7, 0.5, 0.3, 0.1]
        r = module._pearson(xs, ys)
        assert abs(r + 1.0) < 1e-9

    def test_pearson_zero_variance(self, module) -> None:
        xs = [0.5, 0.5, 0.5, 0.5]
        ys = [0.1, 0.3, 0.5, 0.9]
        assert module._pearson(xs, ys) == 0.0

    def test_da_from_triples_skips_neutral(self, module) -> None:
        triples = [
            ("a", "x", True),
            ("a", "y", False),
            ("b", "z", None),  # neutral expected — skipped
            ("c", "w", True),
        ]
        da, hits, n = module._da_from_triples(triples)
        assert n == 3
        assert hits == 2
        assert abs(da - 2 / 3) < 1e-9

    def test_extreme_filter(self, module) -> None:
        fig = {
            "status": "ok",
            "astro_only": {"a": 0.9, "b": 0.5, "c": 0.1},
            "expected": {
                "a": {"value": 0.85, "confidence": "high"},
                "b": {"value": 0.55, "confidence": "high"},
                "c": {"value": 0.15, "confidence": "high"},
            },
        }
        _, _, triples = module._extract_pairs(
            {"f1": fig}, ["a", "b", "c"], extreme_only=True,
        )
        traits_in = {t[1] for t in triples}
        assert traits_in == {"a", "c"}, "extreme filter should keep only 0.85 and 0.15"

    def test_confidence_filter_high_only(self, module) -> None:
        fig = {
            "status": "ok",
            "astro_only": {"a": 0.9, "b": 0.4},
            "expected": {
                "a": {"value": 0.8, "confidence": "high"},
                "b": {"value": 0.3, "confidence": "low"},
            },
        }
        _, _, triples = module._extract_pairs(
            {"f1": fig}, ["a", "b"], confidence_filter={"high"},
        )
        assert {t[1] for t in triples} == {"a"}


class TestMetricsOutput:
    """Sanity checks on the emitted metrics JSON — only runs if the study was executed."""

    def test_metrics_file_exists(self) -> None:
        if not METRICS_PATH.exists():
            pytest.skip("metrics file not generated yet (run validate_astro_study.py)")

    def test_metrics_schema(self) -> None:
        if not METRICS_PATH.exists():
            pytest.skip("metrics file not generated yet")
        with METRICS_PATH.open(encoding="utf-8") as f:
            m = json.load(f)
        for key in ("da", "cw_da", "extreme", "correlation",
                    "per_trait", "per_person", "confidence_coverage",
                    "thresholds", "validated_traits"):
            assert key in m, f"metrics missing key: {key}"
        assert len(m["validated_traits"]) == VALIDATED_TRAIT_COUNT
        assert "political_spectrum" not in m["validated_traits"]

    def test_per_trait_covers_all_validated(self) -> None:
        if not METRICS_PATH.exists():
            pytest.skip("metrics file not generated yet")
        with METRICS_PATH.open(encoding="utf-8") as f:
            m = json.load(f)
        traits_in_per = {t["trait"] for t in m["per_trait"]}
        assert traits_in_per == set(m["validated_traits"])


class TestGeneratorScript:
    """Module-level import smoke — catches syntax and import errors early."""

    def test_generator_script_imports(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "generate_celebrity_astro_profiles",
            ROOT / "scripts" / "generate_celebrity_astro_profiles.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # Just load; don't execute main()
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main")
        assert hasattr(mod, "_local_to_utc")
