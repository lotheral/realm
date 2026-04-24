"""DemographicEngine interface + DemographicProfile dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DemographicProfile:
    """Complete demographic record for a single agent."""

    agent_id: str

    # Identity
    name_first: str
    name_last: str
    gender: str                     # "M" | "F" | "X"

    # Geography & birth
    country: str                    # ISO2
    city: str
    birth_datetime: datetime        # tz-aware
    birth_latitude: float
    birth_longitude: float
    birth_timezone: str

    # Socioeconomic
    age_years: int
    profession_code: str
    profession_name: str
    income_annual_usd: float
    education_level: str            # "primary" | "secondary" | "bachelor" | "graduate"

    # Marginality (decision #8 — expert distribution, 3 modes)
    marginal_flag: bool
    marginal_category: str | None

    # Cultural references
    primary_religion: str
    region: str

    # Optional questionnaire-provided Big Five scores (for BigFiveAdapter path).
    # None when agent was generated demographically without a questionnaire.
    big_five_scores: Mapping[str, float] | None = None

    def short_label(self) -> str:
        return f"{self.name_first} {self.name_last} ({self.age_years}y, {self.city}/{self.country})"


class IDemographicGenerator(ABC):
    """Produce a batch of DemographicProfiles reproducibly from a master seed."""

    @abstractmethod
    def generate(self, n_agents: int) -> list[DemographicProfile]:
        ...
