"""BigFiveAdapter — user supplies 5 OCEAN scores, we derive 24 traits.

Formula per derived trait:

    value = 0.5 + Σ_{bf ∈ OCEAN} coeff_bf × (bf_score - 0.5)
    clamp to [0, 1]

Coefficients come from `data/personality/big_five_derivation.json` — each entry
names its literature source and confidence marker. Traits with no published
Big Five correlation fall back to 0.5; this is intentional and labeled.

Coefficients are literature-informed best estimates, NOT measured correlations
on a REALM-specific sample. Validity study must re-measure against a held-out
trait inventory before claiming predictive accuracy.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from realm.core.config import load_realm_config
from realm.core.exceptions import PersonalityEmbeddingError
from realm.personality.trait_vector import TraitVector

from .interfaces import IInputAdapter

BIG_FIVE_KEYS: tuple[str, ...] = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)

# IPIP-NEO facet codes: O1..O6, C1..C6, E1..E6, A1..A6, N1..N6
_FACET_CODES: frozenset[str] = frozenset(
    f"{d}{i}" for d in "OCEAN" for i in range(1, 7)
)


@dataclass(frozen=True, slots=True)
class DerivationEntry:
    """Per-trait coefficient block.

    `coefficients` is the domain-level (5 OCEAN keys) mapping — always
    populated for a sourced trait. `facet_coefficients` is an optional
    facet-level mapping (IPIP-NEO facet codes like O5, N1, C6). When
    `use_facets` is enabled AND the input provides all facets listed in
    `facet_coefficients`, the adapter uses the facet formula; otherwise
    it falls back to domain-level.
    """

    coefficients: Mapping[str, float]
    source: str
    confidence: str
    facet_coefficients: Mapping[str, float] | None = None


class BigFiveAdapter(IInputAdapter):
    """OCEAN → 24-trait vector.

    Backwards-compatible: input dict with 5 OCEAN keys works exactly as
    before. When `use_facets=True` (constructor arg or via realm.yaml's
    `realm.personality.big_five.use_facets`), the adapter will also accept
    IPIP-NEO facet keys (O1..N6) in the input. For any trait with a
    `facet_coefficients` block whose required facets are all present, the
    facet-level formula is used; unlisted/missing-facet traits fall back
    to the domain formula.
    """

    def __init__(
        self,
        derivation_path: str | Path | None = None,
        use_facets: bool | None = None,
    ) -> None:
        self._derivation: dict[str, DerivationEntry] = {}
        self._raw_notes: dict[str, Any] = {}
        path = Path(
            derivation_path or Path(__file__).parent.parent.parent.parent
            / "data" / "personality" / "big_five_derivation.json",
        )
        if path.exists():
            self._load_derivation(path)
        # else: derivation table not yet generated — all 19 domain traits
        # fall back to 0.5. AdapterType still valid.

        if use_facets is None:
            try:
                cfg = load_realm_config()
                use_facets = bool(
                    cfg.get("realm", {})
                    .get("personality", {})
                    .get("big_five", {})
                    .get("use_facets", False),
                )
            except Exception:
                use_facets = False
        self._use_facets: bool = use_facets

    def _load_derivation(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._raw_notes = {k: v for k, v in raw.items() if k.startswith("_")}
        traits_block = raw.get("traits", {})
        for trait, entry in traits_block.items():
            coeffs = entry.get("coefficients")
            if not coeffs:
                continue
            facet_coeffs_raw = entry.get("facet_coefficients")
            facet_coeffs = (
                {k: float(v) for k, v in facet_coeffs_raw.items()}
                if isinstance(facet_coeffs_raw, Mapping)
                else None
            )
            self._derivation[trait] = DerivationEntry(
                coefficients={k: float(v) for k, v in coeffs.items()},
                source=str(entry.get("source", "")),
                confidence=str(entry.get("confidence", "unspecified")),
                facet_coefficients=facet_coeffs,
            )

    def build(self, input_data: Any) -> TraitVector:
        if not isinstance(input_data, Mapping):
            raise PersonalityEmbeddingError(
                f"BigFiveAdapter expects Mapping of Big Five scores, "
                f"got {type(input_data).__name__}",
            )
        domain_scores: dict[str, float] = {}
        for k in BIG_FIVE_KEYS:
            if k not in input_data:
                raise PersonalityEmbeddingError(
                    f"BigFiveAdapter missing required Big Five key {k!r}; "
                    f"provided keys: {sorted(input_data.keys())}",
                )
            domain_scores[k] = float(input_data[k])

        # Collect any facet scores present in input (optional)
        facet_scores: dict[str, float] = {
            k: float(v) for k, v in input_data.items()
            if k in _FACET_CODES
        }

        values: dict[str, float] = {}
        for k in BIG_FIVE_KEYS:
            values[k] = domain_scores[k]

        for trait in TraitVector.trait_names():
            if trait in BIG_FIVE_KEYS:
                continue
            entry = self._derivation.get(trait)
            if entry is None:
                values[trait] = 0.5
                continue

            # Prefer facet formula when enabled AND all required facets present.
            if (
                self._use_facets
                and entry.facet_coefficients
                and all(f in facet_scores for f in entry.facet_coefficients)
            ):
                value = 0.5
                for facet, coeff in entry.facet_coefficients.items():
                    value += coeff * (facet_scores[facet] - 0.5)
                values[trait] = value
                continue

            # Domain fallback (original behavior)
            value = 0.5
            for bf_key, coeff in entry.coefficients.items():
                if bf_key not in domain_scores:
                    continue
                value += coeff * (domain_scores[bf_key] - 0.5)
            values[trait] = value

        return TraitVector.from_dict(values)

    @property
    def adapter_type(self) -> str:
        return "big_five"

    @property
    def use_facets(self) -> bool:
        return self._use_facets

    @property
    def derived_trait_count(self) -> int:
        """Count of 19 domain traits that have a literature-backed entry."""
        return len(self._derivation)

    @property
    def facet_enabled_trait_count(self) -> int:
        """Count of traits that have a facet_coefficients block."""
        return sum(
            1 for e in self._derivation.values() if e.facet_coefficients
        )

    @property
    def unsourced_traits(self) -> list[str]:
        """List of domain traits falling back to 0.5 because no source exists."""
        all_domain = [n for n in TraitVector.trait_names() if n not in BIG_FIVE_KEYS]
        return sorted(t for t in all_domain if t not in self._derivation)
