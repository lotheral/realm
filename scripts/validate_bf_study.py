"""BigFiveAdapter validity study — comparative report.

Runs the same synthetic Big Five population through two input adapters
(BigFive and Astrological) with calibration both off and on, measuring:

  1. Pass-through accuracy (Big Five input <-> output Pearson r)
  2. Per-trait distribution shape (mean, std, skew, kurtosis)
  3. Fallback/excluded trait behavior under each calibration state
  4. Big Five 5x5 intercorrelation preservation
  5. Derived 13x13 intercorrelation structure (predicted vs observed)
  6. Cross-path comparison (BigFive vs Astrological)
  7. Butterfly lift — 4 combos of (adapter, cal state)
  8. Honest limitations section
  9. Success criteria evaluation

Output:    outputs/bf_validity_study.md

Usage:
    python scripts/validate_bf_study.py [N=10000] [--seed=42]
    python scripts/validate_bf_study.py 2000 --seed=42     # faster smoke
"""

from __future__ import annotations

import contextlib as _ctx
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.core.logging import setup_logging  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402
from realm.ingestion.scenarios import build_tech_scenario  # noqa: E402
from realm.output.predictor import (  # noqa: E402
    BranchSpec,
    PredictionEngine,
    observe_topic_share,
)
from realm.personality.adapters import get_input_adapter  # noqa: E402
from realm.personality.bf_population import DEFAULT_CORRELATIONS, OCEAN  # noqa: E402
from realm.personality.calibration import TraitCalibrator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

# We reuse the BF population helper from the sister script.
sys.path.insert(0, str(ROOT / "scripts"))
from generate_bf_population import build_bf_profiles  # noqa: E402

BIG_FIVE = OCEAN  # alias for readability
DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"
TARGET_STD_MIN = 0.14
PASS_THROUGH_MIN = 0.99  # Big Five input<->output Pearson r threshold
DERIVED_STD_MIN = 0.05


# --------------------------------------------------------------------------
# Stats helpers
# --------------------------------------------------------------------------

def _moments(vals: list[float]) -> tuple[float, float, float, float]:
    n = len(vals)
    if n < 2:
        return (vals[0] if vals else 0.0, 0.0, 0.0, 0.0)
    m = statistics.mean(vals)
    s = statistics.stdev(vals)
    if s < 1e-9:
        return (m, 0.0, 0.0, 0.0)
    skew = sum((v - m) ** 3 for v in vals) / (n * s ** 3)
    kurt = sum((v - m) ** 4 for v in vals) / (n * s ** 4) - 3.0
    return (m, s, skew, kurt)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-9 or dy < 1e-9:
        return 0.0
    return num / (dx * dy)


# --------------------------------------------------------------------------
# Pipeline runs
# --------------------------------------------------------------------------

def _make_calibrator(enabled: bool, adapter_type: str) -> TraitCalibrator:
    if enabled:
        return TraitCalibrator(
            enabled=True,
            target_mean=0.50,
            target_std=0.17,
            adapter_type=adapter_type,
        )
    return TraitCalibrator(enabled=False)


def run_pipeline(
    profiles, adapter_type: str, enable_calibration: bool,
) -> dict[str, list[float]]:
    """Build agents via factory, return {trait: [value per agent]}."""
    adapter = get_input_adapter(adapter_type)
    calibrator = _make_calibrator(enable_calibration, adapter_type)
    factory = AgentFactory(adapter=adapter, calibrator=calibrator)
    agents = factory.build_batch(profiles)
    data: dict[str, list[float]] = {n: [] for n in TraitVector.trait_names()}
    for a in agents:
        for n in TraitVector.trait_names():
            data[n].append(getattr(a.traits, n))
    return data


# --------------------------------------------------------------------------
# Derivation table — used for structural-pair predictions
# --------------------------------------------------------------------------

def _load_derivation() -> dict[str, dict[str, float]]:
    """Return {trait_name: {bf_key: coefficient}} for traits with entries."""
    if not DERIVATION_PATH.exists():
        return {}
    raw = json.loads(DERIVATION_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict[str, float]] = {}
    for trait, entry in raw.get("traits", {}).items():
        coeffs = entry.get("coefficients")
        if coeffs:
            out[trait] = {k: float(v) for k, v in coeffs.items()}
    return out


def _dominant_driver(coeffs: dict[str, float]) -> tuple[str, float]:
    """Return (bf_key, coefficient) with largest |coefficient|."""
    return max(coeffs.items(), key=lambda kv: abs(kv[1]))


def structural_pairs(
    derivation: dict[str, dict[str, float]],
) -> list[tuple[str, str, str, int]]:
    """Return [(trait_a, trait_b, shared_driver, predicted_sign), ...].

    Two derived traits are "structurally paired" when their dominant OCEAN
    drivers match. Predicted sign of the correlation between them is the
    product of the signs of their dominant coefficients.
    """
    entries = [
        (trait, *_dominant_driver(coeffs))
        for trait, coeffs in derivation.items()
    ]
    pairs = []
    for i in range(len(entries)):
        trait_a, drv_a, coef_a = entries[i]
        for j in range(i + 1, len(entries)):
            trait_b, drv_b, coef_b = entries[j]
            if drv_a == drv_b:
                predicted_sign = 1 if coef_a * coef_b > 0 else -1
                pairs.append((trait_a, trait_b, drv_a, predicted_sign))
    return pairs


# --------------------------------------------------------------------------
# Butterfly comparison
# --------------------------------------------------------------------------

def _astro_agent_builder(enable_cal: bool):
    def builder(seed: int, n: int):
        factory = AgentFactory(
            calibrator=_make_calibrator(enable_cal, "astrological"),
        )
        return factory.build_batch(
            WorldGenerator(master_seed=seed).generate(n),
        )
    return builder


def _bf_agent_builder(enable_cal: bool):
    def builder(seed: int, n: int):
        adapter = get_input_adapter("big_five")
        factory = AgentFactory(
            adapter=adapter,
            calibrator=_make_calibrator(enable_cal, "big_five"),
        )
        profiles = build_bf_profiles(n, seed=seed)
        return factory.build_batch(profiles)
    return builder


def run_butterfly(
    adapter_type: str, enable_cal: bool, master_seed: int,
) -> tuple[float, float, float]:
    """Return (baseline_mean, scenario_mean, lift)."""
    builder = (
        _bf_agent_builder(enable_cal) if adapter_type == "big_five"
        else _astro_agent_builder(enable_cal)
    )
    common = {
        "name": "tech_share",
        "observe": observe_topic_share("tech"),
        "threshold": 0.30,
        "horizon_ticks": 12,
        "n_branches": 3,
        "n_agents": 150,
        "agent_builder": builder,
    }
    baseline = BranchSpec(**common)
    scenario = BranchSpec(**common, initial_events=build_tech_scenario())
    engine = PredictionEngine(master_seed=master_seed)
    base_out = engine.run(baseline)
    scn_out = engine.run(scenario)
    return (base_out.mean_value, scn_out.mean_value,
            scn_out.mean_value - base_out.mean_value)


# --------------------------------------------------------------------------
# Report builders
# --------------------------------------------------------------------------

def _per_trait_table(
    names: tuple[str, ...], data: dict[str, list[float]],
    threshold: float = TARGET_STD_MIN,
) -> list[str]:
    lines = ["| trait | mean | std | skew | kurtosis | meets std target? |",
             "|-------|------|-----|------|----------|-------------------|"]
    for n in names:
        m, s, sk, kt = _moments(data[n])
        ok = "yes" if s >= threshold else "no"
        lines.append(
            f"| {n} | {m:.3f} | {s:.3f} | {sk:+.2f} | {kt:+.2f} | {ok} |",
        )
    return lines


def _mean_std_row(label: str, data: dict[str, list[float]]) -> str:
    stds = [_moments(data[n])[1] for n in TraitVector.trait_names()]
    mean_std = statistics.mean(stds)
    pass_count = sum(1 for s in stds if s >= TARGET_STD_MIN)
    return f"| {label} | {mean_std:.3f} | {pass_count}/24 |"


def build_report(
    n_agents: int, seed: int,
    bf_scores: list[dict[str, float]],
    runs: dict[tuple[str, bool], dict[str, list[float]]],
    butterfly: dict[tuple[str, bool], tuple[float, float, float]],
) -> str:
    derivation = _load_derivation()
    s_pairs = structural_pairs(derivation)
    derived_traits = tuple(sorted(derivation.keys()))
    fallback_traits = tuple(
        n for n in TraitVector.trait_names()
        if n not in BIG_FIVE and n not in derivation and n != "political_spectrum"
    )
    excluded = "political_spectrum"

    lines: list[str] = []
    lines.append(f"# BigFiveAdapter Validity Study (N={n_agents}, seed={seed})")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(
        "## Methodology\n\n"
        "A synthetic Big Five population (N agents) was sampled from "
        "Costa & McCrae adult norms (mean=0.50, std=0.17 per trait on [0,1]) "
        "with 6 literature-documented intercorrelation pairs: "
        + ", ".join(f"{a[:1].upper()}~{b[:1].upper()}={r:+.2f}"
                    for (a, b), r in DEFAULT_CORRELATIONS.items())
        + ". The same population was then run through four pipeline "
        "configurations — (BigFive adapter, Astrological adapter) x "
        "(calibration off, calibration on) — to compare distribution, "
        "pass-through accuracy, intercorrelation preservation, and "
        "butterfly-scenario sensitivity.",
    )
    lines.append("")
    lines.append(
        "Calibration uses **adapter-specific stats**: "
        "`config/trait_calibration_big_five.json` for the BigFive path and "
        "`config/trait_calibration_astrological.json` for the Astrological "
        "path. Each was generated from a 5K population matching the adapter "
        "(`scripts/build_calibration_stats.py --adapter=<type>`). This "
        "removes the cross-distribution distortion that affected an earlier "
        "shared-stats version of this study.",
    )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 1 — Population synthesis verification
    # -------------------------------------------------------------------
    lines.append("## Section 1 — Population synthesis verification\n")
    lines.append("Does the synthetic Big Five population match its target distribution?\n")
    lines.append("| trait | target mean | observed mean | target std | observed std |")
    lines.append("|-------|-------------|---------------|------------|--------------|")
    for t in BIG_FIVE:
        vals = [d[t] for d in bf_scores]
        m, s, _, _ = _moments(vals)
        lines.append(f"| {t} | 0.500 | {m:.3f} | 0.170 | {s:.3f} |")
    lines.append("")
    lines.append("Observed input correlations (should match targets within ±0.03):\n")
    lines.append("| pair | target r | observed r |")
    lines.append("|------|----------|------------|")
    for (a, b), expected in DEFAULT_CORRELATIONS.items():
        xs = [d[a] for d in bf_scores]
        ys = [d[b] for d in bf_scores]
        lines.append(f"| {a}~{b} | {expected:+.2f} | {_pearson(xs, ys):+.3f} |")
    lines.append("")

    # -------------------------------------------------------------------
    # Section 2 — Pass-through accuracy (BigFive 5)
    # -------------------------------------------------------------------
    lines.append("## Section 2 — Big Five pass-through accuracy (BigFive path)\n")
    lines.append(
        "Per-trait Pearson r between input OCEAN scores and output Big Five "
        f"values. Expect r >= {PASS_THROUGH_MIN} pre-cal (direct copy through "
        "adapter + CulturalModifier). Post-cal may drop slightly as calibration "
        "rescales toward the astrological reference mean.\n",
    )
    lines.append("| trait | cal OFF | cal ON |")
    lines.append("|-------|---------|--------|")
    for t in BIG_FIVE:
        input_vals = [d[t] for d in bf_scores]
        r_off = _pearson(input_vals, runs[("big_five", False)][t])
        r_on = _pearson(input_vals, runs[("big_five", True)][t])
        lines.append(f"| {t} | {r_off:+.3f} | {r_on:+.3f} |")
    lines.append("")

    # -------------------------------------------------------------------
    # Section 3 — Derived 13 traits
    # -------------------------------------------------------------------
    lines.append("## Section 3 — Derived traits (BigFive path, 13 literature-sourced)\n")
    low_conf = ("contrarian_tendency", "authority_compliance")
    lines.append(
        "Per-trait mean/std/skew/kurtosis. Two traits flagged as "
        "low-confidence by the derivation table: "
        + ", ".join(low_conf)
        + ".\n",
    )
    lines.append("### Cal OFF")
    lines.extend(_per_trait_table(
        derived_traits, runs[("big_five", False)], threshold=DERIVED_STD_MIN,
    ))
    lines.append("")
    lines.append("### Cal ON")
    lines.extend(_per_trait_table(
        derived_traits, runs[("big_five", True)], threshold=DERIVED_STD_MIN,
    ))
    lines.append("")

    # -------------------------------------------------------------------
    # Section 4 — Fallback + excluded traits
    # -------------------------------------------------------------------
    lines.append("## Section 4 — Fallback traits + excluded (BigFive path)\n")
    lines.append(
        "The 5 fallback traits are effectively disabled on the BigFive path — "
        "no published Big Five correlation found in literature, so they stay "
        "at 0.5 in cal OFF. With adapter-specific calibration stats, cal ON "
        "should keep the mean near 0.5 (since the stats source has the same "
        "0.5 mean) but stretch the std modestly. Saturation indicates the "
        "stretch factor was too aggressive for a near-zero source variance.\n",
    )
    lines.append("| trait | mean (cal OFF) | std (cal OFF) | mean (cal ON) | std (cal ON) | saturated (cal ON)? |")
    lines.append("|-------|----------------|---------------|---------------|--------------|--------------------|")
    for t in (*fallback_traits, excluded):
        off = runs[("big_five", False)][t]
        on = runs[("big_five", True)][t]
        m_off, s_off, _, _ = _moments(off)
        m_on, s_on, _, _ = _moments(on)
        sat = "yes" if (m_on < 0.05 or m_on > 0.95) else "no"
        lines.append(
            f"| {t} | {m_off:.3f} | {s_off:.3f} | {m_on:.3f} | {s_on:.3f} | {sat} |",
        )
    lines.append("")
    lines.append(
        f"Note: `{excluded}` is excluded by design across all adapters "
        "(REALM models temperament, not ideology).\n",
    )

    # -------------------------------------------------------------------
    # Section 5 — Big Five intercorrelation preservation
    # -------------------------------------------------------------------
    lines.append("## Section 5 — Big Five intercorrelation preservation (BigFive path)\n")
    lines.append(
        "Does the input OCEAN correlation structure survive the pipeline? "
        "Input is the synthetic sample; outputs are the BigFive path, "
        "calibration off and on.\n",
    )
    lines.append("| pair | target | input observed | output (cal OFF) | output (cal ON) |")
    lines.append("|------|--------|----------------|------------------|-----------------|")
    sign_preserved_off = 0
    sign_preserved_on = 0
    total = 0
    for (a, b), target in DEFAULT_CORRELATIONS.items():
        xs_in = [d[a] for d in bf_scores]
        ys_in = [d[b] for d in bf_scores]
        r_in = _pearson(xs_in, ys_in)
        r_off = _pearson(runs[("big_five", False)][a], runs[("big_five", False)][b])
        r_on = _pearson(runs[("big_five", True)][a], runs[("big_five", True)][b])
        if (r_off > 0) == (target > 0):
            sign_preserved_off += 1
        if (r_on > 0) == (target > 0):
            sign_preserved_on += 1
        total += 1
        lines.append(f"| {a}~{b} | {target:+.2f} | {r_in:+.3f} | {r_off:+.3f} | {r_on:+.3f} |")
    lines.append("")
    lines.append(
        f"Sign preservation: {sign_preserved_off}/{total} off, "
        f"{sign_preserved_on}/{total} on.\n",
    )

    # -------------------------------------------------------------------
    # Section 6 — Derived-trait structural intercorrelations
    # -------------------------------------------------------------------
    lines.append("## Section 6 — Derived-trait structural intercorrelations (BigFive path, cal OFF)\n")
    lines.append(
        "Two derived traits sharing the same dominant OCEAN driver should "
        "correlate in a predictable direction. Predicted sign = sign of "
        "coefficient_a * coefficient_b on the shared driver. Tolerance "
        "benchmark: observed |r| >= 0.10 with matching sign counts as "
        "'structure', otherwise 'noise-like'.\n",
    )
    lines.append("| trait_a | trait_b | shared driver | predicted sign | observed r | matches? |")
    lines.append("|---------|---------|---------------|----------------|------------|----------|")
    data = runs[("big_five", False)]
    structural_hits = 0
    for (a, b, drv, sign) in s_pairs:
        r = _pearson(data[a], data[b])
        matches = (r > 0) == (sign > 0) and abs(r) >= 0.10
        if matches:
            structural_hits += 1
        lines.append(
            f"| {a} | {b} | {drv[:1].upper()} | {'+' if sign > 0 else '-'} | "
            f"{r:+.3f} | {'yes' if matches else 'no'} |",
        )
    total_pairs = len(s_pairs)
    pair_frac = structural_hits / max(total_pairs, 1)
    lines.append("")
    lines.append(
        f"**Structural match rate: {structural_hits}/{total_pairs} = {pair_frac*100:.0f}%**\n",
    )
    # Mean |r| across all unique derived pairs (structure-vs-noise summary)
    all_pair_rs = []
    for i, ta in enumerate(derived_traits):
        for tb in derived_traits[i + 1:]:
            all_pair_rs.append(abs(_pearson(data[ta], data[tb])))
    mean_abs_r = statistics.mean(all_pair_rs) if all_pair_rs else 0.0
    lines.append(
        f"Mean |r| across all {len(all_pair_rs)} unique derived-trait pairs: "
        f"**{mean_abs_r:.3f}**.\n",
    )
    if mean_abs_r < 0.05:
        lines.append(
            "Interpretation: derived traits are effectively independent "
            "linear combinations of OCEAN — a known limitation. Real "
            "populations have tangled trait structure that this simple "
            "linear derivation cannot reproduce.\n",
        )
    else:
        lines.append(
            "Interpretation: derived traits show non-trivial coupling "
            "consistent with shared OCEAN drivers in the derivation table.\n",
        )

    # -------------------------------------------------------------------
    # Section 7 — Cross-path comparison
    # -------------------------------------------------------------------
    lines.append("## Section 7 — Cross-path comparison: BigFive vs Astrological\n")
    lines.append(
        "Mean trait std across all 24 traits under each pipeline configuration.\n",
    )
    lines.append("| configuration | mean trait std | traits >= 0.14 |")
    lines.append("|---------------|----------------|----------------|")
    lines.append(_mean_std_row("BigFive, cal OFF", runs[("big_five", False)]))
    lines.append(_mean_std_row("BigFive, cal ON", runs[("big_five", True)]))
    lines.append(_mean_std_row("Astrological, cal OFF", runs[("astrological", False)]))
    lines.append(_mean_std_row("Astrological, cal ON", runs[("astrological", True)]))
    lines.append("")

    # -------------------------------------------------------------------
    # Section 8 — Butterfly lift
    # -------------------------------------------------------------------
    lines.append("## Section 8 — Butterfly lift (tech-news scenario, n=150, 12 ticks, 3 branches)\n")
    lines.append(
        "Baseline vs scenario tech_share under each configuration. "
        "Scenario injects the identical 20-headline Apple AI device cascade "
        "at tick 0 (same payload as `scripts/demo_butterfly.py`).\n",
    )
    lines.append("| configuration | baseline | scenario | Δ (lift) | relative % |")
    lines.append("|---------------|----------|----------|----------|------------|")
    for (adapter_type, cal_state) in [
        ("big_five", False),
        ("big_five", True),
        ("astrological", False),
        ("astrological", True),
    ]:
        base, scn, lift = butterfly[(adapter_type, cal_state)]
        rel = (lift / base * 100) if base > 1e-9 else 0.0
        cal_label = "ON " if cal_state else "OFF"
        label = f"{adapter_type}, cal {cal_label}"
        lines.append(f"| {label} | {base:.3f} | {scn:.3f} | {lift:+.3f} | {rel:+.1f}% |")
    lines.append("")

    # -------------------------------------------------------------------
    # Section 9 — Honest limitations
    # -------------------------------------------------------------------
    lines.append("## Section 9 — Honest limitations\n")
    lines.append(
        f"**Fallback-5 disabled on BigFive path:** {', '.join(fallback_traits)} "
        "all stay at 0.5 on the BigFive path (cal OFF) because no published "
        "Big Five correlation was found for them. Under cal ON with "
        "adapter-specific stats, mean stays near 0.5 but std may saturate at "
        "tails when the stretch factor is large (e.g. spirituality, "
        "tradition_vs_progress where source std is ~0.01). See Section 4.\n",
    )
    lines.append(
        "**Low-confidence derivations:** contrarian_tendency and "
        "authority_compliance were flagged as low-confidence in the "
        "derivation table (weak Big Five literature support). Their "
        "Section 3 numbers should be read as design sketches rather than "
        "validated claims.\n",
    )
    lines.append(
        "**Calibrator now adapter-aware:** earlier sessions used a single "
        "`config/trait_calibration.json` built from an astrological run, "
        "applied to all adapters. As of 2026-04-24 the calibrator loads "
        "`config/trait_calibration_{adapter_type}.json` based on the active "
        "adapter, removing the cross-distribution distortion. Stats files "
        "must be regenerated when their underlying distribution changes "
        "(damping, derivation table, cultural blend, etc).\n",
    )
    lines.append(
        "**Narrow derived-trait variance:** Section 3 cal-OFF stds reveal "
        "that each derived trait's std is bounded by the OCEAN input std "
        "(~0.17) scaled by its max coefficient (typically 0.3-0.45). Without "
        "calibration, derived traits sit around std=0.05-0.08 — similar to "
        "the DemographicAdapter narrow-variance finding from 2026-04-24. "
        "A BlendedAdapter combining BigFive + per-agent noise (e.g. "
        "astrological residuals or questionnaire jitter) is flagged as "
        "future work.\n",
    )
    lines.append(
        "**Weak derived-trait intercorrelation structure** — see Section 6 "
        "match rate. Linear derivation from five independent OCEAN axes "
        "cannot reproduce the tangled structure of real human personality; "
        "richer mapping (cross-trait coupling or post-hoc correlation "
        "injection) is a roadmap item.\n",
    )

    # -------------------------------------------------------------------
    # Section 10 — Success criteria evaluation
    # -------------------------------------------------------------------
    lines.append("## Section 10 — Success criteria evaluation\n")
    stds_bf_on = [_moments(runs[("big_five", True)][n])[1]
                  for n in TraitVector.trait_names()]
    mean_std_bf_on = statistics.mean(stds_bf_on)
    criterion_1 = mean_std_bf_on >= TARGET_STD_MIN

    pass_through_min = min(
        _pearson([d[t] for d in bf_scores],
                 runs[("big_five", False)][t])
        for t in BIG_FIVE
    )
    criterion_2 = pass_through_min >= PASS_THROUGH_MIN

    criterion_3 = sign_preserved_off == total

    derived_off_stds = [
        _moments(runs[("big_five", False)][t])[1] for t in derived_traits
    ]
    derived_on_stds = [
        _moments(runs[("big_five", True)][t])[1] for t in derived_traits
    ]
    criterion_4_off = all(s > DERIVED_STD_MIN for s in derived_off_stds)
    criterion_4_on = all(s > DERIVED_STD_MIN for s in derived_on_stds)

    _, _, lift_bf_off = butterfly[("big_five", False)]
    _, _, lift_bf_on = butterfly[("big_five", True)]
    criterion_5 = lift_bf_off > 0 or lift_bf_on > 0

    criterion_6 = pair_frac >= 0.50

    def _mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines.append("| # | criterion | measurement | result |")
    lines.append("|---|-----------|-------------|--------|")
    lines.append(
        f"| 1 | BigFive mean trait std >= 0.14 (cal ON) | {mean_std_bf_on:.3f} | "
        f"{_mark(criterion_1)} |",
    )
    lines.append(
        f"| 2 | Big Five input<->output Pearson r >= 0.99 (cal OFF) | "
        f"min = {pass_through_min:.3f} | {_mark(criterion_2)} |",
    )
    lines.append(
        f"| 3 | Input correlation signs preserved in output (cal OFF) | "
        f"{sign_preserved_off}/{total} | {_mark(criterion_3)} |",
    )
    lines.append(
        f"| 4a | Derived 13 traits all std > 0.05 (cal OFF) | "
        f"min = {min(derived_off_stds):.3f} | {_mark(criterion_4_off)} |",
    )
    lines.append(
        f"| 4b | Derived 13 traits all std > 0.05 (cal ON) | "
        f"min = {min(derived_on_stds):.3f} | {_mark(criterion_4_on)} |",
    )
    lines.append(
        f"| 5 | Butterfly lift positive on BigFive path | "
        f"cal OFF = {lift_bf_off:+.3f}, cal ON = {lift_bf_on:+.3f} | "
        f"{_mark(criterion_5)} |",
    )
    lines.append(
        f"| 6 | Derived structural pairs match >= 50% | "
        f"{structural_hits}/{total_pairs} = {pair_frac*100:.0f}% | "
        f"{_mark(criterion_6)} |",
    )
    lines.append("")

    lines.append("## Summary\n")
    passed = sum([
        criterion_1, criterion_2, criterion_3,
        criterion_4_off, criterion_4_on, criterion_5, criterion_6,
    ])
    lines.append(f"**{passed}/7 criteria passed.**\n")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def _parse_argv(argv: list[str]) -> tuple[int, int]:
    n = 10000
    seed = 42
    for arg in argv[1:]:
        if arg.startswith("--seed="):
            seed = int(arg.split("=", 1)[1])
        elif arg.isdigit():
            n = int(arg)
    return n, seed


def main(argv: list[str] | None = None) -> int:
    setup_logging(level="WARNING")
    argv = argv if argv is not None else sys.argv
    n, seed = _parse_argv(argv)

    print(f"BigFiveAdapter validity study: N={n}, seed={seed}")
    print("Output: outputs/bf_validity_study.md\n")

    # 1. Build shared population (demographic profiles + BF scores)
    print(f"[1/4] Building BF population (N={n})...")
    t0 = time.perf_counter()
    profiles = build_bf_profiles(n, seed=seed)
    bf_scores = [dict(p.big_five_scores or {}) for p in profiles]
    print(f"      done in {time.perf_counter() - t0:.1f}s")

    # 2. Run 4 pipeline configurations
    runs: dict[tuple[str, bool], dict[str, list[float]]] = {}
    for (adapter_type, cal_state) in [
        ("big_five", False),
        ("big_five", True),
        ("astrological", False),
        ("astrological", True),
    ]:
        t0 = time.perf_counter()
        print(f"[2/4] Pipeline: {adapter_type}, cal={'ON ' if cal_state else 'OFF'}...")
        runs[(adapter_type, cal_state)] = run_pipeline(
            profiles, adapter_type, cal_state,
        )
        print(f"      done in {time.perf_counter() - t0:.1f}s")

    # 3. Butterfly comparison (4 combos)
    butterfly: dict[tuple[str, bool], tuple[float, float, float]] = {}
    for (adapter_type, cal_state) in [
        ("big_five", False),
        ("big_five", True),
        ("astrological", False),
        ("astrological", True),
    ]:
        t0 = time.perf_counter()
        print(f"[3/4] Butterfly: {adapter_type}, cal={'ON ' if cal_state else 'OFF'}...")
        butterfly[(adapter_type, cal_state)] = run_butterfly(
            adapter_type, cal_state, master_seed=seed,
        )
        base, scn, lift = butterfly[(adapter_type, cal_state)]
        print(f"      baseline={base:.3f}, scenario={scn:.3f}, lift={lift:+.3f} "
              f"({time.perf_counter() - t0:.1f}s)")

    # 4. Write report
    print("[4/4] Writing report...")
    report = build_report(n, seed, bf_scores, runs, butterfly)
    out_path = ROOT / "outputs" / "bf_validity_study.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"      wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
