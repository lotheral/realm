"""Country, city, and Hofstede data loaders with indexed lookup helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from realm.core.config import load_json
from realm.core.exceptions import DataError

# ---- Loaders --------------------------------------------------------------

@lru_cache(maxsize=1)
def load_countries() -> list[dict[str, Any]]:
    raw = load_json("countries.json")
    countries = raw.get("countries", [])
    if not countries:
        raise DataError("countries.json has no 'countries' list")
    return countries


@lru_cache(maxsize=1)
def load_cities() -> list[dict[str, Any]]:
    raw = load_json("cities.json")
    cities = raw.get("cities", [])
    if not cities:
        raise DataError("cities.json has no 'cities' list")
    return cities


@lru_cache(maxsize=1)
def load_hofstede() -> dict[str, dict[str, int]]:
    raw = load_json("hofstede_scores.json")
    scores = raw.get("scores", {})
    if not scores:
        raise DataError("hofstede_scores.json has no 'scores' dict")
    return scores


@lru_cache(maxsize=1)
def load_hofstede_global_mean() -> dict[str, int]:
    raw = load_json("hofstede_scores.json")
    return raw.get("global_mean", {"pdi": 50, "idv": 50, "mas": 50,
                                    "uai": 50, "lto": 50, "ivr": 50})


@lru_cache(maxsize=1)
def load_professions() -> dict[str, Any]:
    return load_json("professions.json")


@lru_cache(maxsize=1)
def load_birth_hour_weights() -> list[float]:
    raw = load_json("birth_hour_weights.json")
    weights = raw.get("hour_weights", [])
    if len(weights) != 24:
        raise DataError(f"birth_hour_weights.json must have 24 entries, got {len(weights)}")
    return weights


# ---- Indexed lookups ------------------------------------------------------

@lru_cache(maxsize=1)
def countries_by_iso() -> dict[str, dict[str, Any]]:
    return {c["iso2"]: c for c in load_countries()}


@lru_cache(maxsize=1)
def cities_by_country() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for city in load_cities():
        grouped.setdefault(city["country"], []).append(city)
    return grouped


def get_country(iso2: str) -> dict[str, Any]:
    countries = countries_by_iso()
    if iso2 not in countries:
        raise DataError(f"country {iso2!r} not found")
    return countries[iso2]


def get_cities_for(iso2: str) -> list[dict[str, Any]]:
    cities = cities_by_country().get(iso2, [])
    if not cities:
        raise DataError(f"no cities found for country {iso2!r}")
    return cities


def get_hofstede(iso2: str) -> dict[str, int]:
    """Return Hofstede 6D scores. Falls back to global mean if country missing."""
    scores = load_hofstede()
    if iso2 in scores:
        return scores[iso2]
    return load_hofstede_global_mean()
