"""Country-aware name generation.

Strategy:
    1. If country has `faker_locale`, use Faker with that locale.
    2. Else, load data/names/{iso2_lower}.json fallback list.
    3. Else, fall back to Faker("en_US").

All Faker instances are seeded from the caller-supplied Random so the generated
names are reproducible per master_seed.
"""

from __future__ import annotations

import random
from functools import lru_cache
from typing import Any

from faker import Faker

from realm.core.config import load_json
from realm.core.exceptions import DataError
from realm.core.logging import get_logger

from .country_data import get_country

logger = get_logger(__name__)

_FALLBACK_COUNTRIES: tuple[str, ...] = ("PK", "ET", "IR", "TZ", "MM")


@lru_cache(maxsize=64)
def _faker_for(locale: str) -> Faker:
    """Cached Faker instance per locale. Seed at call time."""
    return Faker(locale)


@lru_cache(maxsize=64)
def _fallback_names(iso2: str) -> dict[str, Any]:
    """Load fallback name pool for a country."""
    iso = iso2.lower()
    try:
        return load_json(f"names/{iso}.json")
    except DataError as e:
        raise DataError(f"No fallback names for country {iso2!r}") from e


def generate_name(
    iso2: str,
    gender: str,
    rng: random.Random,
) -> tuple[str, str]:
    """Return (first_name, last_name) sampled for the given country and gender."""
    country = get_country(iso2)
    locale = country.get("faker_locale")

    if locale:
        fk = _faker_for(locale)
        # Seeding Faker is per-instance — seed before each call for determinism.
        fk.seed_instance(rng.random())
        if gender == "M":
            first = _first_name_male(fk)
        elif gender == "F":
            first = _first_name_female(fk)
        else:
            first = fk.first_name()
        last = fk.last_name()
        return first, last

    # Fallback to static JSON pool
    pool = _fallback_names(iso2)
    if gender == "M":
        firsts = pool["first_names_m"]
    elif gender == "F":
        firsts = pool["first_names_f"]
    else:
        firsts = pool["first_names_m"] + pool["first_names_f"]
    return rng.choice(firsts), rng.choice(pool["last_names"])


def _first_name_male(fk: Faker) -> str:
    """Faker exposes first_name_male() on most locales; fall back otherwise."""
    try:
        return fk.first_name_male()
    except AttributeError:
        return fk.first_name()


def _first_name_female(fk: Faker) -> str:
    try:
        return fk.first_name_female()
    except AttributeError:
        return fk.first_name()
