"""Phase 1 end-to-end validation.

Runs the full pipeline `birth data → natal chart → TraitVector` on a set of
well-documented historical figures and prints the resulting personality profiles
for sanity-check against biographical consensus.

Usage:
    python scripts/validate_phase1.py
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

# UTF-8 stdout on Windows consoles (cp1252 default).
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Ensure the project root is on sys.path when run as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env so KERYKEION_GEONAMES_USERNAME / LLM keys / model overrides are visible.
import contextlib as _ctx  # noqa: E402

with _ctx.suppress(ImportError):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(PROJECT_ROOT / ".env")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.astro.fixtures import ALAN_TURING, CARL_SAGAN, STEVE_JOBS  # noqa: E402
from realm.core.logging import get_logger, setup_logging  # noqa: E402
from realm.personality.embedder import get_personality_embedder  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

logger = get_logger(__name__)

SUBJECTS = [STEVE_JOBS, CARL_SAGAN, ALAN_TURING]


def format_trait_bar(value: float, width: int = 30) -> str:
    filled = int(round(value * width))
    bar = "#" * filled + "." * (width - filled)
    deviation = value - 0.5
    marker = ""
    if deviation > 0.05:
        marker = f"  (+{deviation:.2f})"
    elif deviation < -0.05:
        marker = f"  ({deviation:.2f})"
    return f"[{bar}] {value:.3f}{marker}"


def print_profile(name: str, chart_info: str, traits: TraitVector) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {name}")
    print(f"  {chart_info}")
    print("=" * 72)

    groups = [
        ("Big Five", ["openness", "conscientiousness", "extraversion",
                      "agreeableness", "neuroticism"]),
        ("Decision making", ["risk_appetite", "analytical_depth",
                             "impulsivity", "patience"]),
        ("Social dynamics", ["social_dominance", "herd_susceptibility",
                             "authority_compliance", "contrarian_tendency", "empathy"]),
        ("Financial", ["financial_optimism", "loss_aversion", "fomo_susceptibility"]),
        ("Communication", ["communication_assertiveness", "persuasion_skill",
                           "information_sharing"]),
        ("Worldview", ["political_spectrum", "tradition_vs_progress",
                       "individualism", "spirituality"]),
    ]

    d = traits.to_dict()
    for title, names in groups:
        print(f"\n  [ {title} ]")
        for n in names:
            print(f"    {n:32s}  {format_trait_bar(d[n])}")


def highlights(name: str, traits: TraitVector, top_n: int = 3) -> None:
    """Print the top-N most deviant traits (positive and negative)."""
    d = traits.to_dict()
    ranked = sorted(d.items(), key=lambda kv: kv[1] - 0.5)
    lowest = ranked[:top_n]
    highest = ranked[-top_n:][::-1]
    print("\n  [ Highlights ]")
    print("    Strongest upward shifts:")
    for n, v in highest:
        print(f"      {n:32s} {v:.3f}  (+{v-0.5:.3f})")
    print("    Strongest downward shifts:")
    for n, v in lowest:
        print(f"      {n:32s} {v:.3f}  ({v-0.5:+.3f})")


def main() -> int:
    setup_logging(level="INFO")

    engine = get_astro_engine("auto")
    embedder = get_personality_embedder("rule_based")

    logger.info("Astro backend: %s", engine.backend_name)
    logger.info("Personality mode: %s", embedder.mode)

    for subject in SUBJECTS:
        try:
            chart = engine.calculate_natal_chart(
                birth_dt=subject.birth_dt,
                latitude=subject.latitude,
                longitude=subject.longitude,
                timezone=subject.timezone,
            )
        except Exception as e:
            logger.error("Failed to compute chart for %s: %s", subject.name, e)
            continue

        sun = chart.planet("Sun")
        moon = chart.planet("Moon")
        chart_info = (
            f"Sun {sun.sign} {sun.sign_degree:.1f}°, "
            f"Moon {moon.sign} {moon.sign_degree:.1f}°, "
            f"Asc {int(chart.ascendant)}°  "
            f"({len(chart.aspects)} aspects, backend={engine.backend_name})"
        )

        traits = embedder.embed(chart)
        print_profile(subject.name, chart_info, traits)
        highlights(subject.name, traits)

    print(f"\n{'=' * 72}")
    print("  Phase 1 validation complete.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
