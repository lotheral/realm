"""Load a real human Big Five population from automoto/big-five-data.

Downloads (if not cached), filters, maps country names to REALM ISO2 codes,
and stratifies a sample by country x sex proportional to the filtered
dataset's joint distribution. Builds hybrid DemographicProfile records by
running WorldGenerator's per-agent sampler on the mapped ISO2 and overriding
(age_years, gender, big_five_scores) with real values.

Canonical interface used by validate_bf_study_real.py:

    from load_bigfive_real import (
        load_real_population, load_filtered_dataset, REAL_DATASET_URL,
    )
    profiles = load_real_population(n=10000, seed=42)

CLI:
    python scripts/load_bigfive_real.py --download
    python scripts/load_bigfive_real.py [N=10000] [--seed=42] [--summary]
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import random
import sys
import urllib.request
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from realm.demographics.country_data import load_countries  # noqa: E402
from realm.demographics.interfaces import DemographicProfile  # noqa: E402
from realm.demographics.world_generator import WorldGenerator  # noqa: E402

REAL_DATASET_URL = (
    "https://raw.githubusercontent.com/automoto/big-five-data/"
    "master/big_five_scores.csv"
)
CACHE_DIR = PROJECT_ROOT / "data" / "external"
CACHE_FILE = CACHE_DIR / "big-five-data.csv"
EXPECTED_SHA256 = (
    "c9a3cf2fdca354345136ad50bcd101b6a260b4e864d8cd8fd5b7184aaf6ceaa8"
)

# Dataset country names are truncated to 10 chars. Map those truncated tokens
# to REALM ISO2. Only REALM-supported countries are listed; everything else
# is filtered out and reported in §0 of the validity report.
COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    # Original 30 REALM countries
    "USA": "US",
    "UK": "GB",
    "India": "IN",
    "Philippine": "PH",       # "Philippines"
    "Thailand": "TH",
    "Germany": "DE",
    "South Afri": "ZA",       # "South Africa"
    "China": "CN",
    "France": "FR",
    "Mexico": "MX",
    "Brazil": "BR",
    "Italy": "IT",
    "South Kore": "KR",       # "South Korea"
    "Spain": "ES",
    "Japan": "JP",
    "Turkey": "TR",
    "Russian Fe": "RU",       # "Russian Federation"
    "Pakistan": "PK",
    "Egypt": "EG",
    "Indonesia": "ID",
    "Columbia": "CO",         # dataset spelling of Colombia
    "Colombia": "CO",         # if ever spelled correctly
    "Nigeria": "NG",
    "Bangladesh": "BD",
    "Ethiopia": "ET",
    "Vietnam": "VN",
    "Iran": "IR",
    "Kenya": "KE",
    "Tanzania": "TZ",
    "Burma": "MM",            # Myanmar
    "Burma(Myan": "MM",
    "DR Congo": "CD",
    "Congo,Dem": "CD",

    # Sprint 5: expanded ~35 countries
    # Americas
    "Canada": "CA",
    "Argentina": "AR",
    "Chile": "CL",
    # Europe west
    "Portugal": "PT",
    "Ireland": "IE",
    "Netherland": "NL",
    "Belgium": "BE",
    "Luxembourg": "LU",
    "Switzerlan": "CH",
    "Austria": "AT",
    # Europe east
    "Czech Repu": "CZ",
    "Poland": "PL",
    "Hungary": "HU",
    "Romania": "RO",
    "Bulgaria": "BG",
    "Slovakia": "SK",
    "Ukraine": "UA",
    # Europe south
    "Croatia": "HR",
    "Serbia": "RS",
    "Greece": "GR",
    "Slovenia": "SI",
    # Europe north
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Iceland": "IS",
    "Estonia": "EE",
    "Latvia": "LV",
    "Lithuania": "LT",
    # Asia-Pacific / Oceania
    "Singapore": "SG",
    "Malaysia": "MY",
    "Australia": "AU",
    "New Zealan": "NZ",       # "New Zealand"
    # MENA
    "Israel": "IL",
    "United Ara": "AE",       # "United Arab Emirates"
    "Saudi Arab": "SA",       # "Saudi Arabia"
}

OCEAN_COL_MAP = {
    "openness": "openness_score",
    "conscientiousness": "conscientiousness_score",
    "extraversion": "extraversion_score",
    "agreeableness": "agreeable_score",
    "neuroticism": "neuroticism_score",
}


@dataclass(frozen=True, slots=True)
class RealRow:
    """One row from the filtered real dataset."""

    case_id: int
    country_iso2: str
    country_raw: str
    age: int
    sex: str                    # "M" | "F"
    big_five: dict[str, float]


def download_if_missing(force: bool = False) -> Path:
    """Ensure CACHE_FILE exists on disk; download from GitHub if not."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists() and not force:
        return CACHE_FILE
    print(f"[load_bigfive_real] downloading {REAL_DATASET_URL} -> {CACHE_FILE}")
    with urllib.request.urlopen(REAL_DATASET_URL) as resp, CACHE_FILE.open("wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    # SHA check — best-effort, log mismatch but don't fail (dataset may update)
    sha = hashlib.sha256(CACHE_FILE.read_bytes()).hexdigest()
    if sha != EXPECTED_SHA256:
        print(
            f"[load_bigfive_real] WARN: SHA256 mismatch. "
            f"expected={EXPECTED_SHA256}, got={sha}. "
            "Dataset may have been updated upstream — update EXPECTED_SHA256 "
            "and MANIFEST.md if this is intentional.",
        )
    return CACHE_FILE


def _parse_row(row: dict[str, str]) -> RealRow | None:
    """Validate + map a raw CSV row. Return None if unusable."""
    country_raw = (row.get("country") or "").strip()
    if not country_raw:
        return None
    iso2 = COUNTRY_NAME_TO_ISO2.get(country_raw)
    if iso2 is None:
        return None

    try:
        age = int(row["age"])
    except (KeyError, TypeError, ValueError):
        return None
    if age < 10 or age > 100:
        return None

    sex_raw = (row.get("sex") or "").strip()
    if sex_raw == "1":
        sex = "M"
    elif sex_raw == "2":
        sex = "F"
    else:
        return None

    bf: dict[str, float] = {}
    for trait, col in OCEAN_COL_MAP.items():
        val_s = (row.get(col) or "").strip()
        if not val_s:
            return None
        try:
            v = float(val_s)
        except ValueError:
            return None
        if not (0.0 <= v <= 1.0):
            return None
        bf[trait] = v

    try:
        case_id = int(row["case_id"])
    except (KeyError, ValueError):
        case_id = 0

    return RealRow(
        case_id=case_id,
        country_iso2=iso2,
        country_raw=country_raw,
        age=age,
        sex=sex,
        big_five=bf,
    )


def load_filtered_dataset(
    min_country_n: int = 100,
    csv_path: Path | None = None,
) -> tuple[list[RealRow], dict[str, int], dict[str, int]]:
    """Read the CSV, map countries, apply min_country_n, return rows + counts.

    Returns:
        (kept_rows, iso2_counts_kept, raw_country_counts_dropped)

    `raw_country_counts_dropped` includes everything filtered out — both
    unmapped country names and mapped countries with fewer than
    `min_country_n` participants.
    """
    path = csv_path or download_if_missing()

    # Pass 1: parse all valid rows, track ISO2 counts
    all_valid: list[RealRow] = []
    iso2_counts: dict[str, int] = {}
    dropped_unmapped: dict[str, int] = {}

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            parsed = _parse_row(row)
            if parsed is None:
                raw = (row.get("country") or "").strip() or "<empty>"
                # Treat unmapped country as "dropped for mapping reasons".
                # Other drop reasons (NaN OCEAN, invalid age/sex) mapped to
                # "<invalid_row>" so §0 can distinguish them.
                if raw and raw not in COUNTRY_NAME_TO_ISO2:
                    dropped_unmapped[raw] = dropped_unmapped.get(raw, 0) + 1
                else:
                    dropped_unmapped.setdefault("<invalid_row>", 0)
                    dropped_unmapped["<invalid_row>"] += 1
                continue
            all_valid.append(parsed)
            iso2_counts[parsed.country_iso2] = iso2_counts.get(parsed.country_iso2, 0) + 1

    # Pass 2: apply min_country_n on mapped ISO2 counts
    keep_iso2 = {iso2 for iso2, n in iso2_counts.items() if n >= min_country_n}
    kept = [r for r in all_valid if r.country_iso2 in keep_iso2]
    kept_counts = {iso2: iso2_counts[iso2] for iso2 in keep_iso2}

    # Promote dropped-by-min-N into the dropped report (keyed by ISO2)
    for iso2, n in iso2_counts.items():
        if iso2 not in keep_iso2:
            dropped_unmapped[f"[iso2:{iso2}]"] = n

    return kept, kept_counts, dropped_unmapped


def _stratified_indices(
    rows: list[RealRow],
    n: int,
    strata_keys: tuple[str, ...],
    rng: random.Random,
) -> list[int]:
    """Proportional allocation across (country, sex) strata.

    Groups rows by the chosen strata, computes each group's proportion of the
    total, rounds that to an integer sample count, and draws that many row
    indices with replacement from the group (seeded). If rounding undershoots
    or overshoots the target N, we patch by sampling from the largest groups.
    """
    total = len(rows)
    if total == 0:
        return []

    def _key(r: RealRow) -> tuple[object, ...]:
        out: list[object] = []
        for k in strata_keys:
            if k == "country":
                out.append(r.country_iso2)
            elif k == "sex":
                out.append(r.sex)
            elif k == "age_band":
                out.append(_age_band(r.age))
            else:
                raise ValueError(f"Unknown stratum key: {k!r}")
        return tuple(out)

    groups: dict[tuple[object, ...], list[int]] = {}
    for idx, row in enumerate(rows):
        groups.setdefault(_key(row), []).append(idx)

    allocations: dict[tuple[object, ...], int] = {}
    for key, idx_list in groups.items():
        prop = len(idx_list) / total
        allocations[key] = int(round(prop * n))

    delta = n - sum(allocations.values())
    if delta != 0:
        ordered = sorted(
            allocations.keys(), key=lambda k: len(groups[k]), reverse=True,
        )
        step = 1 if delta > 0 else -1
        i = 0
        while delta != 0:
            key = ordered[i % len(ordered)]
            if step == -1 and allocations[key] == 0:
                i += 1
                continue
            allocations[key] += step
            delta -= step
            i += 1

    picks: list[int] = []
    for key, count in allocations.items():
        if count <= 0:
            continue
        pool = groups[key]
        if count <= len(pool):
            picks.extend(rng.sample(pool, count))
        else:
            picks.extend(pool)
            picks.extend(rng.choices(pool, k=count - len(pool)))
    return picks


def _age_band(age: int) -> str:
    if age <= 25:
        return "18-25"
    if age <= 35:
        return "26-35"
    if age <= 50:
        return "36-50"
    return "51+"


def _profile_from_real(
    row: RealRow,
    agent_index: int,
    generator: WorldGenerator,
    rng: random.Random,
) -> DemographicProfile:
    """Build a hybrid DemographicProfile: synthetic base + real overrides.

    Uses WorldGenerator._generate_one to synthesize a country-consistent
    profile (city, timezone, profession, income, education, religion,
    marginal flag, name), then overrides the three fields that carry
    real-human signal (age_years, gender, big_five_scores) and patches the
    agent_id. Birth datetime year is recomputed from the real age so that
    downstream astrological handling (if ever re-enabled) is consistent.
    """
    base = generator._generate_one(row.country_iso2, rng, agent_index)
    # Recompute birth year for the real age while keeping month/day/hour/tz.
    epoch_year = generator._epoch.year
    new_birth_year = epoch_year - row.age
    new_birth_dt = base.birth_datetime.replace(year=new_birth_year)
    return replace(
        base,
        agent_id=f"REAL_{row.case_id:07d}",
        age_years=row.age,
        gender=row.sex,
        birth_datetime=new_birth_dt,
        big_five_scores=dict(row.big_five),
    )


def load_real_population(
    n: int = 10000,
    seed: int = 42,
    min_country_n: int = 100,
    stratify_by: tuple[str, ...] = ("country", "sex"),
    csv_path: Path | None = None,
) -> tuple[list[DemographicProfile], dict[str, object]]:
    """Load + stratified-sample + hybrid-profile the real Big Five population.

    Returns:
        (profiles, diagnostics) where diagnostics contains:
            - `kept_rows`: total valid rows after country mapping + min_country_n filter
            - `iso2_counts_full`: {iso2: count} in the filtered *source* dataset
            - `iso2_counts_sample`: {iso2: count} in the returned sample
            - `sex_counts_full`, `sex_counts_sample`
            - `age_band_counts_full`, `age_band_counts_sample`
            - `dropped`: {raw_country_or_marker: count} for everything excluded
            - `full_mean_std`: {trait: (mean, std)} computed on the full filtered set
            - `sample_mean_std`: {trait: (mean, std)} computed on the returned sample
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")

    # Sanity-check mapping targets exist in REALM
    supported = {c["iso2"] for c in load_countries()}
    for name, iso2 in COUNTRY_NAME_TO_ISO2.items():
        if iso2 not in supported:
            raise RuntimeError(
                f"COUNTRY_NAME_TO_ISO2['{name}'] -> '{iso2}' is not a "
                "REALM-supported ISO2; update data/countries.json or remove "
                "the mapping.",
            )

    rows, kept_counts, dropped = load_filtered_dataset(
        min_country_n=min_country_n, csv_path=csv_path,
    )
    if not rows:
        raise RuntimeError(
            "No rows kept after filtering — check country mapping and "
            "min_country_n threshold.",
        )

    rng = random.Random(seed)
    picks = _stratified_indices(rows, n, stratify_by, rng)

    generator = WorldGenerator(
        master_seed=seed, sim_epoch=datetime(2026, 1, 1, tzinfo=UTC),
    )
    profile_rng = random.Random(seed + 7919)
    profiles = [
        _profile_from_real(rows[idx], i, generator, profile_rng)
        for i, idx in enumerate(picks)
    ]

    # Diagnostics
    def _count(xs: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for x in xs:
            out[x] = out.get(x, 0) + 1
        return out

    full_traits = {
        trait: [r.big_five[trait] for r in rows]
        for trait in OCEAN_COL_MAP
    }
    sample_traits = {
        trait: [rows[idx].big_five[trait] for idx in picks]
        for trait in OCEAN_COL_MAP
    }

    def _ms(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return (0.0, 0.0)
        m = sum(vals) / len(vals)
        var = sum((v - m) ** 2 for v in vals) / max(len(vals) - 1, 1)
        return (m, var ** 0.5)

    diagnostics: dict[str, object] = {
        "kept_rows": len(rows),
        "iso2_counts_full": kept_counts,
        "iso2_counts_sample": _count([rows[idx].country_iso2 for idx in picks]),
        "sex_counts_full": _count([r.sex for r in rows]),
        "sex_counts_sample": _count([rows[idx].sex for idx in picks]),
        "age_band_counts_full": _count([_age_band(r.age) for r in rows]),
        "age_band_counts_sample": _count([_age_band(rows[idx].age) for idx in picks]),
        "dropped": dropped,
        "full_mean_std": {t: _ms(vs) for t, vs in full_traits.items()},
        "sample_mean_std": {t: _ms(vs) for t, vs in sample_traits.items()},
    }
    return profiles, diagnostics


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def _parse_argv(argv: list[str]) -> tuple[int, int, bool, bool]:
    n = 10000
    seed = 42
    do_download = False
    do_summary = False
    for arg in argv[1:]:
        if arg == "--download":
            do_download = True
        elif arg == "--summary":
            do_summary = True
        elif arg.startswith("--seed="):
            seed = int(arg.split("=", 1)[1])
        elif arg.isdigit():
            n = int(arg)
    return n, seed, do_download, do_summary


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    n, seed, do_download, do_summary = _parse_argv(argv)

    if do_download:
        download_if_missing(force=False)
        print(f"[load_bigfive_real] cached at {CACHE_FILE}")
        if not do_summary:
            return 0

    print(f"[load_bigfive_real] loading N={n}, seed={seed}")
    profiles, diag = load_real_population(n=n, seed=seed)
    print(f"  kept source rows: {diag['kept_rows']}")
    print(f"  sample size:      {len(profiles)}")
    print("  top 10 ISO2 in sample:")
    top = sorted(
        diag["iso2_counts_sample"].items(), key=lambda kv: kv[1], reverse=True,
    )[:10]
    for iso2, c in top:
        print(f"    {iso2:>3}  {c}")
    print("  sex split sample:", diag["sex_counts_sample"])
    print("  age band sample:", diag["age_band_counts_sample"])
    print("  OCEAN means (sample):")
    for trait, (m, s) in diag["sample_mean_std"].items():
        print(f"    {trait:<20} mean={m:.3f}  std={s:.3f}")
    if do_summary:
        dropped = diag["dropped"]
        non_iso = {k: v for k, v in dropped.items() if not k.startswith("[iso2:")}
        under_n = {k: v for k, v in dropped.items() if k.startswith("[iso2:")}
        print(f"  dropped (unmapped names): {sum(non_iso.values())} rows "
              f"across {len(non_iso)} keys")
        print(f"  dropped (mapped but N<100): {sum(under_n.values())} rows "
              f"across {len(under_n)} countries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
