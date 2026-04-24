"""IPIP-NEO-120 facet scorer.

Parses the fixed-width IPIP120.dat file (Johnson 2014, N=619,150) and
computes per-respondent facet and domain scores using the published item
→ facet mapping.

IPIP120.dat properties (from DAT120.doc):
- 151 chars per row
- Reverse-keyed items are ALREADY pre-reversed in the data (values 1-5,
  0 = missing). No recoding needed at scoring time.
- Fields at positions 1-31 are demographics; positions 32-151 are I1..I120.

Normalization:
- Each facet is 4 items × (1..5) → raw range [4, 20]. We rescale to [0, 1].
- Each domain is the mean of its 6 facets → already [0, 1] after facet rescale.

Rows with ≥2 missing items on ANY facet (out of 4 items/facet) are dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DAT_PATH = REPO_ROOT / "data" / "external" / "IPIP120.dat"
DEFAULT_KEY_PATH = REPO_ROOT / "data" / "personality" / "ipip_neo_120_scoring_key.json"

DOMAINS: tuple[str, ...] = ("O", "C", "E", "A", "N")
FACET_CODES: tuple[str, ...] = tuple(
    f"{d}{i}" for d in DOMAINS for i in range(1, 7)
)  # O1..O6, C1..C6, ..., N1..N6 — 30 facets

FACET_TO_DOMAIN: dict[str, str] = {f: f[0] for f in FACET_CODES}


@dataclass(frozen=True, slots=True)
class ScoringKey:
    """Item-num → facet mapping (1-indexed item numbers)."""

    item_to_facet: dict[int, str]

    @property
    def facets(self) -> list[str]:
        seen = []
        for f in self.item_to_facet.values():
            if f not in seen:
                seen.append(f)
        return seen


def load_scoring_key(path: str | Path | None = None) -> ScoringKey:
    p = Path(path) if path else DEFAULT_KEY_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    item_to_facet: dict[int, str] = {}
    for item_num_str, entry in raw["items"].items():
        item_to_facet[int(item_num_str)] = entry["facet"]
    return ScoringKey(item_to_facet=item_to_facet)


@dataclass(frozen=True, slots=True)
class IPIPRecord:
    """One record parsed from IPIP120.dat."""

    case: int
    sex: str  # "M" | "F" | "?"
    age: int
    country: str  # 9-char trimmed
    items: np.ndarray  # shape (120,), dtype=int8, 1..5 (0 = missing)


def _parse_row(raw: bytes) -> IPIPRecord | None:
    """Parse one fixed-width row. Returns None if the row is malformed."""
    try:
        line = raw.decode("ascii", errors="replace")
        if len(line) < 151:
            return None
        case = int(line[0:6].strip() or "0")
        sex_raw = line[6:7].strip()
        sex = "M" if sex_raw == "1" else "F" if sex_raw == "2" else "?"
        age = int(line[7:9].strip() or "0")
        country = line[22:31].strip()
        # Items at positions 32..151 (0-indexed: 31..150), 1 char each
        item_chars = line[31:151]
        if len(item_chars) < 120:
            return None
        items = np.frombuffer(item_chars.encode("ascii"), dtype=np.uint8) - ord("0")
        # 0 = missing (kept as 0). Valid responses are 1-5.
        return IPIPRecord(
            case=case, sex=sex, age=age, country=country,
            items=items.astype(np.int8),
        )
    except (ValueError, UnicodeDecodeError):
        return None


def load_ipip120(
    dat_path: str | Path | None = None,
    max_rows: int | None = None,
) -> list[IPIPRecord]:
    """Load the fixed-width IPIP120.dat file.

    Args:
        dat_path: path to IPIP120.dat; defaults to data/external/IPIP120.dat.
        max_rows: if given, stop after this many successfully-parsed rows.
    """
    path = Path(dat_path) if dat_path else DEFAULT_DAT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"IPIP120.dat not found at {path}. Download via the URL in "
            f"data/external/MANIFEST.md.",
        )
    records: list[IPIPRecord] = []
    with path.open("rb") as f:
        for raw_line in f:
            rec = _parse_row(raw_line.rstrip(b"\r\n"))
            if rec is None:
                continue
            records.append(rec)
            if max_rows is not None and len(records) >= max_rows:
                break
    return records


def score_dataset(
    records: list[IPIPRecord],
    key: ScoringKey | None = None,
    min_valid_per_facet: int = 3,
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Compute facet and domain scores for each record.

    Returns:
        facets: np.ndarray of shape (N_kept, 30), values in [0, 1]
        domains: np.ndarray of shape (N_kept, 5), values in [0, 1]  (order O,C,E,A,N)
        kept_indices: list[int] indexes of records retained

    Records with fewer than `min_valid_per_facet` valid items on any facet
    are dropped to avoid noisy facet scores.
    """
    key = key or load_scoring_key()

    # Build a (30, 120) boolean mask: which items belong to which facet
    facet_idx = {f: i for i, f in enumerate(FACET_CODES)}
    mask = np.zeros((30, 120), dtype=bool)
    for item_num, facet in key.item_to_facet.items():
        mask[facet_idx[facet], item_num - 1] = True

    n_records = len(records)
    item_matrix = np.zeros((n_records, 120), dtype=np.int8)
    for i, rec in enumerate(records):
        item_matrix[i] = rec.items

    valid_mask = item_matrix > 0  # shape (N, 120)

    # For each row, for each facet, count valid items and sum responses
    facet_sums = np.zeros((n_records, 30), dtype=np.float32)
    facet_valid_counts = np.zeros((n_records, 30), dtype=np.int16)
    for fi in range(30):
        item_cols = np.where(mask[fi])[0]  # 4 item indices for this facet
        facet_sums[:, fi] = item_matrix[:, item_cols].astype(np.float32).sum(axis=1)
        facet_valid_counts[:, fi] = valid_mask[:, item_cols].sum(axis=1)

    # Drop respondents with insufficient valid items on any facet
    keep = (facet_valid_counts >= min_valid_per_facet).all(axis=1)
    kept_idx = np.where(keep)[0].tolist()

    # Compute mean response per facet (ignoring missing); rescale [1,5]→[0,1]
    # mean = sum / valid_count; rescaled = (mean - 1) / 4
    facet_means = np.divide(
        facet_sums[keep],
        facet_valid_counts[keep],
        out=np.full(facet_sums[keep].shape, np.nan, dtype=np.float32),
        where=facet_valid_counts[keep] > 0,
    )
    facet_01 = (facet_means - 1.0) / 4.0

    # Domain scores: mean of constituent facets
    domain_01 = np.zeros((len(kept_idx), 5), dtype=np.float32)
    for di, dom in enumerate(DOMAINS):
        cols = [facet_idx[f] for f in FACET_CODES if FACET_TO_DOMAIN[f] == dom]
        domain_01[:, di] = facet_01[:, cols].mean(axis=1)

    return facet_01, domain_01, kept_idx
