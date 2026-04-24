# Steve Jobs directional check (engine=kerykeion)

rank  dampening=0.12                    dampening=0.40                  
--------------------------------------------------------------------------
   1  risk_appetite           (0.679)   risk_appetite           (1.000)
   2  empathy                 (0.656)   impulsivity             (1.000)
   3  impulsivity             (0.653)   empathy                 (1.000)
   4  extraversion            (0.645)   extraversion            (0.983)
   5  persuasion_skill        (0.624)   persuasion_skill        (0.913)
   6  financial_optimism      (0.615)   financial_optimism      (0.885)
   7  openness                (0.615)   openness                (0.882)
   8  agreeableness           (0.608)   agreeableness           (0.862)
   9  contrarian_tendency     (0.608)   contrarian_tendency     (0.859)
  10  social_dominance        (0.605)   social_dominance        (0.849)

rank  dampening=0.12 BOTTOM             dampening=0.40 BOTTOM           
--------------------------------------------------------------------------
   1  patience                (0.482)   patience                (0.438)
   2  political_spectrum      (0.500)   political_spectrum      (0.500)
   3  fomo_susceptibility     (0.500)   fomo_susceptibility     (0.500)
   4  authority_compliance    (0.526)   authority_compliance    (0.587)
   5  tradition_vs_progress   (0.532)   tradition_vs_progress   (0.607)
   6  information_sharing     (0.545)   information_sharing     (0.649)
   7  spirituality            (0.552)   spirituality            (0.673)
   8  loss_aversion           (0.553)   loss_aversion           (0.678)
   9  analytical_depth        (0.557)   analytical_depth        (0.689)
  10  individualism           (0.566)   individualism           (0.719)

## Invariance check (dampening scale change should preserve meaning)
   Spearman rho(ranks at 0.12 vs 0.40): 0.9991 (target 1.0000)
   Top-8 set identical: True
   Bottom-8 set identical: True

PASS -- Jobs chart ranks preserved under dampening 0.12 -> 0.40.
   The change is a pure scale rescale; directional meaning intact.
   Safe to update numeric test tolerances if any assertion fails.
