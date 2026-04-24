"""Inject literature-grounded facet_coefficients into big_five_derivation.json.

Each derived trait gets a `facet_coefficients` block containing the
literature-preferred facet(s) for each domain that carries a non-zero
domain coefficient. This block is CONSUMED by BigFiveAdapter when
`realm.personality.big_five.use_facets = true` AND the input provides
facet scores.

Falls back to domain coefficients otherwise (backward-compatible).

Literature sources backing these picks:
- Costa_McCrae_1992 (NEO-PI-R): N5 Impulsiveness, C5 Self-Discipline,
  C6 Deliberation, E5 Excitement-Seeking, E6 Positive-Emotion, A4
  Compliance, A6 Tender-Mindedness, O5 Ideas, O6 Values, etc.
- DeYoung_Quilty_Peterson_2007 (BFAS aspects): E3 Assertiveness,
  A.Politeness (≈A4), A.Compassion (≈A6), C.Industriousness (≈C4),
  C.Orderliness (≈C2).
- Zhao_Seibert_2006; Lauriola_Levin_2001 (risk/loss studies).
- Zuckerman sensation-seeking framework (for E5 risk path).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"

# Literature-preferred facet coefficients per derived trait.
# Keys are IPIP-NEO-120 facet codes (O1..O6, C1..C6, ..., N1..N6).
# Coefficient magnitudes follow the same [−0.5, 0.5] REALM convention as
# domain-level coefficients. When multiple facets carry a single domain's
# signal, the sum of their magnitudes should be approximately equal to
# (slightly greater than) the domain coefficient magnitude.
FACET_COEFFS: dict[str, dict[str, float]] = {
    "risk_appetite": {
        # O+0.30 → O5 Ideas (intellect drives novel-situation appetite)
        "O5": 0.30,
        # E+0.20 → E5 Excitement-Seeking (Zuckerman sensation-seeking core)
        "E5": 0.20,
        # N−0.25 → N1 Anxiety (inv): anxious agents avoid risk
        "N1": -0.15,
        # Plus N5 Impulsiveness (+): captures within-N positive component
        "N5": 0.10,
        # C−0.15 → C6 Cautiousness (inv): cautious agents avoid risk
        "C6": -0.15,
        # A−0.15 → A2 Morality (inv): scrupulous agents avoid gambling
        "A2": -0.15,
    },
    "analytical_depth": {
        # O+0.40 → O5 Ideas (intellectual curiosity)
        "O5": 0.40,
        # C+0.30 → C6 Deliberation (careful reasoning before acting)
        "C6": 0.30,
    },
    "impulsivity": {
        # N+0.35 → N5 Impulsiveness (Costa-McCrae canonical facet)
        "N5": 0.35,
        # E+0.20 → E5 Excitement-Seeking (reward-driven behavioral activation)
        "E5": 0.20,
        # C−0.30 → C6 Cautiousness (inv): low cautiousness = impulsive
        "C6": -0.30,
    },
    "patience": {
        # C+0.40 → C5 Self-Discipline (primary patience facet)
        "C5": 0.40,
        # N−0.25 → N5 Impulsiveness (inv): patience = anti-impulsivity
        "N5": -0.25,
        # E−0.10 → E5 Excitement-Seeking (inv): sensation-seeking erodes patience
        "E5": -0.10,
    },
    "social_dominance": {
        # E+0.40 → E3 Assertiveness (BFAS canonical dominance facet)
        "E3": 0.40,
        # A−0.25 → A4 Compliance (inv): anti-Compliance = willing to lead/push
        "A4": -0.25,
    },
    "empathy": {
        # A+0.45 → split A3 Altruism + A6 Tender-Mindedness
        "A3": 0.20,
        "A6": 0.25,
        # N+0.10 → N3 Depression (small +): anxious-empathic sensitivity
        "N3": 0.10,
    },
    "loss_aversion": {
        # N+0.30 → split N1 Anxiety + N3 Depression
        "N1": 0.20,
        "N3": 0.10,
        # C+0.15 → C6 Cautiousness (risk-avoidance orientation)
        "C6": 0.15,
        # E−0.10 → E5 Excitement-Seeking (inv): high sensation-seekers less loss-averse
        "E5": -0.10,
    },
    "financial_optimism": {
        # E+0.30 → E6 Positive-Emotion (cheerful outlook)
        "E6": 0.30,
        # N−0.30 → N3 Depression (inv)
        "N3": -0.30,
        # O+0.10 → O4 Adventurousness (openness-to-upside)
        "O4": 0.10,
    },
    "communication_assertiveness": {
        # E+0.40 → E3 Assertiveness (direct aspect loading)
        "E3": 0.40,
        # A−0.15 → A4 Compliance (inv): willingness to push back
        "A4": -0.15,
    },
    "persuasion_skill": {
        # E+0.35 → split E3 Assertiveness + E6 Warmth/Enthusiasm
        "E3": 0.25,
        "E6": 0.10,
        # A+0.15 → A1 Trust (warm-persuasion style needs trusting disposition)
        "A1": 0.15,
        # O+0.10 → O5 Ideas (cognitive flexibility in framing)
        "O5": 0.10,
    },
    "information_sharing": {
        # E+0.25 → E2 Gregariousness (interaction frequency)
        "E2": 0.25,
        # O+0.20 → O5 Ideas (enjoy intellectual exchange)
        "O5": 0.20,
        # A+0.10 → A3 Altruism (prosocial sharing)
        "A3": 0.10,
    },
    "contrarian_tendency": {
        # A−0.30 → A4 Compliance (inv): anti-compliance = contrarian
        "A4": -0.30,
        # O+0.15 → O6 Liberalism (questioning authority/values)
        "O6": 0.15,
        # C−0.10 → C3 Dutifulness (inv)
        "C3": -0.10,
    },
    "authority_compliance": {
        # A+0.25 → A4 Compliance (direct loading)
        "A4": 0.25,
        # C+0.20 → C3 Dutifulness
        "C3": 0.20,
        # O−0.15 → O6 Liberalism (inv): liberal values question authority
        "O6": -0.15,
    },
}


def main() -> int:
    d = json.loads(DERIVATION_PATH.read_text(encoding="utf-8"))
    traits = d["traits"]
    added = 0
    for trait_name, facet_coeffs in FACET_COEFFS.items():
        if trait_name not in traits:
            print(f"WARNING: {trait_name} not in derivation — skipping")
            continue
        # Attach rounded floats
        traits[trait_name]["facet_coefficients"] = {
            f: round(v, 3) for f, v in facet_coeffs.items()
        }
        added += 1

    # Update schema notes
    d["_facet_formula"] = (
        "When use_facets=true AND all required facets are provided: "
        "value = 0.5 + sum(facet_coeff * (facet_score - 0.5)) over the "
        "trait's facet_coefficients; clamp to [0, 1]. Unlisted facets "
        "contribute 0. Falls back to domain formula otherwise."
    )

    DERIVATION_PATH.write_text(
        json.dumps(d, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Injected facet_coefficients into {added} traits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
