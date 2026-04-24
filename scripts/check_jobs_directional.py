"""Directional-invariant check for Steve Jobs chart across dampening changes.

Does NOT assert numeric values (those are tuning-sensitive). Instead verifies
that the *ranking* of traits — which ones are high, which are low — is stable
across the old dampening (0.12) and the new default (0.40). This is the
semantic meaning the earlier session validated anecdotally.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.astro.fixtures import STEVE_JOBS  # noqa: E402
from realm.personality.rule_based import RuleBasedEmbedder  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402


def _rank(tv: TraitVector) -> list[tuple[str, float]]:
    items = [(n, getattr(tv, n)) for n in TraitVector.trait_names()]
    items.sort(key=lambda kv: kv[1], reverse=True)
    return items


def main() -> int:
    engine = get_astro_engine("auto")
    chart = engine.calculate_natal_chart(
        birth_dt=STEVE_JOBS.birth_dt,
        latitude=STEVE_JOBS.latitude,
        longitude=STEVE_JOBS.longitude,
        timezone=STEVE_JOBS.timezone,
    )

    damp_values = (0.12, 0.40)
    results: dict[float, list[tuple[str, float]]] = {}
    for d in damp_values:
        tv = RuleBasedEmbedder(dampening=d).embed(chart)
        results[d] = _rank(tv)

    print(f"# Steve Jobs directional check (engine={engine.backend_name})")
    print()
    print(f"{'rank':>4s}  {'dampening=0.12':32s}  {'dampening=0.40':32s}")
    print("-" * 74)
    n_show = 10
    for i in range(n_show):
        a_name, a_val = results[0.12][i]
        b_name, b_val = results[0.40][i]
        print(f"  {i+1:2d}  {a_name:24s}({a_val:.3f})   {b_name:24s}({b_val:.3f})")

    print()
    print(f"{'rank':>4s}  {'dampening=0.12 BOTTOM':32s}  {'dampening=0.40 BOTTOM':32s}")
    print("-" * 74)
    for i in range(n_show):
        j = -(i + 1)
        a_name, a_val = results[0.12][j]
        b_name, b_val = results[0.40][j]
        print(f"  {i+1:2d}  {a_name:24s}({a_val:.3f})   {b_name:24s}({b_val:.3f})")

    # Invariant: dampening is a scale change only. Two independent checks:
    #   (a) the SET of top-K traits is identical across dampening values
    #   (b) the ranking is identical (Spearman rho == 1.0 for the full 24)
    # Both must hold. Anything less means dampening shifted semantic character,
    # not just magnitudes, and the change should be investigated.
    rank_map = {d: {name: i for i, (name, _) in enumerate(res)}
                for d, res in results.items()}
    names = list(TraitVector.trait_names())
    ranks_a = [rank_map[0.12][n] for n in names]
    ranks_b = [rank_map[0.40][n] for n in names]

    # Spearman on rank vectors — same rank ordering = perfect correlation
    n = len(names)
    mean_r = (n - 1) / 2
    num = sum((ra - mean_r) * (rb - mean_r) for ra, rb in zip(ranks_a, ranks_b, strict=True))
    den_a = sum((ra - mean_r) ** 2 for ra in ranks_a) ** 0.5
    den_b = sum((rb - mean_r) ** 2 for rb in ranks_b) ** 0.5
    spearman = num / (den_a * den_b) if den_a and den_b else 0.0

    k = 8
    top_k_a = {n for n, _ in results[0.12][:k]}
    top_k_b = {n for n, _ in results[0.40][:k]}
    bottom_k_a = {n for n, _ in results[0.12][-k:]}
    bottom_k_b = {n for n, _ in results[0.40][-k:]}

    print()
    print("## Invariance check (dampening scale change should preserve meaning)")
    print(f"   Spearman rho(ranks at 0.12 vs 0.40): {spearman:.4f} (target 1.0000)")
    print(f"   Top-{k} set identical: {top_k_a == top_k_b}")
    if top_k_a != top_k_b:
        print(f"     Only in 0.12: {sorted(top_k_a - top_k_b)}")
        print(f"     Only in 0.40: {sorted(top_k_b - top_k_a)}")
    print(f"   Bottom-{k} set identical: {bottom_k_a == bottom_k_b}")
    if bottom_k_a != bottom_k_b:
        print(f"     Only in 0.12: {sorted(bottom_k_a - bottom_k_b)}")
        print(f"     Only in 0.40: {sorted(bottom_k_b - bottom_k_a)}")

    passed = spearman > 0.999 and top_k_a == top_k_b and bottom_k_a == bottom_k_b
    if not passed:
        print("\nFAIL -- Jobs chart semantic character drifted with dampening change.")
        print("   Do NOT update numeric test tolerances until this is explained.")
        return 1

    print("\nPASS -- Jobs chart ranks preserved under dampening 0.12 -> 0.40.")
    print("   The change is a pure scale rescale; directional meaning intact.")
    print("   Safe to update numeric test tolerances if any assertion fails.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
