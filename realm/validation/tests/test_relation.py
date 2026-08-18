"""Tests for the referent-relation direction channel (Sprint 24).

Classification examples here are deliberately NEW sentences, not copies
of Study A dataset entries — the classifier must generalize by rule, not
by memorized phrasing.
"""

from realm.validation.relation import (
    POLARITY_MATRIX,
    classify_event,
    classify_question,
    relation_direction,
)


class TestClassifyQuestion:
    def test_incumbent_standing(self):
        assert classify_question(
            "Will the public approve of Chancellor Schmidt's performance?"
        ) == "incumbent_standing"
        assert classify_question(
            "Will the governing Liberal Party be supported?"
        ) == "incumbent_standing"
        assert classify_question(
            "Will the public be satisfied with the Prime Minister?"
        ) == "incumbent_standing"

    def test_protective_policy(self):
        assert classify_question(
            "Will joining the NATO military alliance be supported?"
        ) == "protective_policy"
        assert classify_question(
            "Will increased defense spending be supported?"
        ) == "protective_policy"

    def test_hazard_policy(self):
        assert classify_question(
            "Will stricter laws covering the sale of firearms be supported?"
        ) == "hazard_policy"
        assert classify_question(
            "Will a complete phase-out of coal power be supported?"
        ) == "hazard_policy"

    def test_rights_policy(self):
        assert classify_question(
            "Will legal access to abortion be supported?"
        ) == "rights_policy"

    def test_confidence_index(self):
        assert classify_question(
            "Will consumers be confident about the economy?"
        ) == "confidence_index"

    def test_unknown(self):
        assert classify_question("Will it rain tomorrow?") == "unknown"


class TestClassifyEvent:
    def test_external_attack(self):
        assert classify_event(
            "Gunmen storm a theater and take hostages; bombs explode across the capital."
        ) == "external_attack"
        assert classify_event(
            "Foreign forces invade the border provinces as missiles strike the capital."
        ) == "external_attack"

    def test_self_inflicted(self):
        assert classify_event(
            "The president grants a pardon to his predecessor for all federal crimes."
        ) == "self_inflicted"
        assert classify_event(
            "The government unveils sweeping unfunded tax cuts; the currency crashes as gilt markets seize up."
        ) == "self_inflicted"

    def test_disaster(self):
        assert classify_event(
            "A tsunami floods the coastal plants; reactor meltdowns force mass evacuations."
        ) == "disaster"
        assert classify_event(
            "A hurricane breaches the levees and floods the city for days."
        ) == "disaster"

    def test_economic_shock(self):
        assert classify_event(
            "The country's largest bank files for bankruptcy as credit markets freeze and stocks crash."
        ) == "economic_shock"

    def test_rights_threat(self):
        assert classify_event(
            "A leaked draft opinion shows the high court is prepared to overturn the constitutional right."
        ) == "rights_threat"

    def test_unknown(self):
        assert classify_event("The annual flower festival opened this weekend.") == "unknown"


class TestPolarityMatrix:
    def test_rally_prior(self):
        polarity, rationale = POLARITY_MATRIX[("external_attack", "incumbent_standing")]
        assert polarity == 1
        assert "Mueller" in rationale

    def test_self_inflicted_negative(self):
        assert POLARITY_MATRIX[("self_inflicted", "incumbent_standing")][0] == -1

    def test_economic_shock_confidence_negative(self):
        assert POLARITY_MATRIX[("economic_shock", "confidence_index")][0] == -1

    def test_all_entries_have_rationales(self):
        for (event_type, question_type), (polarity, rationale) in POLARITY_MATRIX.items():
            assert polarity in (-1, 0, 1)
            assert rationale.strip(), f"({event_type},{question_type}) missing rationale"


class TestRelationDirection:
    def test_rally_case(self):
        polarity, ev, q, rationale = relation_direction(
            "Hijackers crash airliners into the towers; thousands are killed.",
            "Will the public approve of the President's job performance?",
        )
        assert (polarity, ev, q) == (1, "external_attack", "incumbent_standing")
        assert rationale

    def test_unknown_pair_abstains(self):
        polarity, ev, q, _ = relation_direction(
            "The annual flower festival opened this weekend.",
            "Will it rain tomorrow?",
        )
        assert polarity == 0
        assert ev == "unknown" and q == "unknown"

    def test_threat_alliance_positive(self):
        polarity, ev, q, _ = relation_direction(
            "A full-scale invasion of the neighboring country begins as armored columns cross the border.",
            "Will joining the NATO military alliance be supported?",
        )
        assert polarity == 1
        assert q == "protective_policy"
