"""Tests for referent-relation matrix v2 (Sprint 27).

As in the v1 tests, classification examples are deliberately NEW
sentences — the classifier must generalize by rule, not by memorized
phrasing. v2 is authored from the design-set + held-out failure
analysis (Sprint 24) and MUST only be evaluated on the third,
yet-unauthored event set (see docs/study_a_third_set_protocol.md).
"""

import pytest

from realm.validation.relation import POLARITY_MATRIX, relation_direction
from realm.validation.relation_v2 import (
    MATRIX_VERSION,
    POLARITY_MATRIX_V2,
    classify_event_v2,
    relation_direction_v2,
)


class TestClassifyEventV2:
    # -- new class: military_success -----------------------------------
    def test_military_success_raid(self):
        assert classify_event_v2(
            "Special forces raid a hideout across the border and kill the "
            "group's long-hunted leader."
        ) == "military_success"

    def test_military_success_surrender(self):
        assert classify_event_v2(
            "The occupying garrison surrenders and the islands are liberated "
            "after a ten-week campaign."
        ) == "military_success"

    def test_victory_beats_attack_vocabulary(self):
        # A victory summary usually references the war's attacks; the
        # success cue must win over external_attack.
        assert classify_event_v2(
            "After years of deadly attacks, government troops recapture the "
            "last insurgent stronghold and declare victory."
        ) == "military_success"

    # -- new class: public_health_emergency ----------------------------
    def test_public_health_emergency(self):
        assert classify_event_v2(
            "A novel virus outbreak is declared a national emergency as "
            "hospitals overflow."
        ) == "public_health_emergency"

    def test_health_emergency_beats_self_inflicted_lockdown(self):
        # Fixes the covid_johnson design miss: a lockdown ordered in
        # response to an epidemic is crisis context, not a self-authored
        # controversial act.
        assert classify_event_v2(
            "As the epidemic spreads, the Prime Minister orders people to "
            "stay at home and closes schools nationwide."
        ) == "public_health_emergency"

    # -- new class: personal_scandal -----------------------------------
    def test_personal_scandal(self):
        assert classify_event_v2(
            "Reports reveal the leader conducted an extramarital affair with "
            "an aide and urged her to lie under oath."
        ) == "personal_scandal"

    # -- new class: incumbent_conquest ---------------------------------
    def test_incumbent_conquest(self):
        assert classify_event_v2(
            "The government annexes the disputed peninsula following a "
            "hastily organized referendum."
        ) == "incumbent_conquest"

    # -- extended self_inflicted ---------------------------------------
    def test_withdrawal_beats_attack_inside_compound_event(self):
        # Fixes the afghanistan_biden held-out miss: a self-authored
        # withdrawal that descends into chaos is blamed on the actor even
        # when an attack occurs inside the event window.
        assert classify_event_v2(
            "The army's withdrawal descends into chaos as a bombing at the "
            "airport kills a dozen soldiers."
        ) == "self_inflicted"

    def test_mobilization_is_self_inflicted(self):
        assert classify_event_v2(
            "The president orders a partial mobilization of reservists for "
            "the war effort."
        ) == "self_inflicted"

    def test_own_supporters_storming_is_self_inflicted(self):
        # Fixes the jan6 design abstention: violence by the incumbent's
        # own supporters is attributed to the incumbent.
        assert classify_event_v2(
            "Supporters storm the parliament building in an attempt to stop "
            "certification of the vote."
        ) == "self_inflicted"

    def test_election_subversion_is_self_inflicted(self):
        # Same class, mob-phrasing variant (generalizes to e.g. the
        # Brazilian Jan 8 2023 riots).
        assert classify_event_v2(
            "Rioters ransack government buildings in the capital seeking to "
            "overturn the certification of the presidential vote."
        ) == "self_inflicted"

    # -- v1 classes still work through v2 ------------------------------
    def test_v1_classes_preserved(self):
        assert classify_event_v2(
            "Foreign forces invade the border provinces as missiles strike "
            "the capital."
        ) == "external_attack"
        assert classify_event_v2(
            "A hurricane breaches the levees and floods the city for days."
        ) == "disaster"
        assert classify_event_v2(
            "The country's largest bank files for bankruptcy as credit "
            "markets freeze."
        ) == "economic_shock"
        assert classify_event_v2(
            "A leaked draft opinion shows the high court is prepared to "
            "overturn the constitutional right."
        ) == "rights_threat"

    def test_unknown(self):
        assert classify_event_v2(
            "The annual flower festival opened this weekend."
        ) == "unknown"


class TestPolarityMatrixV2:
    def test_version_marker(self):
        assert MATRIX_VERSION == 2

    def test_inherits_all_v1_rows_verbatim(self):
        for pair, entry in POLARITY_MATRIX.items():
            assert POLARITY_MATRIX_V2[pair] == entry

    def test_new_rows_present_with_rationales(self):
        new_pairs = [
            ("military_success", "incumbent_standing"),
            ("incumbent_conquest", "incumbent_standing"),
            ("personal_scandal", "incumbent_standing"),
            ("public_health_emergency", "incumbent_standing"),
            ("public_health_emergency", "confidence_index"),
        ]
        for pair in new_pairs:
            polarity, rationale = POLARITY_MATRIX_V2[pair]
            assert polarity in (-1, 1)
            assert rationale.strip(), f"{pair} missing rationale"

    def test_new_row_polarities(self):
        assert POLARITY_MATRIX_V2[("military_success", "incumbent_standing")][0] == 1
        assert POLARITY_MATRIX_V2[("incumbent_conquest", "incumbent_standing")][0] == 1
        assert POLARITY_MATRIX_V2[("personal_scandal", "incumbent_standing")][0] == -1
        assert POLARITY_MATRIX_V2[("public_health_emergency", "incumbent_standing")][0] == 1
        assert POLARITY_MATRIX_V2[("public_health_emergency", "confidence_index")][0] == -1

    def test_matrix_is_immutable(self):
        with pytest.raises(TypeError):
            POLARITY_MATRIX_V2[("x", "y")] = (1, "nope")  # type: ignore[index]


class TestRelationDirectionV2:
    def test_victory_rally(self):
        polarity, ev, q, rationale = relation_direction_v2(
            "Commandos raid the compound and kill the militant leader; "
            "crowds celebrate in the streets.",
            "Will the public approve of the President's job performance?",
        )
        assert (polarity, ev, q) == (1, "military_success", "incumbent_standing")
        assert rationale

    def test_scandal_negative(self):
        polarity, ev, q, _ = relation_direction_v2(
            "The chancellor admits to an extramarital affair with a member "
            "of his staff after weeks of denials.",
            "Will the public be satisfied with the Chancellor's performance?",
        )
        assert (polarity, ev, q) == (-1, "personal_scandal", "incumbent_standing")

    def test_epidemic_depresses_confidence(self):
        polarity, ev, q, _ = relation_direction_v2(
            "A fast-spreading virus outbreak shutters businesses across the "
            "country within days.",
            "Will consumers be confident about the economy?",
        )
        assert (polarity, ev, q) == (-1, "public_health_emergency", "confidence_index")

    def test_unknown_pair_abstains(self):
        polarity, ev, q, _ = relation_direction_v2(
            "The annual flower festival opened this weekend.",
            "Will it rain tomorrow?",
        )
        assert polarity == 0

    def test_v1_still_abstains_on_victory(self):
        # Documents the v1→v2 delta: frozen v1 has no victory class and
        # must remain byte-for-byte stable for reproducibility.
        polarity, ev, _, _ = relation_direction(
            "Commandos raid the compound and kill the militant leader; "
            "crowds celebrate in the streets.",
            "Will the public approve of the President's job performance?",
        )
        assert ev != "military_success"
