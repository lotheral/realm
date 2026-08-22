"""Referent-relation matrix v2 (Sprint 27).

v1 (`relation.py`, frozen at commit f2df2de) failed its pre-stated
held-out bar (4/8) with four informative misses: two abstentions on
archetypes the matrix lacked (military success, incumbent-initiated
conquest / personal scandal), one compound event mis-signed (a
self-authored withdrawal containing an external attack), and one
vocabulary abstention (epidemic text hitting no keyword). The two
design-set misses added the lockdown-rally case (covid_johnson) and
the own-supporters-violence case (jan6).

v2 addresses exactly those failure classes. Its entries remain
**literature priors with mandatory rationales** — never coefficients
fitted to any event set. Epistemics: because v2 was authored AFTER the
design and held-out results were known, results on BOTH of those sets
are in-sample for v2. The only clean test is the third event set, whose
selection criteria are pre-stated in
`docs/study_a_third_set_protocol.md` and which is authored strictly
AFTER this module's freeze commit (auditable in git history, the same
freeze-then-author protocol as Sprint 24).

v1 is intentionally untouched: it must stay byte-for-byte reproducible.
The question-side classifier is unchanged and reused from v1.
"""

from __future__ import annotations

from types import MappingProxyType

from realm.validation.relation import POLARITY_MATRIX, classify_question

MATRIX_VERSION = 2

# ---- Event-archetype classification (v2) -----------------------------------
#
# Precedence encodes attribution logic, top to bottom:
#   1. military_success — a victory rallies regardless of who initiated the
#      operation; success summaries routinely reference the war's attacks,
#      so the success cue must win over attack vocabulary.
#   2. public_health_emergency — restrictive measures ordered in response
#      to an epidemic are crisis context, not self-authored controversy
#      (the covid_johnson lesson).
#   3. self_inflicted — self-authored acts (now incl. withdrawals,
#      mobilization, violence by the incumbent's own supporters) are
#      blamed on the actor even when an external attack occurs inside the
#      event window (the afghanistan_biden lesson).
#   4. personal_scandal, 5. rights_threat, 6. external_attack,
#   7. incumbent_conquest, 8. disaster, 9. economic_shock.

_EVENT_RULES_V2: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("military_success", (
        "victory", "surrender", "surrenders", "liberate", "liberated",
        "recapture", "recaptures", "is captured", "are captured",
        "capture of", "special forces raid", "commando raid",
        "commandos raid", "war ends", "killed in a raid",
        "raid a hideout", "raid the compound", "raid a compound",
    )),
    ("public_health_emergency", (
        "outbreak", "epidemic", "pandemic", "virus",
    )),
    ("self_inflicted", (
        # v1 keywords, verbatim:
        "pardon", "tax cuts", "mini-budget", "unveils", "opens the borders",
        "opens germany's borders", "orders people to stay",
        "grants", "appoints", "resigns",
        # v2 additions (attribution for self-authored operations, incl.
        # election-subversion violence by incumbent-aligned crowds):
        "withdrawal", "withdraws troops", "pulls out", "pull out",
        "drawdown", "mobilization", "supporters storm",
        "overturn the certification", "overturn the election",
    )),
    ("personal_scandal", (
        "extramarital", "affair with", "sexual relationship", "mistress",
        "sex scandal", "lie under oath", "hush money",
    )),
    ("rights_threat", (
        "overturn the constitutional right", "leaked draft", "strike down",
        "constitutional right", "trigger ban",
    )),
    ("external_attack", (
        "attack", "gunmen", "hijack", "bomb", "invade", "invasion",
        "coup", "storm the", "storm a", "massacre", "opens fire",
        "murders", "missile", "airstrike", "air campaign", "quarantine of",
    )),
    ("incumbent_conquest", (
        "annex", "annexes", "annexation",
    )),
    ("disaster", (
        "earthquake", "tsunami", "meltdown", "hurricane", "levees",
        "floods", "wildfire", "radioactive", "radiation",
    )),
    ("economic_shock", (
        # v1 keywords minus "pandemic" (owned by public_health_emergency
        # above, which is checked first anyway):
        "bankruptcy", "credit markets", "markets crash", "stocks crash",
        "bear territory", "layoffs", "recession",
        "financial crisis", "currency crashes",
        # v2 vocabulary additions:
        "bank run", "sell-off", "market rout", "bailout",
        "inflation surges", "default on its debt",
    )),
)


def classify_event_v2(event_summary: str) -> str:
    text = event_summary.lower()
    for label, needles in _EVENT_RULES_V2:
        if any(n in text for n in needles):
            return label
    return "unknown"


# ---- Polarity matrix v2 (literature priors — frozen; rationale mandatory) ---
#
# All v1 rows are inherited verbatim (asserted by tests); new rows below.
# MappingProxyType: the matrix is a frozen scientific artifact and must
# not be mutable at runtime.

POLARITY_MATRIX_V2: MappingProxyType[tuple[str, str], tuple[int, str]] = MappingProxyType({
    **POLARITY_MATRIX,
    ("military_success", "incumbent_standing"): (
        1, "Victory rally: successful dramatic uses of force raise incumbent "
           "approval (Mueller 1970 'dramatic events'; Baum 2002)."),
    ("incumbent_conquest", "incumbent_standing"): (
        1, "Acting-side rally around territorial gain ('Crimea consensus', "
           "Hale 2018; Levada series). Limitation: assumes the question's "
           "population is the acting side, not the victim side."),
    ("personal_scandal", "incumbent_standing"): (
        -1, "Personal scandals on average cost incumbent approval (scandal "
            "literature, e.g. Basinger 2013 on electoral penalties). "
            "Documented counterexample: Clinton 1998 — the prior follows "
            "the average, not the exception."),
    ("public_health_emergency", "incumbent_standing"): (
        1, "Initial crisis rally: COVID-19 produced broad cross-national "
           "approval surges in the immediate window (Yam et al. 2020 PNAS; "
           "Baekgaard et al. 2020; De Vries et al. 2021)."),
    ("public_health_emergency", "confidence_index"): (
        -1, "Epidemic shutdowns depress consumer confidence (sudden-stop "
            "economics)."),
})


def relation_direction_v2(
    event_summary: str, question: str,
) -> tuple[int, str, str, str]:
    """Return (polarity, event_type, question_type, rationale).

    Polarity 0 = honest abstention: the pair is outside the matrix's
    literature priors, so the channel makes no directional claim.
    """
    event_type = classify_event_v2(event_summary)
    question_type = classify_question(question)
    polarity, rationale = POLARITY_MATRIX_V2.get(
        (event_type, question_type), (0, "no literature prior for this pair"),
    )
    return polarity, event_type, question_type, rationale
