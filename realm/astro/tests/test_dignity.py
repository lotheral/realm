"""Tests for dignity_analyzer."""

from __future__ import annotations

from realm.astro.dignity_analyzer import (
    get_dignity_score,
    get_dignity_state,
    planet_strength,
)
from realm.core.types import PlanetPosition


def _p(name: str, sign: str, retrograde: bool = False) -> PlanetPosition:
    return PlanetPosition(
        name=name, longitude=0.0, latitude=0.0,
        sign=sign, sign_degree=0.0, house=1,
        is_retrograde=retrograde, speed=1.0,
    )


class TestDignityState:
    def test_rulership(self):
        assert get_dignity_state("Sun", "Leo") == "rulership"
        assert get_dignity_state("Moon", "Cancer") == "rulership"
        assert get_dignity_state("Mars", "Aries") == "rulership"

    def test_exaltation(self):
        assert get_dignity_state("Sun", "Aries") == "exaltation"
        assert get_dignity_state("Moon", "Taurus") == "exaltation"
        assert get_dignity_state("Saturn", "Libra") == "exaltation"

    def test_detriment(self):
        assert get_dignity_state("Sun", "Aquarius") == "detriment"
        assert get_dignity_state("Mars", "Libra") == "detriment"

    def test_fall(self):
        assert get_dignity_state("Sun", "Libra") == "fall"
        assert get_dignity_state("Moon", "Scorpio") == "fall"

    def test_neutral_for_unrelated_sign(self):
        assert get_dignity_state("Sun", "Gemini") == "neutral"

    def test_non_classical_planet_always_neutral(self):
        assert get_dignity_state("North_Node", "Leo") == "neutral"
        assert get_dignity_state("Chiron", "Pisces") == "neutral"


class TestDignityScore:
    def test_rulership_highest(self):
        assert get_dignity_score("Sun", "Leo") > get_dignity_score("Sun", "Aries")
        assert get_dignity_score("Sun", "Leo") > get_dignity_score("Sun", "Gemini")

    def test_fall_lowest(self):
        assert get_dignity_score("Sun", "Libra") < get_dignity_score("Sun", "Aquarius")
        assert get_dignity_score("Sun", "Libra") < get_dignity_score("Sun", "Gemini")

    def test_neutral_is_one(self):
        assert get_dignity_score("Sun", "Gemini") == 1.0


class TestPlanetStrength:
    def test_rulership_retrograde_reduces(self):
        direct = planet_strength(_p("Sun", "Leo", retrograde=False))
        retro = planet_strength(_p("Sun", "Leo", retrograde=True))
        assert retro < direct
        assert abs(retro - direct * 0.9) < 1e-9

    def test_neutral_non_classical_returns_one(self):
        assert planet_strength(_p("Chiron", "Libra", retrograde=False)) == 1.0
