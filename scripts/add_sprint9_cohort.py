"""Append Napoleon + Leonardo to celebrity_profiles.json with 23-trait expected profiles.

Biographical sourcing — no astrological reasoning. Run once from repo root:
    python scripts/add_sprint9_cohort.py
"""
from __future__ import annotations

import json
from pathlib import Path

PROFILES_PATH = Path("data/validation/celebrity_profiles.json")


NAPOLEON = {
    "name": "Napoleon Bonaparte",
    "birth": {
        "local_iso": "1769-08-15T09:52:00",
        "timezone": "Europe/Paris",
        "latitude": 41.9194,
        "longitude": 8.7386,
        "birth_time_confidence": "aa",
        "astro_databank_rating": "AA",
    },
    "era": "historical",
    "occupation": "politics",
    "sources": [
        "Andrew Roberts, Napoleon: A Life (2014)",
        "Napoleon's own correspondence (Correspondance generale)",
        "Adam Zamoyski, Napoleon: A Life (2018)",
    ],
    "expected_traits": {
        "openness": {"value": 0.80, "confidence": "high",
                     "rationale": "Modernizer; Napoleonic Code, metric system advocacy, military innovation"},
        "conscientiousness": {"value": 0.90, "confidence": "high",
                              "rationale": "Relentless work ethic; detailed campaign planning; prolific correspondence"},
        "extraversion": {"value": 0.70, "confidence": "medium",
                         "rationale": "Commanding battlefield presence and public speeches; also described as brooding in private"},
        "agreeableness": {"value": 0.25, "confidence": "high",
                          "rationale": "Betrayed allies, abandoned armies in Egypt and Russia, ruthless with political rivals"},
        "neuroticism": {"value": 0.55, "confidence": "medium",
                        "rationale": "Documented mood volatility during Russian and Waterloo campaigns"},
        "risk_appetite": {"value": 0.95, "confidence": "high",
                          "rationale": "Invaded Russia; Hundred Days return from Elba; bet everything repeatedly"},
        "analytical_depth": {"value": 0.85, "confidence": "high",
                             "rationale": "Strategic genius; read military history voraciously; drafted legal code"},
        "impulsivity": {"value": 0.50, "confidence": "medium",
                        "rationale": "Meticulous planner but capable of sudden irrevocable decisions (Russia, Waterloo)"},
        "patience": {"value": 0.35, "confidence": "high",
                     "rationale": "Impatient for glory; forced premature campaigns; famous for rapid movement"},
        "social_dominance": {"value": 0.95, "confidence": "high",
                             "rationale": "Self-crowned Emperor; dictated terms to crowned heads of Europe"},
        "herd_susceptibility": {"value": 0.15, "confidence": "high",
                                "rationale": "Acted against consensus repeatedly (coup of 18 Brumaire, self-coronation)"},
        "authority_compliance": {"value": 0.10, "confidence": "high",
                                 "rationale": "Overthrew the Directory; ignored Senate; defined his own legitimacy"},
        "contrarian_tendency": {"value": 0.75, "confidence": "high",
                                "rationale": "Fought successive coalitions; defied European royal order"},
        "empathy": {"value": 0.25, "confidence": "high",
                    "rationale": "Famously cold toward battlefield casualties; abandoned his armies twice"},
        "financial_optimism": {"value": 0.70, "confidence": "medium",
                               "rationale": "Confidence in conquest-funded treasury; Louisiana Purchase for quick cash"},
        "loss_aversion": {"value": 0.15, "confidence": "high",
                          "rationale": "Staked empire on single campaigns; chose risky escape from Elba"},
        "fomo_susceptibility": {"value": 0.55, "confidence": "medium",
                                "rationale": "Driven by need for historical glory; envious of Alexander and Caesar"},
        "communication_assertiveness": {"value": 0.95, "confidence": "high",
                                        "rationale": "Iconic proclamations and addresses; direct command style"},
        "persuasion_skill": {"value": 0.90, "confidence": "high",
                             "rationale": "Rallied exhausted troops at Lodi and Arcola; charmed diplomats and soldiers"},
        "information_sharing": {"value": 0.60, "confidence": "medium",
                                "rationale": "Prolific writer/correspondent yet tightly controlled military intelligence"},
        "tradition_vs_progress": {"value": 0.75, "confidence": "high",
                                  "rationale": "Modernizer of law, administration, education; metric and meritocratic reforms"},
        "individualism": {"value": 0.95, "confidence": "high",
                          "rationale": "'Impossible is not French'; cult of personal destiny"},
        "spirituality": {"value": 0.35, "confidence": "medium",
                         "rationale": "Pragmatic deist; Concordat with Rome was political, not devout"},
    },
}


LEONARDO = {
    "name": "Leonardo da Vinci",
    "birth": {
        "local_iso": "1452-04-15T21:40:00",
        "timezone": "Europe/Rome",
        "latitude": 43.7833,
        "longitude": 10.9167,
        "birth_time_confidence": "aa",
        "astro_databank_rating": "AA",
    },
    "era": "historical",
    "occupation": "science",
    "sources": [
        "Walter Isaacson, Leonardo da Vinci (2017)",
        "Leonardo's own notebooks (Codex Atlanticus, Leicester)",
        "Martin Kemp, Leonardo da Vinci: The Marvellous Works of Nature and Man (2006)",
    ],
    "expected_traits": {
        "openness": {"value": 0.98, "confidence": "high",
                     "rationale": "Archetypal polymath; curiosity spanned painting, anatomy, engineering, botany, hydraulics"},
        "conscientiousness": {"value": 0.30, "confidence": "high",
                              "rationale": "Famously abandoned works (Adoration of the Magi, Battle of Anghiari); Mona Lisa unfinished for years"},
        "extraversion": {"value": 0.55, "confidence": "medium",
                         "rationale": "Charming at Sforza and French courts; but workshop solitary and reserved"},
        "agreeableness": {"value": 0.70, "confidence": "medium",
                          "rationale": "Described by contemporaries as gentle and generous with apprentices"},
        "neuroticism": {"value": 0.40, "confidence": "medium",
                        "rationale": "Some melancholic notebook reflections on time and mortality"},
        "risk_appetite": {"value": 0.60, "confidence": "medium",
                          "rationale": "Served rival patrons across Italy; pursued dangerous anatomical dissections"},
        "analytical_depth": {"value": 0.98, "confidence": "high",
                             "rationale": "Dissected 30+ corpses; invented scientific notation; reverse-engineered flight, hydraulics"},
        "impulsivity": {"value": 0.45, "confidence": "medium",
                        "rationale": "Jumped between projects; but often deliberative on individual experiments"},
        "patience": {"value": 0.55, "confidence": "medium",
                     "rationale": "Iterated obsessively on paintings yet abandoned many due to shifting interests"},
        "social_dominance": {"value": 0.45, "confidence": "medium",
                             "rationale": "Respected court artist; commanded his studio; not politically dominant"},
        "herd_susceptibility": {"value": 0.15, "confidence": "high",
                                "rationale": "Challenged Aristotelian received wisdom; direct empirical observation over authority"},
        "authority_compliance": {"value": 0.40, "confidence": "medium",
                                 "rationale": "Served patrons but on his own terms and schedule"},
        "contrarian_tendency": {"value": 0.80, "confidence": "high",
                                "rationale": "Dissected corpses despite Church prohibition; wrote in mirror script; vegetarian in meat-eating age"},
        "empathy": {"value": 0.75, "confidence": "high",
                    "rationale": "Vegetarian on ethical grounds; bought caged birds to free them; anatomical studies with evident compassion"},
        "financial_optimism": {"value": 0.55, "confidence": "medium",
                               "rationale": "Courted wealthy patrons continuously; confident in securing commissions"},
        "loss_aversion": {"value": 0.40, "confidence": "medium",
                          "rationale": "Relatively stable patronage; but protected notebooks and unfinished works closely"},
        "fomo_susceptibility": {"value": 0.25, "confidence": "medium",
                                "rationale": "Internally driven by curiosity rather than contemporary status competition"},
        "communication_assertiveness": {"value": 0.60, "confidence": "medium",
                                        "rationale": "Prolific in writing yet deliberately coded notebooks to obscure content"},
        "persuasion_skill": {"value": 0.75, "confidence": "high",
                             "rationale": "Secured patronage from Sforza, the French King, the Medici, Cesare Borgia successively"},
        "information_sharing": {"value": 0.25, "confidence": "high",
                                "rationale": "Mirror-script notebooks deliberately resistant to others; trade secrets protected"},
        "tradition_vs_progress": {"value": 0.95, "confidence": "high",
                                  "rationale": "Epitome of progressive empirical thinking breaking from Scholastic tradition"},
        "individualism": {"value": 0.90, "confidence": "high",
                          "rationale": "Uniquely polymathic approach; refused guild and academy constraints"},
        "spirituality": {"value": 0.50, "confidence": "medium",
                         "rationale": "Religious commissions executed; notebook content heterodox and proto-deist"},
    },
}


def main() -> None:
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    if "napoleon_bonaparte" in data["figures"] and "leonardo_da_vinci" in data["figures"]:
        print("Already added — no-op.")
        return

    data["figures"]["napoleon_bonaparte"] = NAPOLEON
    data["figures"]["leonardo_da_vinci"] = LEONARDO

    # Sprint 9 cohort-expansion note
    notes = data.setdefault("notes", {})
    notes["sprint9_cohort_expansion"] = (
        "Sprint 9 added Napoleon Bonaparte (1769) and Leonardo da Vinci (1452) following the "
        "install of seas_12.se1 which extends Kerykeion's asteroid ephemeris coverage back to "
        "1200 CE. Cleopatra (69 BC) remains excluded because Python datetime's minimum year is 1. "
        "Substitute figures (Theodore Roosevelt, Thomas Edison, Nelson Mandela) are retained to "
        "enable direct Sprint 7/8 vs Sprint 9 metric comparisons. Cohort size N=22."
    )
    data["study"] = "Sprint 9 — 22-figure astrological validity (Napoleon + Leonardo added)"

    PROFILES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Added Napoleon + Leonardo. Total figures: {len(data['figures'])}")


if __name__ == "__main__":
    main()
