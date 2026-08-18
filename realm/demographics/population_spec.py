"""PopulationSpec — per-question target population (Sprint 21, design decision #2).

A question's population is defined by the request, not assumed to be "the
world": country and/or region restriction (union semantics), age band,
gender, and education filters. An empty spec means the full 66-country
world sample and MUST leave generation byte-identical to the pre-Sprint-21
pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from realm.demographics.country_data import load_countries

VALID_GENDERS = ("M", "F", "X")
VALID_EDUCATION_LEVELS = ("primary", "secondary", "bachelor", "graduate")

_AGE_FLOOR = 18
_AGE_CEIL = 90


@dataclass(frozen=True, slots=True)
class PopulationSpec:
    """Target population for one question. All fields optional; empty = world.

    ``countries`` (ISO2) and ``regions`` (country-data region keys) are
    UNIONED: the candidate set is every listed country plus every country
    in a listed region. Age/gender/education act as per-agent sampling
    constraints inside the candidate countries.
    """

    countries: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    age_min: int | None = None
    age_max: int | None = None
    genders: tuple[str, ...] = ()
    education_levels: tuple[str, ...] = ()
    label: str = ""

    def is_unrestricted(self) -> bool:
        return not (
            self.countries or self.regions
            or self.age_min is not None or self.age_max is not None
            or self.genders or self.education_levels
        )

    def validate(self) -> None:
        """Raise ValueError on any filter value the data layer cannot honor."""
        lo = self.age_min if self.age_min is not None else _AGE_FLOOR
        hi = self.age_max if self.age_max is not None else _AGE_CEIL
        if lo > hi:
            raise ValueError(f"age_min ({lo}) must be <= age_max ({hi})")
        for g in self.genders:
            if g not in VALID_GENDERS:
                raise ValueError(f"unknown gender {g!r} (valid: {VALID_GENDERS})")
        for e in self.education_levels:
            if e not in VALID_EDUCATION_LEVELS:
                raise ValueError(
                    f"unknown education level {e!r} (valid: {VALID_EDUCATION_LEVELS})"
                )
        self.resolve_countries()

    def resolve_countries(self) -> list[dict]:
        """Return the candidate country dicts, validating ISO2/region names."""
        all_countries = load_countries()
        if not self.countries and not self.regions:
            return list(all_countries)
        by_iso = {c["iso2"]: c for c in all_countries}
        known_regions = {c["region"] for c in all_countries}
        for iso in self.countries:
            if iso not in by_iso:
                raise ValueError(f"unknown country ISO2 {iso!r}")
        for region in self.regions:
            if region not in known_regions:
                raise ValueError(f"unknown region {region!r} (valid: {sorted(known_regions)})")
        picked: dict[str, dict] = {iso: by_iso[iso] for iso in self.countries}
        for c in all_countries:
            if c["region"] in self.regions:
                picked.setdefault(c["iso2"], c)
        return list(picked.values())

    def describe(self) -> str:
        if self.label:
            return self.label
        if self.is_unrestricted():
            return "global"
        parts: list[str] = []
        if self.countries:
            parts.append("+".join(self.countries))
        if self.regions:
            parts.append("+".join(self.regions))
        if self.age_min is not None or self.age_max is not None:
            lo = self.age_min if self.age_min is not None else _AGE_FLOOR
            hi = self.age_max if self.age_max is not None else _AGE_CEIL
            parts.append(f"{lo}-{hi}")
        if self.genders:
            parts.append("/".join(self.genders))
        if self.education_levels:
            parts.append("/".join(self.education_levels))
        return ", ".join(parts)
