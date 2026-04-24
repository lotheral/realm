"""Phase 2 end-to-end validation.

Generates a batch of REALM agents (demographic + natal + trait + culture),
prints distribution statistics, cultural shift summary, and sample profiles.
Lets you sanity-check the global pipeline against realistic expectations.

Usage:
    python scripts/validate_phase2.py [N_AGENTS]
    Default: 2000 agents (~45 seconds on a GMKtec).
"""

from __future__ import annotations

import contextlib
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env so KERYKEION_GEONAMES_USERNAME / LLM keys / model overrides are visible.
import contextlib as _ctx  # noqa: E402

with _ctx.suppress(ImportError):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.agents.interfaces import Agent  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.culture.modifier import compose_modifiers  # noqa: E402
from realm.demographics.country_data import get_hofstede  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.personality.embedder import get_personality_embedder  # noqa: E402
from realm.personality.trait_vector import TraitVector, mean_trait_vector  # noqa: E402

logger = get_logger(__name__)


def _bar(frac: float, width: int = 40) -> str:
    filled = int(round(frac * width))
    return "#" * filled + "." * (width - filled)


def print_country_distribution(agents: list[Agent]) -> None:
    counts = Counter(a.profile.country for a in agents)
    total = len(agents)
    print("\n[ Country distribution — top 15 ]")
    for iso, c in counts.most_common(15):
        pct = c / total
        print(f"  {iso:3s} {c:5d}  {pct*100:5.1f}%  [{_bar(pct, 30)}]")


def print_profession_distribution(agents: list[Agent]) -> None:
    counts = Counter(a.profile.profession_code for a in agents)
    total = len(agents)
    print("\n[ Profession distribution ]")
    for code, c in counts.most_common():
        pct = c / total
        print(f"  {code:16s} {c:5d}  {pct*100:5.1f}%  [{_bar(pct, 30)}]")


def print_age_histogram(agents: list[Agent]) -> None:
    ages = [a.profile.age_years for a in agents]
    bins = [(18, 25), (25, 35), (35, 45), (45, 55), (55, 65), (65, 75), (75, 91)]
    print("\n[ Age histogram ]")
    total = len(ages)
    for lo, hi in bins:
        c = sum(1 for a in ages if lo <= a < hi)
        print(f"  [{lo:2d}-{hi-1:2d}]  {c:5d}  {c*100/total:5.1f}%  [{_bar(c/total, 30)}]")
    print(f"  mean={statistics.mean(ages):.1f}y  median={statistics.median(ages):.0f}y  "
          f"min={min(ages)}y  max={max(ages)}y")


def print_income_stats(agents: list[Agent]) -> None:
    incomes = [a.profile.income_annual_usd for a in agents
               if a.profile.income_annual_usd > 0]
    if not incomes:
        return
    incomes.sort()
    total = len(incomes)
    def pct(p: float) -> float:
        idx = max(0, min(total - 1, int(p * total)))
        return incomes[idx]
    print("\n[ Income (USD/year, excluding zero-income) ]")
    print(f"  p10={pct(0.10):>10,.0f}   median={pct(0.50):>10,.0f}   "
          f"p90={pct(0.90):>10,.0f}   p99={pct(0.99):>10,.0f}")
    print(f"  mean={statistics.mean(incomes):>10,.0f}   max={max(incomes):>10,.0f}")


def print_education_distribution(agents: list[Agent]) -> None:
    counts = Counter(a.profile.education_level for a in agents)
    total = len(agents)
    print("\n[ Education distribution ]")
    for level in ("primary", "secondary", "bachelor", "graduate"):
        c = counts.get(level, 0)
        print(f"  {level:10s}  {c:5d}  {c*100/total:5.1f}%  [{_bar(c/total, 30)}]")


def print_gender_breakdown(agents: list[Agent]) -> None:
    counts = Counter(a.profile.gender for a in agents)
    total = len(agents)
    print("\n[ Gender ]")
    for g in ("M", "F", "X"):
        c = counts.get(g, 0)
        print(f"  {g}  {c:5d}  {c*100/total:5.1f}%")


def print_marginal_breakdown(agents: list[Agent]) -> None:
    counts = Counter(a.profile.marginal_category or "ordinary" for a in agents)
    total = len(agents)
    print("\n[ Marginal profile ]")
    for cat in ("ordinary", "expert", "outlier", "influencer"):
        c = counts.get(cat, 0)
        print(f"  {cat:12s}  {c:5d}  {c*100/total:5.1f}%")


def print_mean_hofstede(agents: list[Agent]) -> None:
    dims = ("pdi", "idv", "mas", "uai", "lto", "ivr")
    sums = dict.fromkeys(dims, 0.0)
    for a in agents:
        scores = get_hofstede(a.profile.country)
        for d in dims:
            sums[d] += scores[d]
    n = len(agents)
    print("\n[ Mean Hofstede (population-weighted) ]")
    for d in dims:
        mean = sums[d] / n
        print(f"  {d.upper()}  {mean:5.1f}  [{_bar(mean/100, 30)}]")


def print_trait_stats(
    agents: list[Agent], title: str, pre_cultural: bool = False,
) -> None:
    if pre_cultural:
        # Recompute natal-only trait vectors (cultural modifier NOT applied)
        embedder = get_personality_embedder("rule_based")
        vectors = [embedder.embed(a.natal_chart) for a in agents]
    else:
        vectors = [a.traits for a in agents]

    names = TraitVector.trait_names()
    print(f"\n[ {title} ]")
    print(f"  {'trait':32s}  {'mean':>6s}  {'median':>6s}  {'min':>5s}  {'max':>5s}  {'std':>5s}")
    for n in names:
        vals = [getattr(v, n) for v in vectors]
        print(f"  {n:32s}  {statistics.mean(vals):.3f}   "
              f"{statistics.median(vals):.3f}   "
              f"{min(vals):.2f}   {max(vals):.2f}   "
              f"{statistics.stdev(vals) if len(vals) > 1 else 0:.3f}")


def print_cultural_shift(agents: list[Agent]) -> None:
    """Compare natal-only vs natal+cultural trait means."""
    embedder = get_personality_embedder("rule_based")
    natal_means = mean_trait_vector(embedder.embed(a.natal_chart) for a in agents)
    final_means = mean_trait_vector(a.traits for a in agents)

    diffs = []
    for n in TraitVector.trait_names():
        pre = getattr(natal_means, n)
        post = getattr(final_means, n)
        diffs.append((n, post - pre))
    diffs.sort(key=lambda kv: abs(kv[1]), reverse=True)

    print("\n[ Cultural shift (natal+culture mean − natal mean) — top 10 traits ]")
    for n, delta in diffs[:10]:
        arrow = "↑" if delta > 0 else "↓"
        print(f"  {n:32s}  {delta:+.4f}  {arrow}")


def print_sample_profiles(agents: list[Agent], n: int = 5) -> None:
    print("\n[ Sample profiles ]")
    for a in agents[:n]:
        p = a.profile
        sun = a.natal_chart.planet("Sun")
        moon = a.natal_chart.planet("Moon")
        hof = get_hofstede(p.country)
        mods = compose_modifiers(p)
        top_mod = max(mods.items(), key=lambda kv: abs(kv[1]))
        print(f"  {p.short_label()}")
        print(f"    {p.profession_name}, {p.education_level}, ${p.income_annual_usd:,.0f}/yr, "
              f"{p.primary_religion}, marginal={p.marginal_category}")
        print(f"    Sun {sun.sign} {sun.sign_degree:.1f}°, Moon {moon.sign} {moon.sign_degree:.1f}°")
        print(f"    Hofstede: PDI={hof['pdi']} IDV={hof['idv']} MAS={hof['mas']} "
              f"UAI={hof['uai']} LTO={hof['lto']} IVR={hof['ivr']}")
        print(f"    Strongest cultural shift: {top_mod[0]} ({top_mod[1]:+.3f})")


def main(argv: list[str]) -> int:
    setup_logging(level="INFO")

    n_agents = int(argv[1]) if len(argv) > 1 else 2000

    logger.info("Generating %d agents…", n_agents)
    t0 = time.perf_counter()

    gen = WorldGenerator(master_seed=42)
    factory = AgentFactory()
    profiles = gen.generate(n_agents)
    agents = factory.build_batch(profiles)

    elapsed = time.perf_counter() - t0
    print(f"\nBuilt {len(agents)}/{n_agents} agents in {elapsed:.1f}s "
          f"({elapsed*1000/max(len(agents),1):.1f}ms/agent)")

    print_country_distribution(agents)
    print_age_histogram(agents)
    print_gender_breakdown(agents)
    print_profession_distribution(agents)
    print_income_stats(agents)
    print_education_distribution(agents)
    print_marginal_breakdown(agents)
    print_mean_hofstede(agents)
    print_cultural_shift(agents)
    print_trait_stats(agents, "Final trait stats (natal + cultural)", pre_cultural=False)
    print_sample_profiles(agents, n=5)

    print(f"\n{'=' * 78}")
    print(f"  Phase 2 validation complete — {len(agents)} agents.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
