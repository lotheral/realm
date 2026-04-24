"""Tests for Hofstede → trait modifier mapping."""

from __future__ import annotations

from realm.culture.hofstede import hofstede_to_modifiers
from realm.culture.religion_worldview import religion_to_modifiers


class TestHofstedeMapping:
    def test_neutral_scores_produce_zero_modifiers(self):
        # Every dimension = 50 → centered = 0 → all modifiers zero
        neutral = {"pdi": 50, "idv": 50, "mas": 50, "uai": 50, "lto": 50, "ivr": 50}
        m = hofstede_to_modifiers(neutral)
        for trait, delta in m.items():
            assert abs(delta) < 1e-9, f"{trait}={delta}"

    def test_high_pdi_boosts_authority_compliance(self):
        m = hofstede_to_modifiers({"pdi": 100})
        assert m["authority_compliance"] > 0

    def test_high_idv_boosts_individualism(self):
        m = hofstede_to_modifiers({"idv": 100})
        assert m["individualism"] > 0

    def test_high_uai_raises_loss_aversion_reduces_risk(self):
        m = hofstede_to_modifiers({"uai": 100})
        assert m["loss_aversion"] > 0
        assert m["risk_appetite"] < 0

    def test_high_lto_increases_patience_reduces_impulsivity(self):
        m = hofstede_to_modifiers({"lto": 100})
        assert m["patience"] > 0
        assert m["impulsivity"] < 0

    def test_high_ivr_boosts_extraversion(self):
        m = hofstede_to_modifiers({"ivr": 100})
        assert m["extraversion"] > 0

    def test_modifiers_in_sensible_range(self):
        extreme = {"pdi": 100, "idv": 0, "mas": 100, "uai": 0, "lto": 100, "ivr": 0}
        m = hofstede_to_modifiers(extreme)
        for trait, delta in m.items():
            assert -0.5 <= delta <= 0.5, f"{trait}={delta}"


class TestReligionMapping:
    def test_known_religion_produces_modifiers(self):
        m = religion_to_modifiers("buddhist")
        assert "patience" in m
        assert "spirituality" in m

    def test_unknown_religion_empty(self):
        assert religion_to_modifiers("jedi") == {}

    def test_buddhist_reduces_impulsivity(self):
        m = religion_to_modifiers("buddhist")
        assert m["impulsivity"] < 0
