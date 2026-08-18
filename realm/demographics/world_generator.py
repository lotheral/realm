"""WorldGenerator — produces a reproducible batch of DemographicProfiles.

Determinism contract:
    Given (master_seed, sim_epoch, n_agents) the output is byte-identical.

Sampling pipeline per agent:
    1. Sample country weighted by national population.
    2. Sample city within country weighted by city population.
    3. Apply rural offset with probability `rural_ratio` (decision #7).
    4. Sample age from country median (truncated normal, clamped to [18, 90]).
    5. Sample gender (49/49/2 M/F/X).
    6. Sample profession with age gates + country-tier adjustments.
    7. Sample income log-normally from (country_gdp * profession_multiplier).
    8. Sample education weighted by country tier.
    9. Sample marginal flag (decision #8: 2% expert / 4% outlier / 4% influencer).
   10. Generate country-appropriate name (Faker + fallback JSON pools).
   11. Sample birth datetime: hour from realistic distribution; year = epoch-age.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from realm.core.config import derive_seed, load_realm_config
from realm.core.logging import get_logger

from .country_data import (
    get_cities_for,
    get_country,
    load_birth_hour_weights,
    load_countries,
)
from .interfaces import DemographicProfile, IDemographicGenerator
from .name_generator import generate_name
from .population_spec import PopulationSpec
from .profession_generator import sample_profession
from .socioeconomic import (
    sample_age,
    sample_education,
    sample_gender,
    sample_income,
    sample_marginal,
)

logger = get_logger(__name__)


class WorldGenerator(IDemographicGenerator):
    def __init__(
        self,
        master_seed: int | None = None,
        sim_epoch: datetime | None = None,
        rural_ratio: float = 0.30,
        rural_offset_deg: float = 1.0,
        population_spec: PopulationSpec | None = None,
    ) -> None:
        if master_seed is None:
            cfg = load_realm_config()
            master_seed = int(cfg["realm"]["simulation"]["master_seed"])
        self._master_seed = master_seed
        self._epoch = sim_epoch or datetime(2026, 1, 1, tzinfo=UTC)
        self._rural_ratio = rural_ratio
        self._rural_offset = rural_offset_deg
        self._spec = population_spec

    def generate(self, n_agents: int) -> list[DemographicProfile]:
        if n_agents < 1:
            return []

        demo_seed = derive_seed(self._master_seed, "demographics")
        rng = random.Random(demo_seed)

        # Sprint 21: per-question target population. An unrestricted spec
        # resolves to the full country list, keeping RNG consumption and
        # output byte-identical to the no-spec pipeline.
        countries = (
            self._spec.resolve_countries() if self._spec is not None
            else load_countries()
        )
        country_isos = [c["iso2"] for c in countries]
        country_weights = [float(c["population"]) for c in countries]

        profiles: list[DemographicProfile] = []
        for i in range(n_agents):
            iso = rng.choices(country_isos, weights=country_weights, k=1)[0]
            profiles.append(self._generate_one(iso, rng, i))

        logger.info(
            "Generated %d agents across %d countries (master_seed=%d, demo_seed=%d)",
            len(profiles), len(countries), self._master_seed, demo_seed,
        )
        return profiles

    def _generate_one(
        self, iso2: str, rng: random.Random, agent_index: int,
    ) -> DemographicProfile:
        country = get_country(iso2)
        cities = get_cities_for(iso2)

        # City weighted by population
        city_weights = [float(c["pop"]) for c in cities]
        city = rng.choices(cities, weights=city_weights, k=1)[0]

        # Geography — rural offset applied to some agents
        lat = float(city["lat"])
        lon = float(city["lon"])
        if rng.random() < self._rural_ratio:
            lat += rng.uniform(-self._rural_offset, self._rural_offset)
            lon += rng.uniform(-self._rural_offset, self._rural_offset)
            lat = max(-90.0, min(90.0, lat))
            lon = ((lon + 180) % 360) - 180  # wrap to [-180, 180]

        # Demographic core (Sprint 21: constrained by PopulationSpec if set)
        age = self._constrained_age(iso2, rng)
        gender = self._constrained_gender(rng)
        profession = sample_profession(iso2, rng, age)
        income = sample_income(iso2, profession["income_multiplier"], rng)
        education = self._constrained_education(iso2, rng)
        marginal_flag, marginal_cat = sample_marginal(rng)
        first, last = generate_name(iso2, gender, rng)

        birth_dt = self._sample_birth_datetime(age, city["timezone"], rng)

        return DemographicProfile(
            agent_id=f"AGT_{agent_index:06d}",
            name_first=first,
            name_last=last,
            gender=gender,
            country=iso2,
            city=city["name"],
            birth_datetime=birth_dt,
            birth_latitude=lat,
            birth_longitude=lon,
            birth_timezone=city["timezone"],
            age_years=age,
            profession_code=profession["code"],
            profession_name=profession["name"],
            income_annual_usd=income,
            education_level=education,
            marginal_flag=marginal_flag,
            marginal_category=marginal_cat,
            primary_religion=country["primary_religion"],
            region=country["region"],
        )

    # Sprint 21: bounded rejection resampling against the PopulationSpec.
    # When the spec is None or the relevant filter is empty, the existing
    # sampler is called exactly once — identical RNG consumption keeps the
    # unrestricted path byte-identical to pre-Sprint-21 output.
    _MAX_RESAMPLE = 200

    def _constrained_age(self, iso2: str, rng: random.Random) -> int:
        spec = self._spec
        if spec is None or (spec.age_min is None and spec.age_max is None):
            return sample_age(iso2, rng)
        lo = spec.age_min if spec.age_min is not None else 18
        hi = spec.age_max if spec.age_max is not None else 90
        for _ in range(self._MAX_RESAMPLE):
            age = sample_age(iso2, rng)
            if lo <= age <= hi:
                return age
        return max(lo, min(hi, sample_age(iso2, rng)))

    def _constrained_gender(self, rng: random.Random) -> str:
        spec = self._spec
        if spec is None or not spec.genders:
            return sample_gender(rng)
        for _ in range(self._MAX_RESAMPLE):
            gender = sample_gender(rng)
            if gender in spec.genders:
                return gender
        return spec.genders[0]

    def _constrained_education(self, iso2: str, rng: random.Random) -> str:
        spec = self._spec
        if spec is None or not spec.education_levels:
            return sample_education(iso2, rng)
        for _ in range(self._MAX_RESAMPLE):
            education = sample_education(iso2, rng)
            if education in spec.education_levels:
                return education
        return spec.education_levels[0]

    def _sample_birth_datetime(
        self, age_years: int, tz_name: str, rng: random.Random,
    ) -> datetime:
        """Deterministic birth datetime. Age maps to birth year; hour weighted by
        realistic distribution; day clamped to 1-28 to avoid month-length issues."""
        hour_weights = load_birth_hour_weights()
        hour = rng.choices(range(24), weights=hour_weights, k=1)[0]
        minute = rng.randint(0, 59)
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        birth_year = self._epoch.year - age_years

        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning("Unknown timezone %r; falling back to UTC", tz_name)
            tz = UTC

        return datetime(birth_year, month, day, hour, minute, tzinfo=tz)
