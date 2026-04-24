"""Agent model and factory interfaces.

Phase 2 Agent = DemographicProfile + NatalChart + TraitVector.
Phase 3 will add memory + decision policy fields.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from realm.core.types import NatalChart
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector


@dataclass(frozen=True, slots=True)
class Agent:
    """Static composition of a REALM agent. Phase 2 scope — no behaviour yet."""

    profile: DemographicProfile
    # Optional: None when a non-astrological InputAdapter produced the traits
    # (e.g. BigFiveAdapter from questionnaire scores, DemographicAdapter from
    # Hofstede-only). Consumers that read natal_chart must guard against None.
    natal_chart: NatalChart | None
    traits: TraitVector

    @property
    def agent_id(self) -> str:
        return self.profile.agent_id

    def short_label(self) -> str:
        return self.profile.short_label()


class IAgentFactory(ABC):
    @abstractmethod
    def build(self, profile: DemographicProfile) -> Agent:
        """Materialize a single agent from a demographic profile."""

    @abstractmethod
    def build_batch(
        self, profiles: list[DemographicProfile],
    ) -> list[Agent]:
        """Build agents for a whole batch. Bad charts are skipped with a warning."""
