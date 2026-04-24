"""Input adapter factory — picks the right adapter given a mode string."""

from __future__ import annotations

from typing import Any

from realm.core.config import load_realm_config
from realm.core.exceptions import PersonalityEmbeddingError

from .astrological import AstrologicalAdapter
from .big_five import BigFiveAdapter
from .blended import BlendedAdapter, BlendedComponent
from .demographic import DemographicAdapter
from .interfaces import IInputAdapter


def _build_leaf_adapter(adapter_type: str) -> IInputAdapter:
    """Build a non-blended adapter by string type."""
    if adapter_type == "astrological":
        return AstrologicalAdapter()
    if adapter_type == "big_five":
        return BigFiveAdapter()
    if adapter_type == "demographic":
        return DemographicAdapter()
    raise PersonalityEmbeddingError(
        f"unknown input adapter type: {adapter_type!r}",
    )


_DEFAULT_BLENDED_CONFIG: dict[str, Any] = {
    "components": [
        {"type": "big_five", "weight": 0.6},
        {"type": "astrological", "weight": 0.4},
    ],
    "noise_sigma": 0.05,
}


def _build_blended_from_config(cfg: dict[str, Any] | None = None) -> BlendedAdapter:
    """Construct a BlendedAdapter from the personality.blended config block.

    Falls back to the default (BigFive 0.6 + Astro 0.4, σ=0.05) if the block
    is absent or malformed.
    """
    if cfg is None:
        cfg = (
            load_realm_config()
            .get("realm", {})
            .get("personality", {})
            .get("blended", {})
            or _DEFAULT_BLENDED_CONFIG
        )
    raw_components = cfg.get("components") or _DEFAULT_BLENDED_CONFIG["components"]
    noise_sigma = float(cfg.get("noise_sigma", _DEFAULT_BLENDED_CONFIG["noise_sigma"]))

    components: list[BlendedComponent] = []
    for entry in raw_components:
        t = entry.get("type")
        w = float(entry.get("weight", 0.0))
        if t == "blended":
            raise PersonalityEmbeddingError(
                "nested blended adapters are not supported",
            )
        components.append(
            BlendedComponent(adapter=_build_leaf_adapter(t), weight=w),
        )
    return BlendedAdapter(components=components, noise_sigma=noise_sigma)


def get_input_adapter(adapter_type: str | None = None) -> IInputAdapter:
    """Return a ready-to-use adapter.

    Args:
        adapter_type: 'astrological' | 'big_five' | 'demographic' | 'blended'.
            If None, read from realm.yaml:realm.personality.adapter
            (defaults to 'astrological' when the key is absent).
    """
    if adapter_type is None:
        cfg = load_realm_config()
        adapter_type = (
            cfg.get("realm", {})
               .get("personality", {})
               .get("adapter", "astrological")
        )
    if adapter_type == "blended":
        return _build_blended_from_config()
    return _build_leaf_adapter(adapter_type)
