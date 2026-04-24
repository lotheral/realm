"""Loader + accessor for planet→trait mapping tables.

Data lives in data/astro/:
    planet_trait_map.json  — per-planet base trait deltas
    aspect_weights.json    — per-aspect amplification + per-planet weights
    sign_modifiers.json    — per-sign additive trait shifts

All load functions are cached.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache

from realm.core.config import load_json


@lru_cache(maxsize=1)
def load_planet_trait_map() -> Mapping[str, Mapping[str, float]]:
    """Return {planet_name: {trait_name: delta_in_[-1,1]}}."""
    raw = load_json("astro/planet_trait_map.json")
    return {k: v for k, v in raw.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def load_sign_modifiers() -> Mapping[str, Mapping[str, float]]:
    """Return {sign_name: {trait_name: delta_in_[-0.3,0.3]}}."""
    raw = load_json("astro/sign_modifiers.json")
    return {k: v for k, v in raw.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def load_aspect_weights() -> tuple[Mapping[str, float], Mapping[str, float]]:
    """Return (aspect_type→weight, planet_name→relative_weight)."""
    raw = load_json("astro/aspect_weights.json")
    aspects = {
        k: v for k, v in raw.items()
        if not k.startswith("_") and k != "planet_weights" and isinstance(v, (int, float))
    }
    planet_weights = raw.get("planet_weights", {})
    return aspects, planet_weights
