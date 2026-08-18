"""Referent-relation direction channel (Sprint 24).

Study A falsified the valence channel: it propagates *event sentiment*
onto the population, but real reactions follow the semantic RELATION
between the event and the question's subject (rallies, threat→alliance
support, hazard→hazard-limiting-policy support). This module is the
minimal structured alternative for blinded/offline use: deterministic
keyword classification of (event, question) into archetypes, and a
polarity matrix whose entries are **literature priors with rationales**
— never coefficients fitted to Study A events.

Epistemics: the matrix was frozen at its first commit, BEFORE the
held-out dataset was authored; design-set results are in-sample at the
class level and are labeled so in every report. This channel is
research-only until it clears the pre-stated held-out bar (see
`outputs/study_a_relation_analysis.md`); it is NOT wired into the
production API.
"""

from __future__ import annotations

# ---- Question-subject classification --------------------------------------

_QUESTION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # protective_policy must run before hazard_policy ("defense" questions
    # can mention laws) and before generic support wording.
    ("protective_policy", (
        "nato", "alliance", "defense spending", "defence spending",
        "military spending", "rearmament", "conscription",
    )),
    ("hazard_policy", (
        "stricter law", "stricter gun", "phase-out", "phase out",
        "ban on", "restrictions on", "tighter regulation",
    )),
    ("rights_policy", (
        "abortion", "right to", "civil right", "legal access",
        "same-sex", "marriage equality",
    )),
    ("confidence_index", (
        "confident about the economy", "consumer confidence",
        "economic outlook", "confident about their finances",
    )),
    ("incumbent_standing", (
        "approve", "approval", "satisfied with", "job performance",
        "governing", "prime minister", "president", "chancellor",
        "vote for", "voting intention", "be supported?",
    )),
)


def classify_question(question: str) -> str:
    q = question.lower()
    for label, needles in _QUESTION_RULES:
        if any(n in q for n in needles):
            # "be supported?" alone is too generic to mean incumbent
            # standing unless a leader/party word is present.
            if label == "incumbent_standing":
                anchors = (
                    "approve", "approval", "satisfied", "job performance",
                    "party", "prime minister", "president", "chancellor",
                    "governing", "vote",
                )
                if not any(a in q for a in anchors):
                    continue
            return label
    return "unknown"


# ---- Event-archetype classification ---------------------------------------

_EVENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # self_inflicted before external_attack: incumbent-authored acts
    # (pardon, budget) may also contain crisis vocabulary.
    ("self_inflicted", (
        "pardon", "tax cuts", "mini-budget", "unveils", "opens the borders",
        "opens germany's borders", "orders people to stay",
        "grants", "appoints", "resigns",
    )),
    ("rights_threat", (
        "overturn", "leaked draft", "strike down", "constitutional right",
        "trigger ban",
    )),
    ("external_attack", (
        "attack", "gunmen", "hijack", "bomb", "invade", "invasion",
        "coup", "storm the", "storm a", "massacre", "opens fire",
        "murders", "missile", "airstrike", "air campaign", "quarantine of",
    )),
    ("disaster", (
        "earthquake", "tsunami", "meltdown", "hurricane", "levees",
        "floods", "wildfire", "radioactive", "radiation",
    )),
    ("economic_shock", (
        "bankruptcy", "credit markets", "markets crash", "stocks crash",
        "bear territory", "layoffs", "pandemic", "recession",
        "financial crisis", "currency crashes",
    )),
)


def classify_event(event_summary: str) -> str:
    text = event_summary.lower()
    for label, needles in _EVENT_RULES:
        if any(n in text for n in needles):
            return label
    return "unknown"


# ---- Polarity matrix (literature priors — frozen; rationale mandatory) -----

POLARITY_MATRIX: dict[tuple[str, str], tuple[int, str]] = {
    ("external_attack", "incumbent_standing"): (
        1, "Rally-round-the-flag: external attacks raise incumbent approval (Mueller 1970)."),
    ("external_attack", "protective_policy"): (
        1, "Attacks raise support for protective/security policy."),
    ("external_attack", "hazard_policy"): (
        1, "Salient harm raises support for policy limiting the instrument of harm (e.g. mass shooting -> stricter firearm laws)."),
    ("external_attack", "confidence_index"): (
        -1, "Violent shocks depress economic confidence."),
    ("self_inflicted", "incumbent_standing"): (
        -1, "Self-authored controversial acts are blamed on the incumbent (no rally without an external adversary)."),
    ("self_inflicted", "confidence_index"): (
        -1, "Policy-induced market turmoil depresses confidence."),
    ("disaster", "incumbent_standing"): (
        -1, "Disasters trigger blame attribution for preparedness/response."),
    ("disaster", "hazard_policy"): (
        1, "Hazard salience raises support for hazard-limiting policy (e.g. nuclear accident -> phase-out support)."),
    ("disaster", "confidence_index"): (
        -1, "Large disasters depress economic confidence."),
    ("economic_shock", "confidence_index"): (
        -1, "Economic shocks depress consumer confidence (valence and referent coincide)."),
    ("economic_shock", "incumbent_standing"): (
        -1, "Economic pain is attributed to incumbents (retrospective voting)."),
    ("rights_threat", "rights_policy"): (
        1, "Threat-to-status-quo mobilization: threatening a right raises its support."),
}


def relation_direction(
    event_summary: str, question: str,
) -> tuple[int, str, str, str]:
    """Return (polarity, event_type, question_type, rationale).

    Polarity 0 = honest abstention: the pair is outside the matrix's
    literature priors, so the channel makes no directional claim.
    """
    event_type = classify_event(event_summary)
    question_type = classify_question(question)
    polarity, rationale = POLARITY_MATRIX.get(
        (event_type, question_type), (0, "no literature prior for this pair"),
    )
    return polarity, event_type, question_type, rationale
