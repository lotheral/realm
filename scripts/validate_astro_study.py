"""20-figure astrological validity study — compute metrics + Markdown report.

Loads outputs/celebrity_astro_profiles.json (produced by
generate_celebrity_astro_profiles.py), compares AstrologicalAdapter outputs
to biographical expected profiles, and writes:

    outputs/astro_validity_study.md
    outputs/astro_validity_metrics.json

Metrics:
    1. Directional Accuracy (DA) — per-trait, overall. Pass: overall > 0.60
    2. Magnitude Correlation (Pearson + Spearman) — per-trait, overall. Pass: r > 0.20
    3. Extreme Trait Detection — DA on {expected>=0.80 or <=0.20}. Pass: > 0.55
    4. Confidence-Weighted DA — DA on high-confidence traits only. Pass: > 0.60
    5. Confidence Coverage Ratio — diagnostic only. Warn if overall low > 0.40

Usage:
    python scripts/validate_astro_study.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASTRO_PROFILES = ROOT / "outputs" / "celebrity_astro_profiles.json"
REPORT_PATH = ROOT / "outputs" / "astro_validity_study.md"
METRICS_PATH = ROOT / "outputs" / "astro_validity_metrics.json"

NEUTRAL = 0.5
EXTREME_HI = 0.80
EXTREME_LO = 0.20

PASS_DA_OVERALL = 0.60
PASS_CORR_OVERALL = 0.20
PASS_EXTREME = 0.55
PASS_CW_DA = 0.60
WARN_LOW_CONFIDENCE_RATIO = 0.40

FALLBACK_TRAITS = {
    "herd_susceptibility", "fomo_susceptibility",
    "individualism", "tradition_vs_progress", "spirituality",
}
EXCLUDED_TRAITS = {"political_spectrum"}


# ---- Math helpers ------------------------------------------------------

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


def _rank(values: list[float]) -> list[float]:
    """Average-rank with tie handling — stable input to Spearman."""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_rank(xs), _rank(ys))


# ---- Directional accuracy ---------------------------------------------

def _directional_hit(expected: float, actual: float) -> bool | None:
    """Return True/False if both have a directional claim, None if expected is
    exactly neutral (no claim)."""
    if abs(expected - NEUTRAL) < 1e-9:
        return None
    if expected > NEUTRAL:
        return actual > NEUTRAL
    return actual < NEUTRAL


# ---- Extraction --------------------------------------------------------

def _extract_pairs(
    figures: dict, validated_traits: list[str],
    confidence_filter: set[str] | None = None,
    extreme_only: bool = False,
) -> tuple[list[float], list[float], list[tuple[str, str, bool | None]]]:
    """Flatten (expected, actual) pairs across figures + traits.

    Returns: (expected_list, actual_list, triples[(fid, trait, hit_flag)]).
    Skips figures with status != 'ok'.
    """
    expected: list[float] = []
    actual: list[float] = []
    triples: list[tuple[str, str, bool | None]] = []

    for fid, fig in figures.items():
        if fig.get("status") != "ok":
            continue
        astro = fig["astro_only"]
        exp_block = fig["expected"]
        for trait in validated_traits:
            if trait not in exp_block or trait not in astro:
                continue
            entry = exp_block[trait]
            if confidence_filter and entry.get("confidence") not in confidence_filter:
                continue
            ev = float(entry["value"])
            if extreme_only and not (ev >= EXTREME_HI or ev <= EXTREME_LO):
                continue
            av = float(astro[trait])
            hit = _directional_hit(ev, av)
            expected.append(ev)
            actual.append(av)
            triples.append((fid, trait, hit))
    return expected, actual, triples


def _da_from_triples(triples: list[tuple[str, str, bool | None]]) -> tuple[float, int, int]:
    """Directional accuracy from triples. Skips None (neutral expected)."""
    classified = [t for _, _, t in triples if t is not None]
    n = len(classified)
    if n == 0:
        return 0.0, 0, 0
    hits = sum(1 for h in classified if h)
    return hits / n, hits, n


# ---- Per-trait and per-person breakdowns ------------------------------

def _per_trait_stats(
    figures: dict, validated_traits: list[str],
) -> list[dict]:
    out = []
    for trait in validated_traits:
        exp_vals: list[float] = []
        act_vals: list[float] = []
        classified: list[bool] = []
        for _, fig in figures.items():
            if fig.get("status") != "ok":
                continue
            if trait not in fig["astro_only"] or trait not in fig["expected"]:
                continue
            ev = float(fig["expected"][trait]["value"])
            av = float(fig["astro_only"][trait])
            exp_vals.append(ev)
            act_vals.append(av)
            hit = _directional_hit(ev, av)
            if hit is not None:
                classified.append(hit)
        n_classified = len(classified)
        da = sum(classified) / n_classified if n_classified else float("nan")
        out.append({
            "trait": trait,
            "n_figures": len(exp_vals),
            "n_classified": n_classified,
            "da": da,
            "pearson": _pearson(exp_vals, act_vals) if len(exp_vals) >= 2 else 0.0,
            "spearman": _spearman(exp_vals, act_vals) if len(exp_vals) >= 2 else 0.0,
            "expected_mean": statistics.mean(exp_vals) if exp_vals else 0.0,
            "actual_mean": statistics.mean(act_vals) if act_vals else 0.0,
            "actual_std": statistics.stdev(act_vals) if len(act_vals) >= 2 else 0.0,
            "is_fallback": trait in FALLBACK_TRAITS,
        })
    return out


def _per_person_stats(
    figures: dict, validated_traits: list[str],
) -> list[dict]:
    out = []
    for fid, fig in figures.items():
        if fig.get("status") != "ok":
            continue
        exp_vals: list[float] = []
        act_vals: list[float] = []
        classified: list[bool] = []
        high_classified: list[bool] = []
        conf_count = {"high": 0, "medium": 0, "low": 0}
        for trait in validated_traits:
            if trait not in fig["astro_only"] or trait not in fig["expected"]:
                continue
            entry = fig["expected"][trait]
            ev = float(entry["value"])
            av = float(fig["astro_only"][trait])
            exp_vals.append(ev)
            act_vals.append(av)
            hit = _directional_hit(ev, av)
            if hit is not None:
                classified.append(hit)
                if entry.get("confidence") == "high":
                    high_classified.append(hit)
            c = entry.get("confidence", "unknown")
            if c in conf_count:
                conf_count[c] += 1
        n_cls = len(classified)
        n_high = len(high_classified)
        out.append({
            "figure_id": fid,
            "name": fig.get("name", fid),
            "era": fig.get("era"),
            "occupation": fig.get("occupation"),
            "sun_sign": fig["chart_summary"]["sun_sign"],
            "asc_sign": fig["chart_summary"]["asc_sign"],
            "n_classified": n_cls,
            "da": sum(classified) / n_cls if n_cls else float("nan"),
            "cw_da": sum(high_classified) / n_high if n_high else float("nan"),
            "pearson": _pearson(exp_vals, act_vals) if len(exp_vals) >= 2 else 0.0,
            "spearman": _spearman(exp_vals, act_vals) if len(exp_vals) >= 2 else 0.0,
            "confidence_counts": conf_count,
            "low_ratio": conf_count["low"] / sum(conf_count.values()) if sum(conf_count.values()) else 0.0,
        })
    return out


# ---- Confidence coverage ---------------------------------------------

def _confidence_coverage(figures: dict, validated_traits: list[str]) -> dict:
    overall = {"high": 0, "medium": 0, "low": 0}
    per_figure = {}
    for fid, fig in figures.items():
        if fig.get("status") != "ok":
            continue
        pf = {"high": 0, "medium": 0, "low": 0}
        for trait in validated_traits:
            if trait not in fig["expected"]:
                continue
            c = fig["expected"][trait].get("confidence", "unknown")
            if c in overall:
                overall[c] += 1
                pf[c] += 1
        per_figure[fid] = pf
    total = sum(overall.values())
    return {
        "overall_counts": overall,
        "overall_ratios": {k: v / total for k, v in overall.items()} if total else {},
        "per_figure": per_figure,
        "warn_low_heavy": (overall["low"] / total > WARN_LOW_CONFIDENCE_RATIO) if total else False,
        "figures_low_heavy": [
            fid for fid, pf in per_figure.items()
            if sum(pf.values()) and pf["low"] / sum(pf.values()) > 0.60
        ],
    }


# ---- Report rendering -------------------------------------------------

def _pct(x: float) -> str:
    if math.isnan(x):
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt(x: float, decimals: int = 3) -> str:
    if math.isnan(x):
        return "n/a"
    return f"{x:.{decimals}f}"


def _pass_fail(ok: bool) -> str:
    return "✅ PASS" if ok else "❌ FAIL"


def build_report(data: dict, metrics: dict) -> str:
    lines: list[str] = []
    fig_count_total = len(data["figures"])
    fig_ok = sum(1 for f in data["figures"].values() if f.get("status") == "ok")
    fig_failed = [fid for fid, f in data["figures"].items() if f.get("status") != "ok"]

    m = metrics
    exec_table = [
        ("Directional Accuracy (overall, N=all)", m["da"]["overall"], PASS_DA_OVERALL),
        ("Magnitude Correlation (Pearson, flat)", m["correlation"]["overall_pearson"], PASS_CORR_OVERALL),
        ("Magnitude Correlation (Spearman, flat)", m["correlation"]["overall_spearman"], PASS_CORR_OVERALL),
        ("Extreme-Trait Detection", m["extreme"]["da"], PASS_EXTREME),
        ("Confidence-Weighted DA (high only)", m["cw_da"]["da"], PASS_CW_DA),
    ]

    # --- Section 1 ---
    lines.append("# Astrological Validity Study (N=20)")
    lines.append("")
    lines.append(f"**Engine:** {data['engine_backend']} · **Embedder:** {data['embedder_mode']} · "
                 f"**Cohort:** {fig_ok}/{fig_count_total} figures computed")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append("| Metric | Value | Target | Status |")
    lines.append("|---|---:|---:|---|")
    for label, value, target in exec_table:
        ok = value >= target
        lines.append(f"| {label} | {_fmt(value)} | ≥ {target:.2f} | {_pass_fail(ok)} |")
    lines.append("")
    lines.append(f"*Validated traits:* {len(m['validated_traits'])} of 24 "
                 f"(political_spectrum excluded — not populated by astrological mapping; "
                 f"see `data/astro/planet_trait_map.json:_excluded_by_design`).")
    lines.append("")
    cc = m["confidence_coverage"]
    cc_r = cc["overall_ratios"]
    lines.append(f"*Confidence coverage (CCR):* high {_pct(cc_r.get('high', 0))} · "
                 f"medium {_pct(cc_r.get('medium', 0))} · low {_pct(cc_r.get('low', 0))}.")
    if cc["warn_low_heavy"]:
        lines.append("> ⚠ Low-confidence entries exceed 40% — weight the Confidence-Weighted DA over overall DA.")
    if cc["figures_low_heavy"]:
        lines.append(f"> ⚠ Figures with >60% low-confidence traits: {cc['figures_low_heavy']}")
    lines.append("")

    # --- Section 2 ---
    lines.append("## 2. Methodology")
    lines.append("")
    lines.append("**Figure selection.** 20 figures chosen for zodiac/element/modality diversity, "
                 "occupational spread (science, art, politics, business, sport, activism, monarchy), "
                 "and a mix of living + historical subjects. Birth data sourced from Astro-Databank "
                 "with rating tiers AA/A/B/C noted per figure in `data/validation/celebrity_profiles.json`.")
    lines.append("")
    lines.append("**Expected profile authoring.** Each figure's expected trait vector was authored "
                 "from biographical knowledge (major biographies, interviews, documented behavior). "
                 "**No astrological reasoning was used** for expected values — circular-reasoning guard. "
                 "Confidence tiers: `high` = explicit, multiply-sourced biographical attestation; "
                 "`medium` = reasonable single-source inference; `low` = speculative or historically uncertain.")
    lines.append("")
    lines.append("**Substitutions from user's initial list** (preserved archetypal signatures):")
    lines.append("- Cleopatra (69 BC) → Nelson Mandela (1918): Python datetime lower bound year ≥ 1 rules out BC dates.")
    lines.append("- Napoleon (1769) → Theodore Roosevelt (1858): Swiss Ephemeris asteroid file `seas_12.se1` "
                 "(1200–1800 CE) is not installed in this environment; only `seas_18.se1` (1800+ CE) is bundled.")
    lines.append("- Leonardo da Vinci (1452) → Thomas Edison (1847): same pre-1800 ephemeris coverage limit.")
    if fig_failed:
        lines.append(f"- Unexpected failures during chart computation: {fig_failed}")
    lines.append("")
    lines.append("**Metrics.** DA (directional accuracy) = share of trait×figure pairs where "
                 "`expected` and `actual` fall on the same side of 0.5. Traits with expected exactly 0.5 "
                 "are neutral and skipped from DA counts. Pearson/Spearman computed on raw magnitudes. "
                 "Extreme-trait detection restricts to pairs with expected ≥ 0.80 or ≤ 0.20.")
    lines.append("")

    # --- Section 3 ---
    lines.append("## 3. Figure Cohort")
    lines.append("")
    lines.append("| # | Figure | Era | Occupation | Sun | ASC | Birth rating |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, fid in enumerate(data["figures"], start=1):
        fig = data["figures"][fid]
        if fig.get("status") != "ok":
            lines.append(f"| {i} | {fig.get('name', fid)} | — | — | — | — | **{fig.get('status', '?')}** |")
            continue
        cs = fig["chart_summary"]
        lines.append(f"| {i} | {fig['name']} | {fig.get('era','')} | {fig.get('occupation','')} | "
                     f"{cs['sun_sign']} | {cs['asc_sign']} | {fig.get('astro_databank_rating','?')} |")
    lines.append("")

    # --- Section 4 ---
    lines.append("## 4. Per-Person Results")
    lines.append("")
    lines.append("| Figure | DA | CW-DA (high) | Pearson r | Spearman ρ | conf (H/M/L) |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for p in m["per_person"]:
        c = p["confidence_counts"]
        lines.append(f"| {p['name']} | {_fmt(p['da'], 3)} | {_fmt(p['cw_da'], 3)} | "
                     f"{_fmt(p['pearson'], 3)} | {_fmt(p['spearman'], 3)} | "
                     f"{c['high']}/{c['medium']}/{c['low']} |")
    lines.append("")

    # Top/Bottom 3 figures by DA
    ranked = sorted(
        [p for p in m["per_person"] if not math.isnan(p["da"])],
        key=lambda p: p["da"], reverse=True,
    )
    lines.append("**Top-3 figures by DA:** " + ", ".join(
        f"{p['name']} ({p['da']:.2f})" for p in ranked[:3]
    ))
    lines.append("")
    lines.append("**Bottom-3 figures by DA:** " + ", ".join(
        f"{p['name']} ({p['da']:.2f})" for p in ranked[-3:]
    ))
    lines.append("")

    # --- Section 5 ---
    lines.append("## 5. Per-Trait Analysis")
    lines.append("")
    lines.append("*Traits marked `(f)` are fallback traits — default to 0.5 in several adapters "
                 "and carry the weakest astrological signal.*")
    lines.append("")
    lines.append("| Trait | DA | Pearson | Spearman | Exp μ | Act μ | Act σ |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    trait_sorted = sorted(m["per_trait"], key=lambda t: t["da"] if not math.isnan(t["da"]) else -1, reverse=True)
    for t in trait_sorted:
        tag = " (f)" if t["is_fallback"] else ""
        lines.append(f"| {t['trait']}{tag} | {_fmt(t['da'], 3)} | {_fmt(t['pearson'], 3)} | "
                     f"{_fmt(t['spearman'], 3)} | {_fmt(t['expected_mean'], 2)} | "
                     f"{_fmt(t['actual_mean'], 2)} | {_fmt(t['actual_std'], 2)} |")
    lines.append("")

    # Best/worst mapped traits
    non_nan = [t for t in m["per_trait"] if not math.isnan(t["da"])]
    by_da_desc = sorted(non_nan, key=lambda t: t["da"], reverse=True)
    lines.append("**Best-mapped traits (top-3 by DA):** " + ", ".join(
        f"{t['trait']} ({t['da']:.2f})" for t in by_da_desc[:3]
    ))
    lines.append("")
    lines.append("**Worst-mapped traits (bottom-3 by DA):** " + ", ".join(
        f"{t['trait']} ({t['da']:.2f})" for t in by_da_desc[-3:]
    ))
    lines.append("")

    # Fallback traits stats
    fb = [t for t in m["per_trait"] if t["is_fallback"]]
    non_fb = [t for t in m["per_trait"] if not t["is_fallback"]]

    def _mean_or_nan(seq: list[float]) -> float:
        vals = [v for v in seq if not math.isnan(v)]
        return statistics.mean(vals) if vals else float("nan")

    fb_da = _mean_or_nan([t["da"] for t in fb])
    non_fb_da = _mean_or_nan([t["da"] for t in non_fb])
    lines.append(f"*Fallback-trait mean DA:* {_fmt(fb_da, 3)} · *non-fallback mean DA:* {_fmt(non_fb_da, 3)}.")
    lines.append("")

    # --- Section 6 ---
    lines.append("## 6. Astrological Factor Diagnostics")
    lines.append("")
    lines.append("Grouping per-person DA by Sun-sign element (fire/earth/air/water):")
    lines.append("")

    fire = {"Aries", "Leo", "Sagittarius"}
    earth = {"Taurus", "Virgo", "Capricorn"}
    air = {"Gemini", "Libra", "Aquarius"}
    water = {"Cancer", "Scorpio", "Pisces"}
    element_for = dict.fromkeys(fire, "fire")
    element_for.update(dict.fromkeys(earth, "earth"))
    element_for.update(dict.fromkeys(air, "air"))
    element_for.update(dict.fromkeys(water, "water"))

    by_elem: dict[str, list[float]] = {"fire": [], "earth": [], "air": [], "water": []}
    for p in m["per_person"]:
        e = element_for.get(p["sun_sign"])
        if e and not math.isnan(p["da"]):
            by_elem[e].append(p["da"])

    lines.append("| Element | Figures | Mean DA | Mean Pearson |")
    lines.append("|---|---:|---:|---:|")
    for elem in ("fire", "earth", "air", "water"):
        das = by_elem[elem]
        pears = [p["pearson"] for p in m["per_person"]
                 if element_for.get(p["sun_sign"]) == elem and not math.isnan(p["pearson"])]
        mean_da = statistics.mean(das) if das else float("nan")
        mean_p = statistics.mean(pears) if pears else float("nan")
        lines.append(f"| {elem} | {len(das)} | {_fmt(mean_da, 3)} | {_fmt(mean_p, 3)} |")
    lines.append("")

    # --- Section 7 ---
    lines.append("## 7. Limitations")
    lines.append("")
    lines.append("- **Expected-profile subjectivity.** Claude-authored expected values reflect training-data "
                 "biographical knowledge without live web verification. Low-confidence entries surface this honestly. "
                 "Interpret the Confidence-Weighted DA as the more trustworthy metric.")
    lines.append("- **Small N.** Twenty figures is adequate for directional-accuracy signal but will not detect "
                 "subtle systematic biases in individual trait mappings.")
    lines.append("- **Survivor/notability bias.** Famous figures over-represent extreme personalities; neutral or "
                 "moderate trait values are under-sampled.")
    lines.append("- **Uncertain birth times.** Cases marked `c` or `unknown` rating have noon-or-approximate defaults, "
                 "systematically biasing Ascendant and house placements.")
    lines.append("- **Political_spectrum excluded.** Astrological mapping intentionally does not populate this trait "
                 "(scope decision — REALM models temperament, not ideology).")
    lines.append("- **Ephemeris coverage.** Pre-1800 CE birth dates cannot be computed with the installed "
                 "`seas_18.se1` asteroid file. Three figures in the original cohort (Cleopatra, Napoleon, Leonardo) "
                 "were substituted.")
    lines.append("- **Substitution politics.** Mandela is not a pure Cleopatra substitute — archetype differs. "
                 "Readers should view those three substitutions as additional figures, not direct replacements.")
    lines.append("")

    # --- Section 8 ---
    lines.append("## 8. Recommendations")
    lines.append("")
    mapping_candidates = [t["trait"] for t in by_da_desc[-3:] if not t["is_fallback"]]
    if mapping_candidates:
        lines.append(f"Traits with lowest DA that are **not** fallback traits: `{', '.join(mapping_candidates)}`. "
                     f"These are candidates for review of their mapping in `data/astro/planet_trait_map.json` "
                     f"and `data/astro/aspect_weights.json` — the mapping may systematically miss directional signal.")
    else:
        lines.append("No non-fallback trait fell below `DA=0.50`. Mapping table changes are not indicated by this run.")
    lines.append("")
    lines.append("Future work:")
    lines.append("- Expand cohort to N=50+ with stratified sampling on Sun-sign and occupation for sub-group analysis.")
    lines.append("- Install `seas_12.se1` Swiss Ephemeris file to restore pre-1800 coverage (Napoleon, Leonardo).")
    lines.append("- Cross-validate with a blind panel: have 2–3 human raters author expected profiles without Claude's, "
                 "compute inter-rater agreement, and use majority-agreed trait×figure pairs as the gold set.")
    lines.append("- Run the same figures through **BlendedAdapter** with real BigFive scores (if ever available) "
                 "to quantify astrological signal contribution.")
    lines.append("")

    # --- Section 9 ---
    lines.append("## 9. Success Criteria Evaluation")
    lines.append("")
    lines.append("| Criterion | Target | Observed | Status |")
    lines.append("|---|---:|---:|---|")
    criteria = [
        ("Directional Accuracy > 0.60", PASS_DA_OVERALL, m["da"]["overall"]),
        ("Magnitude Correlation (Pearson) > 0.20", PASS_CORR_OVERALL, m["correlation"]["overall_pearson"]),
        ("Extreme-Trait Detection > 0.55", PASS_EXTREME, m["extreme"]["da"]),
        ("Confidence-Weighted DA > 0.60", PASS_CW_DA, m["cw_da"]["da"]),
    ]
    for label, target, observed in criteria:
        lines.append(f"| {label} | ≥ {target:.2f} | {_fmt(observed)} | {_pass_fail(observed >= target)} |")
    lines.append("")
    lines.append("_Research-study principle: a FAIL here is still a valid finding — this is the first "
                 "benchmark of REALM's astrological directional accuracy. Honest reporting > artificial pass._")
    lines.append("")

    return "\n".join(lines) + "\n"


# ---- Main -------------------------------------------------------------

def compute_metrics(data: dict) -> dict:
    figures = data["figures"]
    validated_traits = [t for t in data["trait_scope"]["all_traits"] if t not in EXCLUDED_TRAITS]

    # Overall DA + correlation (across all trait×figure pairs)
    all_exp, all_act, all_triples = _extract_pairs(figures, validated_traits)
    da_overall, hits_overall, n_overall = _da_from_triples(all_triples)
    pearson_overall = _pearson(all_exp, all_act)
    spearman_overall = _spearman(all_exp, all_act)

    # Confidence-weighted (high only)
    _, _, high_triples = _extract_pairs(figures, validated_traits, confidence_filter={"high"})
    da_high, hits_high, n_high = _da_from_triples(high_triples)

    # Extreme detection
    _, _, extreme_triples = _extract_pairs(figures, validated_traits, extreme_only=True)
    da_extreme, hits_extreme, n_extreme = _da_from_triples(extreme_triples)

    per_trait = _per_trait_stats(figures, validated_traits)
    per_person = _per_person_stats(figures, validated_traits)
    cc = _confidence_coverage(figures, validated_traits)

    return {
        "validated_traits": validated_traits,
        "da": {
            "overall": da_overall,
            "hits": hits_overall,
            "n_classified": n_overall,
        },
        "cw_da": {
            "da": da_high,
            "hits": hits_high,
            "n_classified": n_high,
        },
        "extreme": {
            "da": da_extreme,
            "hits": hits_extreme,
            "n_classified": n_extreme,
        },
        "correlation": {
            "overall_pearson": pearson_overall,
            "overall_spearman": spearman_overall,
            "n_pairs": len(all_exp),
        },
        "per_trait": per_trait,
        "per_person": per_person,
        "confidence_coverage": cc,
        "thresholds": {
            "da_overall": PASS_DA_OVERALL,
            "correlation_overall": PASS_CORR_OVERALL,
            "extreme": PASS_EXTREME,
            "cw_da": PASS_CW_DA,
            "warn_low_ratio": WARN_LOW_CONFIDENCE_RATIO,
        },
    }


def main() -> int:
    with ASTRO_PROFILES.open(encoding="utf-8") as f:
        data = json.load(f)

    metrics = compute_metrics(data)

    with METRICS_PATH.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    report = build_report(data, metrics)
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(report)

    # Print concise summary to stdout
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"Wrote {METRICS_PATH.relative_to(ROOT)}")
    print()
    print(f"Overall DA:           {metrics['da']['overall']:.3f} "
          f"({metrics['da']['hits']}/{metrics['da']['n_classified']}) "
          f"-- target >= {PASS_DA_OVERALL:.2f}")
    print(f"Pearson r (overall):  {metrics['correlation']['overall_pearson']:.3f} "
          f"-- target >= {PASS_CORR_OVERALL:.2f}")
    print(f"Spearman rho (overall): {metrics['correlation']['overall_spearman']:.3f}")
    print(f"Extreme DA:           {metrics['extreme']['da']:.3f} "
          f"({metrics['extreme']['hits']}/{metrics['extreme']['n_classified']}) "
          f"-- target >= {PASS_EXTREME:.2f}")
    print(f"CW-DA (high conf):    {metrics['cw_da']['da']:.3f} "
          f"({metrics['cw_da']['hits']}/{metrics['cw_da']['n_classified']}) "
          f"-- target >= {PASS_CW_DA:.2f}")
    cc = metrics["confidence_coverage"]["overall_ratios"]
    print(f"CCR: high {cc.get('high', 0)*100:.1f}% | "
          f"medium {cc.get('medium', 0)*100:.1f}% | "
          f"low {cc.get('low', 0)*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
