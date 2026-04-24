"""LLM-based personality embedder (Mode B per doc §5.2).

Serializes the natal chart to JSON, calls an LLM with the persona prompt,
parses the 24-dim trait vector from the response.

Gracefully degrades to the rule-based embedder if:
    - No LLM backend is configured
    - LLM returns malformed output after retries

Embeddings are cached by natal-chart hash to avoid re-hitting the API for
the same agent across multiple runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from realm.core.exceptions import PersonalityEmbeddingError
from realm.core.logging import get_logger
from realm.core.types import NatalChart
from realm.llm.interfaces import ILLMBackend, LLMBackendError
from realm.llm.prompts import load_prompt
from realm.llm.router import TASK_PERSONALITY, LLMRouter

from .interfaces import IPersonalityEmbedder
from .rule_based import RuleBasedEmbedder
from .trait_vector import TraitVector

logger = get_logger(__name__)


def natal_chart_hash(chart: NatalChart) -> str:
    """Stable hash over (birth_dt, lat, lon, tz). Chart is a pure function of
    these inputs when the astro engine is fixed, so this key is safe."""
    payload = json.dumps(
        {
            "dt": chart.birth_datetime.isoformat(),
            "lat": round(chart.latitude, 4),
            "lon": round(chart.longitude, 4),
            "tz": chart.timezone,
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def serialize_natal_chart(chart: NatalChart) -> str:
    """Compact JSON view of the chart fit for LLM consumption."""
    return json.dumps({
        "birth_datetime": chart.birth_datetime.isoformat(),
        "location": {
            "lat": round(chart.latitude, 3),
            "lon": round(chart.longitude, 3),
            "tz": chart.timezone,
        },
        "ascendant": round(chart.ascendant, 2),
        "midheaven": round(chart.midheaven, 2),
        "planets": [
            {
                "name": p.name,
                "sign": p.sign,
                "sign_degree": round(p.sign_degree, 2),
                "house": p.house,
                "retrograde": p.is_retrograde,
            }
            for p in chart.planets
        ],
        "aspects": [
            {
                "p1": a.planet1, "p2": a.planet2,
                "type": a.aspect_type,
                "orb": round(a.orb, 2),
                "applying": a.is_applying,
            }
            for a in chart.aspects
        ],
        "element_balance": {k: round(v, 3) for k, v in chart.element_balance.items()},
        "modality_balance": {k: round(v, 3) for k, v in chart.modality_balance.items()},
    }, separators=(",", ":"))


@dataclass
class LLMEmbedder(IPersonalityEmbedder):
    """Mode B — pure LLM embedder."""

    backend: ILLMBackend | None = None
    router: LLMRouter | None = None
    fallback_to_rule_based: bool = True
    _cache: dict[str, TraitVector] = field(default_factory=dict)

    def __post_init__(self):
        if self.backend is None:
            router = self.router or LLMRouter()
            try:
                self.backend = router.for_task(TASK_PERSONALITY)
            except LLMBackendError as e:
                if not self.fallback_to_rule_based:
                    raise
                logger.warning("LLMEmbedder: %s — falling back to rule-based", e)
                self.backend = None

    @property
    def mode(self) -> str:
        return "llm"

    def embed(self, chart: NatalChart) -> TraitVector:
        key = natal_chart_hash(chart)
        if key in self._cache:
            return self._cache[key]

        if self.backend is None:
            tv = RuleBasedEmbedder().embed(chart)
            self._cache[key] = tv
            return tv

        system_prompt = load_prompt("personality/system").content
        user_template = load_prompt("personality/user_template")
        user = user_template.render(chart_json=serialize_natal_chart(chart))

        try:
            raw = self.backend.complete_json(
                system=system_prompt, user=user,
                max_tokens=1024, temperature=0.2,
            )
        except LLMBackendError as e:
            if not self.fallback_to_rule_based:
                raise PersonalityEmbeddingError(str(e)) from e
            logger.warning("LLM embed failed (%s) — using rule-based fallback", e)
            tv = RuleBasedEmbedder().embed(chart)
            self._cache[key] = tv
            return tv

        tv = _trait_vector_from_dict(raw)
        self._cache[key] = tv
        return tv


def _trait_vector_from_dict(data: Any) -> TraitVector:
    if not isinstance(data, dict):
        raise PersonalityEmbeddingError(
            f"LLM must return a JSON object, got {type(data).__name__}",
        )
    return TraitVector.from_dict(
        {k: v for k, v in data.items() if isinstance(v, (int, float))}
    )
