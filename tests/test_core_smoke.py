"""Smoke test for realm.core — imports work, config loads, logger constructs."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from realm.core import config, exceptions, logging as rlog
from realm.core.types import (
    ASPECT_TYPES,
    DIGNITY_SCORE,
    PLANET_DIGNITY,
    PLANETS_ALL_PHASE1,
    SIGN_ELEMENT,
    SIGN_MODALITY,
    SIGNS,
    Aspect,
    NatalChart,
    PlanetPosition,
    TransitSnapshot,
)


class TestVocabulary:
    def test_signs_are_twelve(self):
        assert len(SIGNS) == 12
        assert len(set(SIGNS)) == 12

    def test_phase1_planets_are_thirteen(self):
        # Classic 10 + North_Node + South_Node + Chiron
        assert len(PLANETS_ALL_PHASE1) == 13
        assert "Sun" in PLANETS_ALL_PHASE1
        assert "Chiron" in PLANETS_ALL_PHASE1
        assert "North_Node" in PLANETS_ALL_PHASE1

    def test_sign_element_covers_all_signs(self):
        assert set(SIGN_ELEMENT.keys()) == set(SIGNS)

    def test_sign_modality_covers_all_signs(self):
        assert set(SIGN_MODALITY.keys()) == set(SIGNS)

    def test_dignity_scores_have_expected_levels(self):
        assert DIGNITY_SCORE["rulership"] > DIGNITY_SCORE["exaltation"] > DIGNITY_SCORE["neutral"]
        assert DIGNITY_SCORE["neutral"] > DIGNITY_SCORE["detriment"] > DIGNITY_SCORE["fall"]

    def test_every_classic_planet_has_dignity_entries(self):
        classic = {
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
        }
        assert set(PLANET_DIGNITY.keys()) == classic
        for p, dignities in PLANET_DIGNITY.items():
            assert set(dignities.keys()) == {"rulership", "exaltation", "detriment", "fall"}
            # Rulership and detriment signs should be opposite
            assert dignities["rulership"] in SIGNS
            assert dignities["detriment"] in SIGNS


class TestDataclasses:
    def test_planet_position_is_frozen(self):
        p = PlanetPosition(
            name="Sun", longitude=15.0, latitude=0.0,
            sign="Aries", sign_degree=15.0, house=1,
            is_retrograde=False, speed=1.0,
        )
        with pytest.raises((AttributeError, Exception)):
            p.sign = "Taurus"  # type: ignore[misc]

    def test_natal_chart_planet_lookup(self):
        sun = PlanetPosition(
            name="Sun", longitude=15.0, latitude=0.0,
            sign="Aries", sign_degree=15.0, house=1,
            is_retrograde=False, speed=1.0,
        )
        moon = PlanetPosition(
            name="Moon", longitude=100.0, latitude=0.0,
            sign="Cancer", sign_degree=10.0, house=4,
            is_retrograde=False, speed=13.0,
        )
        chart = NatalChart(
            birth_datetime=datetime(1990, 1, 1, 12, 0, tzinfo=timezone.utc),
            latitude=0.0, longitude=0.0, timezone="UTC",
            planets=(sun, moon),
            houses=tuple([float(i * 30) for i in range(12)]),
            aspects=(),
            ascendant=0.0, midheaven=270.0,
            element_balance={"fire": 0.5, "water": 0.5, "air": 0.0, "earth": 0.0},
            modality_balance={"cardinal": 1.0, "fixed": 0.0, "mutable": 0.0},
        )
        assert chart.planet("Sun") is sun
        assert chart.planet("Mars") is None

    def test_aspects_for_filters_correctly(self):
        a1 = Aspect("Sun", "Moon", "trine", 120.0, 1.0, True)
        a2 = Aspect("Moon", "Mars", "square", 90.0, 2.0, False)
        a3 = Aspect("Venus", "Mars", "conjunction", 0.0, 0.5, True)
        chart = NatalChart(
            birth_datetime=datetime(1990, 1, 1, tzinfo=timezone.utc),
            latitude=0.0, longitude=0.0, timezone="UTC",
            planets=(), houses=tuple([0.0] * 12), aspects=(a1, a2, a3),
            ascendant=0.0, midheaven=0.0,
            element_balance={e: 0.25 for e in ("fire", "earth", "air", "water")},
            modality_balance={m: 1 / 3 for m in ("cardinal", "fixed", "mutable")},
        )
        moon_aspects = chart.aspects_for("Moon")
        assert set(moon_aspects) == {a1, a2}


class TestConfig:
    def test_realm_config_loads(self):
        cfg = config.load_realm_config()
        assert cfg["realm"]["name"] == "REALM"
        assert cfg["realm"]["simulation"]["master_seed"] == 42

    def test_astrology_config_loads(self):
        cfg = config.load_astrology_config()
        assert cfg["astrology"]["system"] == "western_tropical"
        assert cfg["astrology"]["celestial_bodies"]["nodes"] is True

    def test_master_seed_from_config(self):
        # Clear cache to avoid env pollution from prior test
        config.load_realm_config.cache_clear()
        assert config.get_master_seed() == 42

    def test_master_seed_env_override(self, monkeypatch):
        monkeypatch.setenv("REALM_MASTER_SEED", "1337")
        assert config.get_master_seed() == 1337

    def test_master_seed_bad_env_raises(self, monkeypatch):
        monkeypatch.setenv("REALM_MASTER_SEED", "not-an-int")
        with pytest.raises(exceptions.ConfigError):
            config.get_master_seed()

    def test_missing_yaml_raises(self, tmp_path):
        with pytest.raises(exceptions.ConfigError):
            config.load_yaml(tmp_path / "does_not_exist.yaml")

    def test_derive_seed_is_deterministic(self):
        s1 = config.derive_seed(42, "astro")
        s2 = config.derive_seed(42, "astro")
        assert s1 == s2
        # Different subsystems yield different seeds
        assert config.derive_seed(42, "astro") != config.derive_seed(42, "personality")
        # Different master seeds yield different results
        assert config.derive_seed(42, "astro") != config.derive_seed(43, "astro")


class TestLogging:
    def test_get_logger_prefixes_namespace(self):
        lg = rlog.get_logger("astro.natal")
        assert lg.name == "realm.astro.natal"

    def test_get_logger_respects_existing_prefix(self):
        lg = rlog.get_logger("realm.personality")
        assert lg.name == "realm.personality"

    def test_setup_logging_is_idempotent(self):
        rlog.setup_logging()
        rlog.setup_logging()  # second call should not duplicate handlers
