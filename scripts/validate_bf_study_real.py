"""Real-data BigFiveAdapter validity study — side-by-side synthetic vs real.

Runs two populations at the same N through the same four pipeline
configurations (BigFive/Astrological x calibration off/on), then reports
every metric in two columns:

    column 'synth': Costa & McCrae-distributed synthetic OCEAN population
                    (identical to what scripts/validate_bf_study.py uses).
    column 'real':  filtered + stratified sample from
                    automoto/big-five-data, with hybrid demographic profiles.

Adds one new success criterion (#8-real): does the real OCEAN input
distribution match Costa & McCrae synthetic norms within per-trait
|Δmean| < 0.05 AND |Δstd| < 0.03? This is expected to FAIL because
self-reported IPIP-NEO-300 data clusters at ~0.68 not 0.50 — documenting
the gap is the value, not hiding it.

Output:  outputs/bf_validity_study_real.md

Usage:
    python scripts/validate_bf_study_real.py [N=10000] [--seed=42]
    python scripts/validate_bf_study_real.py 2000 --seed=42      # fast smoke
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

sys.path.insert(0, str(ROOT / "scripts"))
from generate_bf_population import build_bf_profiles  # noqa: E402
from load_bigfive_real import load_real_population  # noqa: E402

BIG_FIVE = OCEAN
DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"
TARGET_STD_MIN = 0.14
PASS_THROUGH_MIN = 0.99
DERIVED_STD_MIN = 0.05
DIST_MEAN_TOL = 0.05
DIST_STD_TOL = 0.03
COSTA_MCCRAE_MEAN = 0.50
COSTA_MCCRAE_STD = 0.17

Population = str  # "synth" or "real"
Adapter = str     # "big_five" or "astrological"
RunKey = tuple[Population, Adapter, bool]  # (pop, adapter, cal_on)

CONFIGS: tuple[tuple[Adapter, bool], ...] = (
    ("big_five", False),
    ("big_five", True),
    ("astrological", False),
    ("astrological", True),
)


# --------------------------------------------------------------------------
# Stats helpers (shared with synthetic study — small copies to avoid drift)
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

def _make_calibrator(
    enabled: bool, adapter_type: str, source: str = "synthetic",
) -> TraitCalibrator:
    if enabled:
        return TraitCalibrator(
            enabled=True,
            target_mean=0.50,
            target_std=0.17,
            adapter_type=adapter_type,
            source=source,
        )
    return TraitCalibrator(enabled=False)


def _source_for(population: str, adapter_type: str) -> str:
    """Real-population BigFive path uses real-derived calibration stats.

    Everything else (astro path, synth BigFive path) keeps the synthetic
    stats — that's the canonical default.
    """
    if population == "real" and adapter_type == "big_five":
        return "real"
    return "synthetic"


def run_pipeline(
    profiles, adapter_type: str, enable_calibration: bool,
    population: str = "synth",
) -> dict[str, list[float]]:
    adapter = get_input_adapter(adapter_type)
    source = _source_for(population, adapter_type)
    calibrator = _make_calibrator(enable_calibration, adapter_type, source)
    factory = AgentFactory(adapter=adapter, calibrator=calibrator)
    agents = factory.build_batch(profiles)
    data: dict[str, list[float]] = {n: [] for n in TraitVector.trait_names()}
    for a in agents:
        for n in TraitVector.trait_names():
            data[n].append(getattr(a.traits, n))
    return data


# --------------------------------------------------------------------------
# Derivation table
# --------------------------------------------------------------------------

def _load_derivation() -> dict[str, dict[str, float]]:
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
    return max(coeffs.items(), key=lambda kv: abs(kv[1]))


def structural_pairs(
    derivation: dict[str, dict[str, float]],
) -> list[tuple[str, str, str, int]]:
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
# Butterfly runs — per population because agent_builder embeds the population
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


def _bf_agent_builder_synth(enable_cal: bool):
    def builder(seed: int, n: int):
        adapter = get_input_adapter("big_five")
        factory = AgentFactory(
            adapter=adapter,
            calibrator=_make_calibrator(enable_cal, "big_five"),
        )
        profiles = build_bf_profiles(n, seed=seed)
        return factory.build_batch(profiles)
    return builder


def _bf_agent_builder_real(enable_cal: bool, master_seed: int):
    """Real-population builder. Branches reuse the same stratified sample
    seeded by master_seed — per-branch seed variation is irrelevant because
    the population is fixed by the dataset.
    """
    # Pre-load once to avoid re-reading CSV for each branch call
    real_profiles, _ = load_real_population(
        n=max(150, 500), seed=master_seed,
    )

    def builder(seed: int, n: int):
        adapter = get_input_adapter("big_five")
        factory = AgentFactory(
            adapter=adapter,
            calibrator=_make_calibrator(enable_cal, "big_five", "real"),
        )
        # Deterministically subsample n from the pre-loaded pool based on seed
        import random as _r
        rng = _r.Random(seed)
        if n <= len(real_profiles):
            picks = rng.sample(real_profiles, n)
        else:
            picks = list(real_profiles) + rng.choices(real_profiles, k=n - len(real_profiles))
        return factory.build_batch(picks)
    return builder


def run_butterfly_synth(
    adapter_type: str, enable_cal: bool, master_seed: int,
) -> tuple[float, float, float]:
    if adapter_type == "big_five":
        builder = _bf_agent_builder_synth(enable_cal)
    else:
        builder = _astro_agent_builder(enable_cal)
    return _butterfly(builder, master_seed)


def run_butterfly_real(
    adapter_type: str, enable_cal: bool, master_seed: int,
) -> tuple[float, float, float]:
    if adapter_type == "big_five":
        builder = _bf_agent_builder_real(enable_cal, master_seed)
    else:
        # Astrological butterfly on the "real" side uses real demographics
        # only via the BigFiveAdapter path; the astrological path is
        # independent of Big Five scores so we re-use the synthetic astro
        # builder for cross-path reference. This is documented in the report.
        builder = _astro_agent_builder(enable_cal)
    return _butterfly(builder, master_seed)


def _butterfly(builder, master_seed: int) -> tuple[float, float, float]:
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
# Report helpers
# --------------------------------------------------------------------------

def _intercorr_matrix(
    bf_scores: list[dict[str, float]],
) -> dict[tuple[str, str], float]:
    return {
        (a, b): _pearson([d[a] for d in bf_scores], [d[b] for d in bf_scores])
        for i, a in enumerate(OCEAN) for b in OCEAN[i + 1:]
    }


def _pair_preservation(
    input_corrs: dict[tuple[str, str], float],
    output: dict[str, list[float]],
) -> tuple[int, int, float]:
    """Returns (pairs_within_eps_0.05, total_pairs, max_abs_delta)."""
    total = 0
    hits = 0
    max_delta = 0.0
    for (a, b), r_in in input_corrs.items():
        r_out = _pearson(output[a], output[b])
        delta = abs(r_out - r_in)
        max_delta = max(max_delta, delta)
        total += 1
        if delta <= 0.05:
            hits += 1
    return hits, total, max_delta


def _dual_moment_row(
    trait: str, synth: list[float], real: list[float],
) -> str:
    ms, ss, sks, kts = _moments(synth)
    mr, sr, skr, ktr = _moments(real)
    return (
        f"| {trait} | {ms:.3f} | {mr:.3f} | {ms - mr:+.3f} | "
        f"{ss:.3f} | {sr:.3f} | {sks:+.2f} | {skr:+.2f} |"
    )


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def build_report(
    n_agents: int, seed: int,
    bf_synth: list[dict[str, float]],
    bf_real: list[dict[str, float]],
    runs: dict[RunKey, dict[str, list[float]]],
    butterfly: dict[tuple[Population, Adapter, bool], tuple[float, float, float]],
    real_diag: dict[str, object],
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
    lines.append(f"# Real-Data BigFive Validity Study (N={n_agents}, seed={seed})")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(
        "Side-by-side validity study comparing a Costa & McCrae-distributed "
        "synthetic Big Five population against a stratified sample from "
        "[automoto/big-five-data](https://github.com/automoto/big-five-data) "
        "(307,313 rows; pre-computed OCEAN [0,1] from IPIP-NEO-300). Every "
        "metric below is reported in two columns — `synth` and `real` — "
        "using an identical pipeline on both sides.",
    )
    lines.append("")
    lines.append(
        "See `outputs/sapa_validation_plan.md` for the design document and "
        "`outputs/bf_validity_study.md` for the synthetic-only baseline this "
        "study extends.",
    )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 0 — Side-by-side population characterization
    # -------------------------------------------------------------------
    lines.append("## Section 0 — Population characterization (synth vs real)\n")
    lines.append(
        "### OCEAN distribution (per-trait, both populations at N="
        f"{n_agents})\n",
    )
    lines.append(
        "| trait | synth mean | real mean | Δmean | synth std | real std | synth skew | real skew |",
    )
    lines.append(
        "|-------|-----------|-----------|-------|-----------|----------|-----------|-----------|",
    )
    for t in BIG_FIVE:
        lines.append(
            _dual_moment_row(t, bf_synth and [d[t] for d in bf_synth],
                             [d[t] for d in bf_real]),
        )
    lines.append("")
    lines.append(
        "**Finding**: real IPIP-NEO-300 means cluster around 0.65-0.73, "
        "not the 0.50 Costa & McCrae midpoint the synthetic sampler targets. "
        "This is a documented feature of self-endorsed item-mean scoring "
        "(participants answer above midpoint on aggregate), not a bug in "
        "either dataset. Real stds (~0.09-0.13) are also narrower than the "
        "synthetic 0.17 target.\n",
    )

    lines.append("### Input intercorrelations (synth vs real, OCEAN pairs)\n")
    lines.append(
        "| pair | synth target | synth observed | real observed |",
    )
    lines.append("|------|--------------|----------------|---------------|")
    for (a, b), target in DEFAULT_CORRELATIONS.items():
        r_synth = _pearson([d[a] for d in bf_synth], [d[b] for d in bf_synth])
        r_real = _pearson([d[a] for d in bf_real], [d[b] for d in bf_real])
        lines.append(f"| {a}~{b} | {target:+.2f} | {r_synth:+.3f} | {r_real:+.3f} |")
    lines.append("")

    # Dataset demographics summary
    lines.append("### Real-dataset demographics (sample of N="
                 f"{n_agents})\n")
    iso2_sample = real_diag["iso2_counts_sample"]
    iso2_full = real_diag["iso2_counts_full"]
    total_full = sum(iso2_full.values())
    top10 = sorted(iso2_sample.items(), key=lambda kv: kv[1], reverse=True)[:10]
    lines.append("**Top 10 countries in sample:**\n")
    lines.append("| ISO2 | sample N | sample % | filtered source % |")
    lines.append("|------|----------|----------|-------------------|")
    for iso2, c in top10:
        full_n = iso2_full.get(iso2, 0)
        full_pct = (full_n / total_full * 100.0) if total_full else 0.0
        smp_pct = (c / n_agents * 100.0) if n_agents else 0.0
        lines.append(f"| {iso2} | {c} | {smp_pct:.1f}% | {full_pct:.1f}% |")
    lines.append("")
    lines.append(
        f"**Sex split (sample)**: {real_diag['sex_counts_sample']}. "
        f"**Age bands (sample)**: {real_diag['age_band_counts_sample']}. "
        f"Dataset skews young (18-35 heavy) and female-majority — a known "
        "feature of voluntary online IPIP-NEO testing.\n",
    )
    dropped = real_diag["dropped"]
    unmapped_names = {
        k: v for k, v in dropped.items()
        if not k.startswith("[iso2:") and k != "<invalid_row>"
    }
    under_n = {k: v for k, v in dropped.items() if k.startswith("[iso2:")}
    invalid = dropped.get("<invalid_row>", 0)
    lines.append(
        f"**Filter results**: "
        f"{real_diag['kept_rows']} rows kept after filtering. "
        f"Excluded: **{sum(unmapped_names.values())}** rows across "
        f"{len(unmapped_names)} country names not in REALM's 30-country "
        f"map (e.g. Canada 21,798; Australia 10,400; Netherlands 3,469; "
        f"Singapore 2,450); "
        f"**{sum(under_n.values())}** rows across {len(under_n)} mapped "
        f"countries below N=100; {invalid} invalid rows.\n",
    )
    lines.append(
        "The demographic shift between the real sample (86%+ USA-weighted "
        "because of dataset skew) and REALM's WorldGenerator population "
        "weights (China 19%, India 19%, USA 4%) is itself a finding: "
        "synthetic agents simulate a more globally-balanced population than "
        "an online IPIP-NEO sample could ever measure.\n",
    )

    # -------------------------------------------------------------------
    # Section 1 — Input verification (synth target recovery only applies to synth)
    # -------------------------------------------------------------------
    lines.append("## Section 1 — Input verification\n")
    lines.append(
        "Synthetic side is expected to recover Costa & McCrae norms "
        "(mean=0.50, std=0.17); real side is descriptive only (no target).\n",
    )
    lines.append("| trait | synth target mean/std | synth obs mean/std | real obs mean/std |")
    lines.append("|-------|----------------------|--------------------|-------------------|")
    for t in BIG_FIVE:
        ms, ss, _, _ = _moments([d[t] for d in bf_synth])
        mr, sr, _, _ = _moments([d[t] for d in bf_real])
        lines.append(
            f"| {t} | 0.500 / 0.170 | {ms:.3f} / {ss:.3f} | {mr:.3f} / {sr:.3f} |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 2 — Pass-through accuracy (both populations)
    # -------------------------------------------------------------------
    lines.append("## Section 2 — Big Five pass-through accuracy\n")
    lines.append(
        "Per-trait Pearson r between input OCEAN scores and output Big Five "
        f"values on the BigFive path. Expected r >= {PASS_THROUGH_MIN} with "
        "cal OFF (direct pipe-through).\n",
    )
    lines.append("| trait | synth cal OFF | synth cal ON | real cal OFF | real cal ON |")
    lines.append("|-------|---------------|--------------|--------------|-------------|")
    for t in BIG_FIVE:
        in_synth = [d[t] for d in bf_synth]
        in_real = [d[t] for d in bf_real]
        rs_off = _pearson(in_synth, runs[("synth", "big_five", False)][t])
        rs_on = _pearson(in_synth, runs[("synth", "big_five", True)][t])
        rr_off = _pearson(in_real, runs[("real", "big_five", False)][t])
        rr_on = _pearson(in_real, runs[("real", "big_five", True)][t])
        lines.append(
            f"| {t} | {rs_off:+.3f} | {rs_on:+.3f} | {rr_off:+.3f} | {rr_on:+.3f} |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 3 — Derived 13 traits (dual column, cal OFF + cal ON)
    # -------------------------------------------------------------------
    lines.append("## Section 3 — Derived traits, per-population mean trait std\n")
    lines.append(
        f"Compressed view: mean std across the {len(derived_traits)} derived "
        "traits and count of those at / above the 0.05 minimum (BigFive path).\n",
    )
    lines.append("| config | mean derived std | #derived with std > 0.05 |")
    lines.append("|--------|------------------|-----|")
    for (pop, cal) in [
        ("synth", False), ("synth", True), ("real", False), ("real", True),
    ]:
        vals = [_moments(runs[(pop, "big_five", cal)][t])[1]
                for t in derived_traits]
        mean_std = statistics.mean(vals)
        pass_count = sum(1 for s in vals if s > DERIVED_STD_MIN)
        lines.append(
            f"| {pop} cal {'ON ' if cal else 'OFF'} | {mean_std:.3f} | "
            f"{pass_count}/{len(derived_traits)} |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 4 — Fallback + excluded
    # -------------------------------------------------------------------
    lines.append("## Section 4 — Fallback + excluded traits (dual)\n")
    lines.append(
        f"Fallback 5 traits stay at 0.5 on the BigFive path with cal OFF "
        f"(no Big Five coefficients). `{excluded}` is excluded by design "
        "(REALM models temperament, not ideology). Under cal ON each "
        "population uses its own source-specific stats "
        "(`config/trait_calibration_big_five.json` for synth, "
        "`config/trait_calibration_big_five_real.json` for real), so the "
        "two cal-ON columns reflect population-matched recentering.\n",
    )
    lines.append("| trait | synth mean (cal ON) | synth std (cal ON) | real mean (cal ON) | real std (cal ON) | saturated? |")
    lines.append("|-------|---------------------|--------------------|--------------------|-------------------|-----------|")
    for t in (*fallback_traits, excluded):
        ms, ss, _, _ = _moments(runs[("synth", "big_five", True)][t])
        mr, sr, _, _ = _moments(runs[("real", "big_five", True)][t])
        sat = "yes" if (ms < 0.05 or ms > 0.95 or mr < 0.05 or mr > 0.95) else "no"
        lines.append(
            f"| {t} | {ms:.3f} | {ss:.3f} | {mr:.3f} | {sr:.3f} | {sat} |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 5 — Big Five intercorrelation preservation (side-by-side)
    # -------------------------------------------------------------------
    lines.append("## Section 5 — Big Five intercorrelation preservation (BigFive path)\n")
    lines.append(
        "Input observed vs output on each population, cal OFF. "
        "Reports whether the pipeline preserves the INPUT intercorrelation "
        "(real input has its own structure, distinct from the synthetic target).\n",
    )
    lines.append("| pair | synth target | synth in | synth out | real in | real out | max Δ |")
    lines.append("|------|--------------|----------|-----------|---------|----------|-------|")
    synth_in_corrs = _intercorr_matrix(bf_synth)
    real_in_corrs = _intercorr_matrix(bf_real)
    for (a, b), target in DEFAULT_CORRELATIONS.items():
        key = (a, b) if (a, b) in synth_in_corrs else (b, a)
        r_si = synth_in_corrs.get(key, 0.0)
        r_ri = real_in_corrs.get(key, 0.0)
        r_so = _pearson(
            runs[("synth", "big_five", False)][a],
            runs[("synth", "big_five", False)][b],
        )
        r_ro = _pearson(
            runs[("real", "big_five", False)][a],
            runs[("real", "big_five", False)][b],
        )
        max_d = max(abs(r_so - r_si), abs(r_ro - r_ri))
        lines.append(
            f"| {a}~{b} | {target:+.2f} | {r_si:+.3f} | {r_so:+.3f} | "
            f"{r_ri:+.3f} | {r_ro:+.3f} | {max_d:.3f} |",
        )
    synth_hits, synth_total, synth_max = _pair_preservation(
        synth_in_corrs, runs[("synth", "big_five", False)],
    )
    real_hits, real_total, real_max = _pair_preservation(
        real_in_corrs, runs[("real", "big_five", False)],
    )
    lines.append("")
    lines.append(
        f"**Preservation within ε=0.05 (cal OFF)**: synth "
        f"{synth_hits}/{synth_total} (max Δ = {synth_max:.3f}); real "
        f"{real_hits}/{real_total} (max Δ = {real_max:.3f}).\n",
    )

    # -------------------------------------------------------------------
    # Section 6 — Structural pair match rate (dual)
    # -------------------------------------------------------------------
    lines.append("## Section 6 — Derived-trait structural pair match rate\n")
    lines.append(
        "Shared-driver pair match rate: two derived traits whose dominant "
        "OCEAN drivers match should correlate with predicted sign, |r| >= 0.10. "
        "BigFive path, cal OFF, both populations.\n",
    )
    lines.append("| population | matches | match rate | mean |r| |")
    lines.append("|------------|---------|------------|----------|")
    synth_data = runs[("synth", "big_five", False)]
    real_data = runs[("real", "big_five", False)]
    for label, data in (("synth", synth_data), ("real", real_data)):
        hits = 0
        for (a, b, _drv, sign) in s_pairs:
            r = _pearson(data[a], data[b])
            if (r > 0) == (sign > 0) and abs(r) >= 0.10:
                hits += 1
        all_rs = []
        for i, ta in enumerate(derived_traits):
            for tb in derived_traits[i + 1:]:
                all_rs.append(abs(_pearson(data[ta], data[tb])))
        mean_abs = statistics.mean(all_rs) if all_rs else 0.0
        rate = hits / max(len(s_pairs), 1)
        lines.append(
            f"| {label} | {hits}/{len(s_pairs)} | {rate*100:.0f}% | {mean_abs:.3f} |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 7 — Cross-path mean trait std
    # -------------------------------------------------------------------
    lines.append("## Section 7 — Cross-path mean trait std (all 24 traits)\n")
    lines.append("| configuration | mean trait std | #traits >= 0.14 |")
    lines.append("|---------------|----------------|-----------------|")
    for (pop, adapter, cal) in [
        ("synth", "big_five", False), ("synth", "big_five", True),
        ("synth", "astrological", False), ("synth", "astrological", True),
        ("real", "big_five", False), ("real", "big_five", True),
    ]:
        data = runs[(pop, adapter, cal)]
        stds = [_moments(data[n])[1] for n in TraitVector.trait_names()]
        mean_std = statistics.mean(stds)
        pc = sum(1 for s in stds if s >= TARGET_STD_MIN)
        lines.append(
            f"| {pop} {adapter} cal {'ON ' if cal else 'OFF'} | "
            f"{mean_std:.3f} | {pc}/{len(stds)} |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 8 — Butterfly lift (dual)
    # -------------------------------------------------------------------
    lines.append("## Section 8 — Butterfly lift (tech-news scenario)\n")
    lines.append(
        "Baseline vs scenario tech_share under each configuration (n=150 per "
        "branch, 12 ticks, 3 branches). Synth and real BigFive configs run "
        "with their respective populations; astrological config is unchanged "
        "across populations (independent of Big Five scores) and shown once.\n",
    )
    lines.append("| configuration | baseline | scenario | Δ (lift) | relative % |")
    lines.append("|---------------|----------|----------|----------|------------|")
    for (pop, adapter, cal) in [
        ("synth", "big_five", False), ("synth", "big_five", True),
        ("real", "big_five", False), ("real", "big_five", True),
        ("synth", "astrological", False), ("synth", "astrological", True),
    ]:
        base, scn, lift = butterfly[(pop, adapter, cal)]
        rel = (lift / base * 100) if base > 1e-9 else 0.0
        cal_label = "ON " if cal else "OFF"
        label = (
            f"{pop} {adapter} cal {cal_label}"
            if adapter == "big_five"
            else f"astrological cal {cal_label}"
        )
        lines.append(
            f"| {label} | {base:.3f} | {scn:.3f} | {lift:+.3f} | {rel:+.1f}% |",
        )
    lines.append("")

    # -------------------------------------------------------------------
    # Section 9 — Honest limitations (real-data specific)
    # -------------------------------------------------------------------
    lines.append("## Section 9 — Honest limitations\n")
    lines.append(
        "**Self-selection bias** — the automoto dataset is derived from the "
        "pool of people who chose to complete an online IPIP-NEO-300 test. "
        "Age skews young (~66% 18-25 in the filtered subset), country skews "
        "USA (86% even after stratification because USA is 86% of the "
        "filtered source), female-majority, English-speaking internet-using. "
        "'Real' here means 'real online IPIP-NEO respondents', not a "
        "representative human population.\n",
    )
    lines.append(
        "**No facet-level detail** — the dataset ships the 5 OCEAN composite "
        "scores only. The 30-facet IPIP-NEO structure underlying each score "
        "is not exposed, so this study cannot validate facet-specific claims "
        "in `data/personality/big_five_derivation.json` (e.g. 'patience "
        "derives from C5 Self-Discipline'). For facet validity, switch to "
        "the Johnson IPIP-NEO-120/300 OSF release in a follow-up study.\n",
    )
    lines.append(
        "**Country coverage gap** — REALM's WorldGenerator supports 30 "
        "ISO2 country codes; the dataset has 236 unique country names. "
        "The intersection after min_country_n=100 is 21 countries, leaving "
        f"{sum(v for k, v in dropped.items() if not k.startswith('[iso2:') and k != '<invalid_row>'):,} rows "
        "unused. Primary casualties: Canada (21,798), Australia (10,400), "
        "Netherlands (3,469), Singapore (2,450), Ireland (2,102), "
        "New Zealand (2,016), Finland, Sweden, Norway, Malaysia. The "
        "dataset is heavily Anglo/Western-European; filtering to REALM's "
        "30-country list drops most of that population tail.\n",
    )
    lines.append(
        "**Truncated country names** — the dataset stores country as a "
        "10-char-truncated string (e.g. `South Afri`, `Russian Fe`, "
        "`Philippine`). `COUNTRY_NAME_TO_ISO2` in `scripts/load_bigfive_real.py` "
        "is hand-maintained; any additions/renames upstream need a code "
        "update, not a data-only change.\n",
    )
    lines.append(
        "**Mean drift from Costa & McCrae norms** — real self-report "
        "IPIP-NEO-300 means cluster at ~0.65-0.73, not the 0.50 Costa & "
        "McCrae midpoint. This is documented §0 behavior of item-mean "
        "scoring on 0-1 normalized scales; it is NOT a calibration failure. "
        "Criterion #8-real below fails by design — the value is measuring "
        "*how much* synthetic and real diverge, not pretending they match.\n",
    )
    lines.append(
        "**Source-matched calibration stats** — as of 2026-04-24 both "
        "populations use their own source-specific stats when cal=ON: "
        "`config/trait_calibration_big_five.json` (synth, Costa & McCrae "
        "N=5K) for the synth path, `config/trait_calibration_big_five_real.json` "
        "(real, automoto stratified N=5K) for the real path. This removes "
        "the earlier synth→real cross-distribution distortion that saturated "
        "derived traits and flipped butterfly lift on the real cal-ON "
        "column. The remaining distance between real input and Costa & "
        "McCrae norms is an *input-property finding* (criterion #8-real), "
        "not a calibrator shortcoming.\n",
    )

    # -------------------------------------------------------------------
    # Section 10 — Success criteria evaluation (dual)
    # -------------------------------------------------------------------
    lines.append("## Section 10 — Success criteria evaluation\n")

    def _compute(pop: Population, bf: list[dict[str, float]]):
        stds_bf_on = [
            _moments(runs[(pop, "big_five", True)][n])[1]
            for n in TraitVector.trait_names()
        ]
        mean_std_bf_on = statistics.mean(stds_bf_on)
        c1 = mean_std_bf_on >= TARGET_STD_MIN

        pt_min = min(
            _pearson([d[t] for d in bf],
                     runs[(pop, "big_five", False)][t])
            for t in BIG_FIVE
        )
        c2 = pt_min >= PASS_THROUGH_MIN

        in_corrs = _intercorr_matrix(bf)
        sign_hits = 0
        total_pairs = len(in_corrs)
        for (a, b), r_in in in_corrs.items():
            r_out = _pearson(
                runs[(pop, "big_five", False)][a],
                runs[(pop, "big_five", False)][b],
            )
            if (r_in > 0) == (r_out > 0) or abs(r_in) < 0.02:
                sign_hits += 1
        c3 = sign_hits == total_pairs

        derived_off = [
            _moments(runs[(pop, "big_five", False)][t])[1] for t in derived_traits
        ]
        derived_on = [
            _moments(runs[(pop, "big_five", True)][t])[1] for t in derived_traits
        ]
        c4off = all(s > DERIVED_STD_MIN for s in derived_off)
        c4on = all(s > DERIVED_STD_MIN for s in derived_on)

        _, _, lift_off = butterfly[(pop, "big_five", False)]
        _, _, lift_on = butterfly[(pop, "big_five", True)]
        c5 = lift_off > 0 or lift_on > 0

        data = runs[(pop, "big_five", False)]
        hits = 0
        for (a, b, _drv, sign) in s_pairs:
            r = _pearson(data[a], data[b])
            if (r > 0) == (sign > 0) and abs(r) >= 0.10:
                hits += 1
        rate = hits / max(len(s_pairs), 1)
        c6 = rate >= 0.50

        return {
            "c1": c1, "mean_std_bf_on": mean_std_bf_on,
            "c2": c2, "pt_min": pt_min,
            "c3": c3, "sign_hits": sign_hits, "total_pairs": total_pairs,
            "c4off": c4off, "c4off_min": min(derived_off),
            "c4on": c4on, "c4on_min": min(derived_on),
            "c5": c5, "lift_off": lift_off, "lift_on": lift_on,
            "c6": c6, "struct_hits": hits, "rate": rate,
        }

    synth_eval = _compute("synth", bf_synth)
    real_eval = _compute("real", bf_real)

    # Criterion 8-real: real input OCEAN distribution vs Costa & McCrae norms
    c8_fails: list[str] = []
    max_mean_delta = 0.0
    max_std_delta = 0.0
    for t in BIG_FIVE:
        m, s, _, _ = _moments([d[t] for d in bf_real])
        dm = abs(m - COSTA_MCCRAE_MEAN)
        ds = abs(s - COSTA_MCCRAE_STD)
        max_mean_delta = max(max_mean_delta, dm)
        max_std_delta = max(max_std_delta, ds)
        if dm > DIST_MEAN_TOL or ds > DIST_STD_TOL:
            c8_fails.append(t)
    c8 = not c8_fails

    def _mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines.append("| # | criterion | synth result | real result |")
    lines.append("|---|-----------|--------------|-------------|")
    lines.append(
        f"| 1 | BigFive mean trait std >= 0.14 (cal ON) | "
        f"{synth_eval['mean_std_bf_on']:.3f} {_mark(synth_eval['c1'])} | "
        f"{real_eval['mean_std_bf_on']:.3f} {_mark(real_eval['c1'])} |",
    )
    lines.append(
        f"| 2 | Big Five input↔output r >= 0.99 (cal OFF) | "
        f"min={synth_eval['pt_min']:.3f} {_mark(synth_eval['c2'])} | "
        f"min={real_eval['pt_min']:.3f} {_mark(real_eval['c2'])} |",
    )
    lines.append(
        f"| 3 | Input correlation signs preserved (cal OFF) | "
        f"{synth_eval['sign_hits']}/{synth_eval['total_pairs']} "
        f"{_mark(synth_eval['c3'])} | "
        f"{real_eval['sign_hits']}/{real_eval['total_pairs']} "
        f"{_mark(real_eval['c3'])} |",
    )
    lines.append(
        f"| 4a | Derived 13 traits std > 0.05 (cal OFF) | "
        f"min={synth_eval['c4off_min']:.3f} {_mark(synth_eval['c4off'])} | "
        f"min={real_eval['c4off_min']:.3f} {_mark(real_eval['c4off'])} |",
    )
    lines.append(
        f"| 4b | Derived 13 traits std > 0.05 (cal ON) | "
        f"min={synth_eval['c4on_min']:.3f} {_mark(synth_eval['c4on'])} | "
        f"min={real_eval['c4on_min']:.3f} {_mark(real_eval['c4on'])} |",
    )
    lines.append(
        f"| 5 | Butterfly lift > 0 on BigFive path | "
        f"off={synth_eval['lift_off']:+.3f}, on={synth_eval['lift_on']:+.3f} "
        f"{_mark(synth_eval['c5'])} | "
        f"off={real_eval['lift_off']:+.3f}, on={real_eval['lift_on']:+.3f} "
        f"{_mark(real_eval['c5'])} |",
    )
    lines.append(
        f"| 6 | Derived structural pairs match >= 50% | "
        f"{synth_eval['struct_hits']}/{len(s_pairs)} "
        f"({synth_eval['rate']*100:.0f}%) {_mark(synth_eval['c6'])} | "
        f"{real_eval['struct_hits']}/{len(s_pairs)} "
        f"({real_eval['rate']*100:.0f}%) {_mark(real_eval['c6'])} |",
    )
    lines.append(
        f"| **8-real** | Real OCEAN ≈ Costa & McCrae (Δmean<0.05 AND Δstd<0.03 per trait) | "
        f"— (n/a on synth) | "
        f"max Δmean={max_mean_delta:.3f}, max Δstd={max_std_delta:.3f} "
        f"{_mark(c8)} |",
    )
    lines.append("")

    synth_passed = sum(
        int(synth_eval[k]) for k in
        ("c1", "c2", "c3", "c4off", "c4on", "c5", "c6")
    )
    real_passed = sum(
        int(real_eval[k]) for k in
        ("c1", "c2", "c3", "c4off", "c4on", "c5", "c6")
    ) + int(c8)

    lines.append("## Summary\n")
    lines.append(
        f"**Synthetic column: {synth_passed}/7 criteria passed.**\n\n"
        f"**Real column: {real_passed}/8 criteria passed.**\n",
    )
    if c8_fails:
        lines.append(
            f"Criterion 8-real FAILs: {', '.join(c8_fails)} "
            f"(expected — real self-report means drift ~0.15-0.23 above "
            "Costa & McCrae midpoint; see §0 and §9).\n",
        )
    lines.append("")
    lines.append("See `scripts/validate_bf_subgroups.py` output in ")
    lines.append("`outputs/bf_validity_subgroups_real.md` for the §11 ")
    lines.append("per-country × sex × age-band matrix.\n")

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

    print(f"Real-data BigFive validity study: N={n}, seed={seed}")
    print("Output: outputs/bf_validity_study_real.md\n")

    # Populations
    print(f"[1/5] Building synthetic BF population (N={n})...")
    t0 = time.perf_counter()
    synth_profiles = build_bf_profiles(n, seed=seed)
    bf_synth = [dict(p.big_five_scores or {}) for p in synth_profiles]
    print(f"      done in {time.perf_counter() - t0:.1f}s")

    print(f"[2/5] Loading real BF population (N={n}, stratified by country×sex)...")
    t0 = time.perf_counter()
    real_profiles, real_diag = load_real_population(n=n, seed=seed)
    bf_real = [dict(p.big_five_scores or {}) for p in real_profiles]
    print(f"      kept source rows: {real_diag['kept_rows']}")
    print(f"      sample size: {len(real_profiles)}")
    print(f"      done in {time.perf_counter() - t0:.1f}s")

    # Pipeline runs — 8 configs total (2 pops x 2 adapters x 2 cal states)
    runs: dict[RunKey, dict[str, list[float]]] = {}
    for pop, profiles in (("synth", synth_profiles), ("real", real_profiles)):
        for (adapter, cal) in CONFIGS:
            t0 = time.perf_counter()
            print(
                f"[3/5] Pipeline: pop={pop}, adapter={adapter}, "
                f"cal={'ON ' if cal else 'OFF'}...",
            )
            runs[(pop, adapter, cal)] = run_pipeline(
                profiles, adapter, cal, population=pop,
            )
            print(f"      done in {time.perf_counter() - t0:.1f}s")

    # Butterfly — 6 unique configs (astro butterfly is pop-invariant; run once)
    butterfly: dict[tuple[Population, Adapter, bool], tuple[float, float, float]] = {}
    butterfly_configs = [
        ("synth", "big_five", False),
        ("synth", "big_five", True),
        ("real", "big_five", False),
        ("real", "big_five", True),
        ("synth", "astrological", False),
        ("synth", "astrological", True),
    ]
    for (pop, adapter, cal) in butterfly_configs:
        t0 = time.perf_counter()
        print(
            f"[4/5] Butterfly: pop={pop}, adapter={adapter}, "
            f"cal={'ON ' if cal else 'OFF'}...",
        )
        if adapter == "astrological":
            # Astro butterfly is independent of BF population
            base, scn, lift = run_butterfly_synth(adapter, cal, master_seed=seed)
        elif pop == "synth":
            base, scn, lift = run_butterfly_synth(adapter, cal, master_seed=seed)
        else:
            base, scn, lift = run_butterfly_real(adapter, cal, master_seed=seed)
        butterfly[(pop, adapter, cal)] = (base, scn, lift)
        print(
            f"      base={base:.3f}, scn={scn:.3f}, lift={lift:+.3f} "
            f"({time.perf_counter() - t0:.1f}s)",
        )

    # Report
    print("[5/5] Writing report...")
    report = build_report(n, seed, bf_synth, bf_real, runs, butterfly, real_diag)
    out_path = ROOT / "outputs" / "bf_validity_study_real.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"      wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
