"""Per-sub-group Big Five validity matrix — §11 of the real-data study.

Runs the same 6 pass/fail criteria that `validate_bf_study_real.py` applies
to the full real sample, but broken down by:

  - top-10 countries by N in the stratified sample
  - sex (M / F)
  - age band (18-25 / 26-35 / 36-50 / 51+)

The criteria that need the entire population for well-defined statistics
(butterfly lift) are omitted from the sub-group matrix because running a
full branch simulation per sub-group would 10x runtime without adding
interpretable signal at the sub-population N. Six criteria remain:

    1. BigFive mean trait std >= 0.14 (cal ON)
    2. Big Five input↔output r >= 0.99 (cal OFF)
    3. Input correlation signs preserved (cal OFF)
   4a. Derived 13 traits std > 0.05 (cal OFF)
   4b. Derived 13 traits std > 0.05 (cal ON)
    6. Derived structural pairs match >= 50%

Per the plan this is informational-only: FAIL on any subgroup is logged,
not treated as overall failure.

Output:  outputs/bf_validity_subgroups_real.md

Usage:
    python scripts/validate_bf_subgroups.py [N=10000] [--seed=42]
"""

from __future__ import annotations

import contextlib as _ctx
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.core.logging import setup_logging  # noqa: E402
from realm.personality.adapters import get_input_adapter  # noqa: E402
from realm.personality.bf_population import OCEAN  # noqa: E402
from realm.personality.calibration import TraitCalibrator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from load_bigfive_real import _age_band, load_real_population  # noqa: E402

TARGET_STD_MIN = 0.14
PASS_THROUGH_MIN = 0.99
DERIVED_STD_MIN = 0.05
DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"
MIN_SUBGROUP_N = 30  # below this, skip sub-group analysis (too noisy)


@dataclass(frozen=True)
class SubgroupResult:
    label: str
    n: int
    mean_std_cal_on: float
    pt_min: float
    sign_preserved: tuple[int, int]
    derived_off_min: float
    derived_on_min: float
    structural: tuple[int, int]

    def checks(self) -> dict[str, bool]:
        return {
            "1": self.mean_std_cal_on >= TARGET_STD_MIN,
            "2": self.pt_min >= PASS_THROUGH_MIN,
            "3": self.sign_preserved[0] == self.sign_preserved[1],
            "4a": self.derived_off_min > DERIVED_STD_MIN,
            "4b": self.derived_on_min > DERIVED_STD_MIN,
            "6": self.structural[0] / max(self.structural[1], 1) >= 0.50,
        }


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------

def _moments(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    if n < 2:
        return (vals[0] if vals else 0.0, 0.0)
    m = statistics.mean(vals)
    s = statistics.stdev(vals)
    return (m, s if s > 1e-9 else 0.0)


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
# Pipeline
# --------------------------------------------------------------------------

def _make_calibrator(enabled: bool) -> TraitCalibrator:
    if enabled:
        # Real-population sub-groups evaluated with the real-sourced stats.
        return TraitCalibrator(
            enabled=True,
            target_mean=0.50,
            target_std=0.17,
            adapter_type="big_five",
            source="real",
        )
    return TraitCalibrator(enabled=False)


def run_bf_pipeline(
    profiles, enable_cal: bool,
) -> dict[str, list[float]]:
    adapter = get_input_adapter("big_five")
    calibrator = _make_calibrator(enable_cal)
    factory = AgentFactory(adapter=adapter, calibrator=calibrator)
    agents = factory.build_batch(profiles)
    data: dict[str, list[float]] = {n: [] for n in TraitVector.trait_names()}
    for a in agents:
        for n in TraitVector.trait_names():
            data[n].append(getattr(a.traits, n))
    return data


def _load_derivation() -> dict[str, dict[str, float]]:
    raw = json.loads(DERIVATION_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict[str, float]] = {}
    for trait, entry in raw.get("traits", {}).items():
        coeffs = entry.get("coefficients")
        if coeffs:
            out[trait] = {k: float(v) for k, v in coeffs.items()}
    return out


def _structural_pairs(
    derivation: dict[str, dict[str, float]],
) -> list[tuple[str, str, int]]:
    entries = []
    for trait, coeffs in derivation.items():
        drv, coef = max(coeffs.items(), key=lambda kv: abs(kv[1]))
        entries.append((trait, drv, coef))
    pairs = []
    for i in range(len(entries)):
        ta, da, ca = entries[i]
        for j in range(i + 1, len(entries)):
            tb, db, cb = entries[j]
            if da == db:
                pairs.append((ta, tb, 1 if ca * cb > 0 else -1))
    return pairs


# --------------------------------------------------------------------------
# Per-subgroup evaluation
# --------------------------------------------------------------------------

def evaluate(
    label: str,
    profiles: list,
    bf_scores: list[dict[str, float]],
    s_pairs: list[tuple[str, str, int]],
    derived_traits: tuple[str, ...],
) -> SubgroupResult | None:
    n = len(profiles)
    if n < MIN_SUBGROUP_N:
        return None

    out_off = run_bf_pipeline(profiles, enable_cal=False)
    out_on = run_bf_pipeline(profiles, enable_cal=True)

    # Criterion 1
    stds_on = [_moments(out_on[t])[1] for t in TraitVector.trait_names()]
    mean_std_cal_on = statistics.mean(stds_on)

    # Criterion 2
    pt_min = min(
        _pearson([d[t] for d in bf_scores], out_off[t]) for t in OCEAN
    )

    # Criterion 3 (sign preservation of input intercorrelations)
    sign_hits = 0
    sign_total = 0
    for i, a in enumerate(OCEAN):
        for b in OCEAN[i + 1:]:
            r_in = _pearson([d[a] for d in bf_scores], [d[b] for d in bf_scores])
            r_out = _pearson(out_off[a], out_off[b])
            sign_total += 1
            if (r_in > 0) == (r_out > 0) or abs(r_in) < 0.02:
                sign_hits += 1

    # Criterion 4a / 4b
    derived_off = [_moments(out_off[t])[1] for t in derived_traits]
    derived_on = [_moments(out_on[t])[1] for t in derived_traits]

    # Criterion 6
    struct_hits = 0
    for (a, b, sign) in s_pairs:
        r = _pearson(out_off[a], out_off[b])
        if (r > 0) == (sign > 0) and abs(r) >= 0.10:
            struct_hits += 1

    return SubgroupResult(
        label=label, n=n,
        mean_std_cal_on=mean_std_cal_on,
        pt_min=pt_min,
        sign_preserved=(sign_hits, sign_total),
        derived_off_min=min(derived_off) if derived_off else 0.0,
        derived_on_min=min(derived_on) if derived_on else 0.0,
        structural=(struct_hits, len(s_pairs)),
    )


def _group_by(
    profiles: list, bf_scores: list[dict[str, float]], keyfn,
) -> dict[object, tuple[list, list[dict[str, float]]]]:
    out: dict[object, tuple[list, list[dict[str, float]]]] = {}
    for p, bf in zip(profiles, bf_scores, strict=True):
        k = keyfn(p)
        bucket = out.setdefault(k, ([], []))
        bucket[0].append(p)
        bucket[1].append(bf)
    return out


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def build_report(
    n: int, seed: int,
    overall: SubgroupResult,
    country_results: list[SubgroupResult],
    sex_results: list[SubgroupResult],
    age_results: list[SubgroupResult],
) -> str:
    lines: list[str] = []
    lines.append(
        f"# Real-Data BigFive Sub-group Validity Matrix (N={n}, seed={seed})",
    )
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(
        "Informational-only breakdown of `validate_bf_study_real.py` "
        "criteria applied per sub-group (country, sex, age-band). Minimum "
        f"sub-group size for evaluation: N >= {MIN_SUBGROUP_N}. Butterfly "
        "lift (criterion 5) is omitted because per-sub-group branch "
        "simulations don't meaningfully characterize sub-group behavior "
        "with the n=150 branch size, and criterion 8-real is a whole-sample "
        "distribution check.\n",
    )
    lines.append("Criteria abbreviated as #1, #2, #3, #4a, #4b, #6 per §10.\n")

    def _header() -> list[str]:
        return [
            "| subgroup | N | #1 mean std (cal ON) | #2 min r | #3 signs | #4a min std | #4b min std | #6 struct | passed |",
            "|---|---|---|---|---|---|---|---|---|",
        ]

    def _row(r: SubgroupResult) -> str:
        checks = r.checks()
        passed = sum(checks.values())
        c1 = f"{r.mean_std_cal_on:.3f} {_mark(checks['1'])}"
        c2 = f"{r.pt_min:.3f} {_mark(checks['2'])}"
        c3 = (
            f"{r.sign_preserved[0]}/{r.sign_preserved[1]} "
            f"{_mark(checks['3'])}"
        )
        c4a = f"{r.derived_off_min:.3f} {_mark(checks['4a'])}"
        c4b = f"{r.derived_on_min:.3f} {_mark(checks['4b'])}"
        c6 = (
            f"{r.structural[0]}/{r.structural[1]} "
            f"{_mark(checks['6'])}"
        )
        return f"| {r.label} | {r.n} | {c1} | {c2} | {c3} | {c4a} | {c4b} | {c6} | {passed}/6 |"

    # Overall reference row
    lines.append("## Overall (full real sample, baseline for comparison)\n")
    lines.extend(_header())
    lines.append(_row(overall))
    lines.append("")

    # Per-country (top 10 by N, descending)
    lines.append("## Per-country (top 10 by sample N)\n")
    lines.extend(_header())
    for r in sorted(country_results, key=lambda x: x.n, reverse=True)[:10]:
        lines.append(_row(r))
    lines.append("")

    # Per-sex
    lines.append("## Per-sex\n")
    lines.extend(_header())
    for r in sex_results:
        lines.append(_row(r))
    lines.append("")

    # Per-age-band
    lines.append("## Per-age-band\n")
    lines.extend(_header())
    for r in sorted(age_results, key=lambda x: x.label):
        lines.append(_row(r))
    lines.append("")

    lines.append("## Interpretation hints\n")
    lines.append(
        "- Expect **#2 to pass everywhere** — the BigFiveAdapter pipe-through "
        "is a direct copy with a cultural modifier, so per-trait Pearson r "
        "should stay ≥ 0.99 independent of sub-group.\n",
    )
    lines.append(
        "- Expect **#8-real style mean drift** (not shown here) to worsen "
        "in sub-groups with the largest IPIP-NEO response bias — typically "
        "younger age bands and English-speaking majorities.\n",
    )
    lines.append(
        "- Small-N sub-groups (close to the minimum N threshold) will show "
        "noise in #3 and #6; weight interpretation toward the larger "
        "per-country cells.\n",
    )
    lines.append(
        "- #1 (mean trait std cal ON) may FAIL in sub-groups where input "
        "variance is narrow — compression compounds through the calibrator "
        "when source std is low.\n",
    )
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

    print(f"Sub-group validity matrix: N={n}, seed={seed}")
    print("Output: outputs/bf_validity_subgroups_real.md\n")

    # Load population
    print(f"[1/4] Loading real population (N={n})...")
    t0 = time.perf_counter()
    profiles, diag = load_real_population(n=n, seed=seed)
    bf_scores = [dict(p.big_five_scores or {}) for p in profiles]
    print(f"      kept source rows: {diag['kept_rows']}")
    print(f"      sample size: {len(profiles)}")
    print(f"      done in {time.perf_counter() - t0:.1f}s")

    derivation = _load_derivation()
    s_pairs = _structural_pairs(derivation)
    derived_traits = tuple(sorted(derivation.keys()))

    # Overall
    print("[2/4] Overall sample eval...")
    overall = evaluate(
        "overall", profiles, bf_scores, s_pairs, derived_traits,
    )
    if overall is None:
        raise RuntimeError("Overall evaluation returned None (sample too small).")
    print(f"      passed: {sum(overall.checks().values())}/6")

    # Per-country
    print("[3/4] Per-country eval (top 10 by N)...")
    by_country = _group_by(profiles, bf_scores, lambda p: p.country)
    country_results: list[SubgroupResult] = []
    for iso2, (grp_profiles, grp_bf) in sorted(
        by_country.items(), key=lambda kv: len(kv[1][0]), reverse=True,
    )[:10]:
        r = evaluate(iso2, grp_profiles, grp_bf, s_pairs, derived_traits)
        if r is not None:
            country_results.append(r)

    # Per-sex
    print("[4/4] Per-sex and per-age-band eval...")
    sex_results: list[SubgroupResult] = []
    by_sex = _group_by(profiles, bf_scores, lambda p: p.gender)
    for sex_label, (grp_profiles, grp_bf) in by_sex.items():
        r = evaluate(sex_label, grp_profiles, grp_bf, s_pairs, derived_traits)
        if r is not None:
            sex_results.append(r)

    # Per-age-band
    age_results: list[SubgroupResult] = []
    by_age = _group_by(profiles, bf_scores, lambda p: _age_band(p.age_years))
    for age_label, (grp_profiles, grp_bf) in by_age.items():
        r = evaluate(age_label, grp_profiles, grp_bf, s_pairs, derived_traits)
        if r is not None:
            age_results.append(r)

    # Report
    report = build_report(
        n, seed, overall, country_results, sex_results, age_results,
    )
    out_path = ROOT / "outputs" / "bf_validity_subgroups_real.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"      wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
