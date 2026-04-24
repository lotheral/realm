"""Generate a synthetic population with both demographic + Big Five data.

Wires WorldGenerator (demographics) together with sample_bf_population
(synthetic OCEAN scores from Costa & McCrae norms) and injects the OCEAN
dict into each DemographicProfile via dataclasses.replace().

Provides:
- `build_bf_profiles(n, seed)` library function — used by validate_bf_study.py
  and any future butterfly comparison that needs the BigFive path.
- CLI:    python scripts/generate_bf_population.py [N=10000] [--seed=42] [--save]

The CLI prints summary stats and optionally writes a JSON snapshot to
outputs/bf_population_snapshot.json for inspection.
"""

from __future__ import annotations

import contextlib
import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from realm.demographics.interfaces import DemographicProfile  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.personality.bf_population import OCEAN, sample_bf_population  # noqa: E402


def build_bf_profiles(
    n: int, seed: int = 42,
) -> list[DemographicProfile]:
    """Return n DemographicProfiles with synthetic Big Five scores attached.

    The demographic side uses WorldGenerator(master_seed=seed) — same
    real-world-weighted distribution scripts/build_calibration_stats.py uses.
    The OCEAN side uses sample_bf_population(seed=seed+1) so demographic and
    Big Five RNGs are independent (no spurious correlation between e.g.
    country and Openness).
    """
    profiles = WorldGenerator(master_seed=seed).generate(n)
    scores_list = sample_bf_population(n, seed=seed + 1)
    return [
        replace(p, big_five_scores=scores)
        for p, scores in zip(profiles, scores_list, strict=True)
    ]


def _summary(profiles: list[DemographicProfile]) -> dict[str, object]:
    n = len(profiles)
    countries: dict[str, int] = {}
    ages: list[int] = []
    bf_means: dict[str, float] = dict.fromkeys(OCEAN, 0.0)
    for p in profiles:
        countries[p.country] = countries.get(p.country, 0) + 1
        ages.append(p.age_years)
        for k in OCEAN:
            bf_means[k] += float(p.big_five_scores[k])  # type: ignore[index]
    for k in OCEAN:
        bf_means[k] /= n
    top5 = sorted(countries.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "n": n,
        "age_mean": statistics.mean(ages),
        "age_stdev": statistics.pstdev(ages),
        "top5_countries": top5,
        "bf_means": {k: round(v, 4) for k, v in bf_means.items()},
    }


def _parse_argv(argv: list[str]) -> tuple[int, int, bool]:
    n = 10000
    seed = 42
    save = False
    for arg in argv[1:]:
        if arg == "--save":
            save = True
        elif arg.startswith("--seed="):
            seed = int(arg.split("=", 1)[1])
        elif arg.isdigit():
            n = int(arg)
    return n, seed, save


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    n, seed, save = _parse_argv(argv)

    print(f"Generating BF population: n={n}, seed={seed}")
    profiles = build_bf_profiles(n, seed=seed)
    summary = _summary(profiles)

    print("\n--- Summary ---")
    print(f"  Population size:    {summary['n']}")
    print(f"  Age mean / stdev:   {summary['age_mean']:.1f}  /  {summary['age_stdev']:.1f}")
    print("  Top 5 countries (count):")
    for iso2, c in summary["top5_countries"]:  # type: ignore[union-attr]
        print(f"    {iso2:>3}  {c}")
    print("  Big Five sample means:")
    for k, v in summary["bf_means"].items():  # type: ignore[union-attr]
        print(f"    {k:<22} {v:.4f}")

    if save:
        out = PROJECT_ROOT / "outputs" / "bf_population_snapshot.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "summary": summary,
            "first_5_profiles": [
                {
                    "agent_id": p.agent_id,
                    "country": p.country,
                    "city": p.city,
                    "age_years": p.age_years,
                    "big_five_scores": dict(p.big_five_scores or {}),
                }
                for p in profiles[:5]
            ],
        }
        out.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
        print(f"\nSnapshot saved: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
