"""Audit BigFive-derivation facet citations against Johnson IPIP-NEO-120.

Deliverable A of Sprint 5 WP3. For each trait in `data/personality/
big_five_derivation.json` whose `source` string cites a specific facet
(e.g. "C5 Self-Discipline", "NEO A6 Tender-Mindedness", "E.Assertiveness"),
this script:

1. Parses the source string to extract cited facet codes (e.g. "C5").
2. For each cited facet, against the Johnson sample, checks:
   - (a) Variance: std(facet) >= 0.05 — is the facet discriminative?
   - (b) Domain loading: Pearson r(facet, parent_domain) >= 0.50 — is the
         facet actually loading on its claimed parent?
   - (c) Direction: sign of REALM's coefficient on the parent domain agrees
         with sign of corr(facet, REALM_synthetic_trait_value) — does the
         trait move in the expected direction with the cited facet?

Writes `outputs/facet_validation_report.md` with per-trait PASS/FAIL/WARN.
"""

from __future__ import annotations

import contextlib as _ctx
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.personality.adapters import BigFiveAdapter  # noqa: E402
from realm.personality.validation.facet_scorer import (  # noqa: E402
    DOMAINS,
    FACET_CODES,
    FACET_TO_DOMAIN,
    load_ipip120,
    score_dataset,
)

DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"
REPORT_PATH = ROOT / "outputs" / "facet_validation_report.md"

DOMAIN_TO_KEY: dict[str, str] = {
    "O": "openness",
    "C": "conscientiousness",
    "E": "extraversion",
    "A": "agreeableness",
    "N": "neuroticism",
}

# Canonical facet name → facet code. Covers Costa-McCrae NEO-PI-R terms and
# BFAS aspect names commonly cited in the derivation table.
FACET_NAME_TO_CODE: dict[str, str] = {
    # N
    "anxiety": "N1", "anger": "N2", "depression": "N3",
    "self-consciousness": "N4", "immoderation": "N5",
    "impulsiveness": "N5", "vulnerability": "N6",
    # E
    "friendliness": "E1", "gregariousness": "E2", "assertiveness": "E3",
    "activity level": "E4", "excitement-seeking": "E5", "cheerfulness": "E6",
    "positive-emotion": "E6", "positive emotion": "E6", "warmth": "E1",
    "enthusiasm": "E6",
    # O
    "imagination": "O1", "artistic interests": "O2", "emotionality": "O3",
    "adventurousness": "O4", "intellect": "O5", "ideas": "O5",
    "liberalism": "O6", "values": "O6", "aesthetics": "O2",
    # A
    "trust": "A1", "morality": "A2", "altruism": "A3",
    "cooperation": "A4", "compliance": "A4", "modesty": "A5",
    "sympathy": "A6", "tender-mindedness": "A6",
    "politeness": "A4",
    # C
    "self-efficacy": "C1", "orderliness": "C2", "dutifulness": "C3",
    "achievement-striving": "C4", "self-discipline": "C5",
    "deliberation": "C6", "cautiousness": "C6",
}


def extract_cited_facets(source: str) -> list[str]:
    """Extract facet codes (e.g. 'C5') cited in a source string.

    Looks for two patterns:
      1. Literal facet codes like "C5", "N1", "O5" with word boundaries
      2. Facet names from `FACET_NAME_TO_CODE` (case-insensitive)
    Returns the set as a stable list.
    """
    found: set[str] = set()

    # Pattern 1: direct facet codes
    for m in re.finditer(r"\b([OCEAN])([1-6])\b", source):
        found.add(f"{m.group(1)}{m.group(2)}")

    # Pattern 2: facet names (case-insensitive, longest-first)
    src_lower = source.lower()
    for name in sorted(FACET_NAME_TO_CODE, key=len, reverse=True):
        if name in src_lower:
            found.add(FACET_NAME_TO_CODE[name])

    return sorted(found)


def _pearson_vec(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson r between two 1D float arrays (finite values only)."""
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return 0.0
    sx, sy = x.std(), y.std()
    if sx < 1e-9 or sy < 1e-9:
        return 0.0
    return float(((x - x.mean()) * (y - y.mean())).mean() / (sx * sy))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    # Parse --max-rows (for quick testing) and --seed
    max_rows = None
    for arg in argv[1:]:
        if arg.startswith("--max-rows="):
            max_rows = int(arg.split("=", 1)[1])

    print(f"Loading IPIP120.dat (max_rows={max_rows or 'all'})...")
    t0 = time.perf_counter()
    records = load_ipip120(max_rows=max_rows)
    print(f"  loaded {len(records):,} records in {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    facets, domains, kept = score_dataset(records)
    N = len(kept)  # noqa: N806 - math convention for sample size
    print(f"  scored {N:,} records (dropped "
          f"{len(records) - N:,} for too many missing) in "
          f"{time.perf_counter() - t0:.1f}s")

    facet_idx = {f: i for i, f in enumerate(FACET_CODES)}

    # Load derivation
    deriv = json.loads(DERIVATION_PATH.read_text(encoding="utf-8"))
    traits = deriv.get("traits", {})

    # Run BigFiveAdapter on Johnson-derived OCEAN to get REALM synthetic
    # trait values per respondent. Inputs come from the 5 domain scores.
    adapter = BigFiveAdapter()
    realm_trait_values: dict[str, np.ndarray] = {
        t: np.zeros(N, dtype=np.float32) for t in traits
    }
    for i in range(N):
        scores = {DOMAIN_TO_KEY[d]: float(domains[i, di])
                  for di, d in enumerate(DOMAINS)}
        tv = adapter.build(scores)
        for t in traits:
            if hasattr(tv, t):
                realm_trait_values[t][i] = getattr(tv, t)

    # Per-trait audit
    results: list[dict] = []
    variance_threshold = 0.05
    domain_loading_threshold = 0.50

    for trait, entry in traits.items():
        coeffs = entry.get("coefficients") or {}
        if not coeffs:
            continue
        source = entry.get("source", "")
        cited = extract_cited_facets(source)
        if not cited:
            results.append({
                "trait": trait,
                "cited": [],
                "overall": "WARN",
                "reason": "no facet-level citation in source string",
                "per_facet": [],
            })
            continue

        per_facet: list[dict] = []
        trait_vals = realm_trait_values[trait]

        for facet in cited:
            fi = facet_idx[facet]
            facet_vals = facets[:, fi].astype(np.float64)

            # (a) Variance
            facet_std = float(np.nanstd(facet_vals))
            variance_pass = facet_std >= variance_threshold

            # (b) Domain loading
            parent_domain = FACET_TO_DOMAIN[facet]
            parent_key = DOMAIN_TO_KEY[parent_domain]
            parent_idx_in_domains = DOMAINS.index(parent_domain)
            domain_vals = domains[:, parent_idx_in_domains].astype(np.float64)
            r_domain = _pearson_vec(facet_vals, domain_vals)
            domain_loading_pass = r_domain >= domain_loading_threshold

            # (c) Direction
            realm_coeff = float(coeffs.get(parent_key, 0.0))
            r_trait = _pearson_vec(facet_vals, trait_vals.astype(np.float64))
            if abs(realm_coeff) < 1e-9:
                direction_pass = True  # no direction claimed on this domain
                direction_verdict = "n/a"
            else:
                direction_pass = (realm_coeff > 0) == (r_trait > 0)
                direction_verdict = "match" if direction_pass else "mismatch"

            # Overall verdict for this facet
            if variance_pass and domain_loading_pass and direction_pass:
                facet_status = "PASS"
            elif not variance_pass or not domain_loading_pass:
                facet_status = "FAIL"
            else:
                facet_status = "WARN"

            per_facet.append({
                "facet": facet,
                "facet_std": facet_std,
                "r_facet_domain": r_domain,
                "realm_domain_coeff": realm_coeff,
                "r_facet_realm_trait": r_trait,
                "direction": direction_verdict,
                "status": facet_status,
                "variance_pass": variance_pass,
                "domain_loading_pass": domain_loading_pass,
                "direction_pass": direction_pass,
            })

        # Trait overall: FAIL if any cited facet fails; WARN if any WARN; else PASS
        statuses = [f["status"] for f in per_facet]
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "WARN" in statuses:
            overall = "WARN"
        else:
            overall = "PASS"

        results.append({
            "trait": trait,
            "cited": cited,
            "overall": overall,
            "reason": "",
            "per_facet": per_facet,
        })

    # Write report
    lines: list[str] = []
    lines.append("# Facet-Level Validation Report")
    lines.append("")
    lines.append("Audit of facet-specific citations embedded in "
                 "`data/personality/big_five_derivation.json` against the "
                 "Johnson IPIP-NEO-120 dataset (N="
                 f"{N:,} respondents, from {len(records):,} parsed).")
    lines.append("")
    lines.append("**Source of facet scoring:** "
                 "[data/personality/ipip_neo_120_scoring_key.json](../data/personality/ipip_neo_120_scoring_key.json)")
    lines.append("")
    lines.append("## Criteria per cited facet")
    lines.append("")
    lines.append(
        f"- **Variance:** std(facet) >= {variance_threshold:.2f} on the "
        "Johnson sample.\n"
        f"- **Domain loading:** Pearson r(facet, parent_domain) >= "
        f"{domain_loading_threshold:.2f} — facet actually loads on its "
        "claimed parent domain.\n"
        "- **Direction:** sign of REALM's coefficient on the parent domain "
        "agrees with sign of corr(facet, REALM's synthetic trait output).",
    )
    lines.append("")

    pass_n = sum(1 for r in results if r["overall"] == "PASS")
    warn_n = sum(1 for r in results if r["overall"] == "WARN")
    fail_n = sum(1 for r in results if r["overall"] == "FAIL")
    lines.append(
        f"## Summary: {pass_n} PASS, {warn_n} WARN, {fail_n} FAIL "
        f"across {len(results)} derived traits.",
    )
    lines.append("")

    lines.append("## Per-trait results")
    lines.append("")
    lines.append("| trait | cited facets | overall | notes |")
    lines.append("|-------|--------------|---------|-------|")
    for r in results:
        cited_s = ", ".join(r["cited"]) if r["cited"] else "—"
        note = r["reason"] or ""
        if r["per_facet"]:
            # Compact per-facet status strings
            facet_summaries = ", ".join(
                f"{f['facet']}:{f['status']}" for f in r["per_facet"]
            )
            note = facet_summaries
        lines.append(f"| {r['trait']} | {cited_s} | **{r['overall']}** | {note} |")
    lines.append("")

    lines.append("## Detailed facet checks")
    lines.append("")
    for r in results:
        if not r["per_facet"]:
            continue
        lines.append(f"### {r['trait']} — overall **{r['overall']}**")
        lines.append("")
        lines.append("| facet | std | r(facet, domain) | REALM coeff | r(facet, trait) | direction | status |")
        lines.append("|-------|-----|------------------|-------------|-----------------|-----------|--------|")
        for f in r["per_facet"]:
            lines.append(
                f"| {f['facet']} | {f['facet_std']:.3f} | "
                f"{f['r_facet_domain']:+.3f} | "
                f"{f['realm_domain_coeff']:+.2f} | "
                f"{f['r_facet_realm_trait']:+.3f} | "
                f"{f['direction']} | {f['status']} |",
            )
        lines.append("")

    lines.append("## Honest limitations")
    lines.append("")
    lines.append(
        "- IPIP-NEO-120 has only 4 items per facet. Short facet scales are "
        "noisier than the full 10-item IPIP-NEO-300 versions, so "
        "direction-check failures on small REALM coefficients (|β|<0.15) "
        "should be read as WARN not FAIL.",
    )
    lines.append(
        "- REALM's `BigFiveAdapter` derives traits from domain scores only; "
        "the facet→trait correlation is therefore a proxy for whether the "
        "cited facet would add information above its parent domain if "
        "REALM switched to facet-level inputs. Near-zero direction r "
        "reflects the single-domain derivation, not an error in citation.",
    )
    lines.append(
        "- Facet citations that survive all three checks here are candidates "
        "for promotion to per-facet coefficients in a follow-up sprint. "
        "See `data/personality/big_five_derivation_facets_draft.json` for "
        "the draft proposal emitted by `scripts/draft_facet_coefficients.py`.",
    )
    lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(f"\nSummary: {pass_n} PASS, {warn_n} WARN, {fail_n} FAIL "
          f"across {len(results)} derived traits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
