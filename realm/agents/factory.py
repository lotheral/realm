"""Default AgentFactory.

Composes: DemographicProfile -> NatalChart (IAstroEngine) -> TraitVector
(IPersonalityEmbedder) -> TraitVector with culture (ICulturalModifier) -> Agent.

Birth data that falls outside the astro engine's ephemeris range (e.g. pre-1899
with DE421) raises AstroCalculationError and is skipped in batch mode.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from realm.astro.factory import get_astro_engine
from realm.astro.interfaces import IAstroEngine
from realm.core.exceptions import AstroCalculationError
from realm.core.logging import get_logger
from realm.culture.interfaces import ICulturalModifier
from realm.culture.modifier import CulturalModifier
from realm.demographics.interfaces import DemographicProfile
from realm.personality.embedder import get_personality_embedder
from realm.personality.interfaces import IPersonalityEmbedder

if TYPE_CHECKING:
    from realm.personality.adapters import IInputAdapter
    from realm.personality.calibration import TraitCalibrator

from .interfaces import Agent, IAgentFactory

logger = get_logger(__name__)


def _seed_from_agent_id(agent_id: str) -> int:
    """Derive a stable 32-bit seed from an agent_id string."""
    digest = hashlib.blake2b(str(agent_id).encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big")


class AgentFactory(IAgentFactory):
    def __init__(
        self,
        astro_engine: IAstroEngine | None = None,
        embedder: IPersonalityEmbedder | None = None,
        cultural_modifier: ICulturalModifier | None = None,
        calibrator: TraitCalibrator | None = None,
        adapter: IInputAdapter | None = None,
        *,
        seed_offsets: dict[str, float] | None = None,
    ) -> None:
        self._astro = astro_engine or get_astro_engine("auto")
        self._embedder = embedder or get_personality_embedder("rule_based")
        self._culture = cultural_modifier or CulturalModifier()
        # Adapter must be set BEFORE the default calibrator so the latter can
        # pick up adapter-aware stats path via adapter_type.
        if adapter is None:
            from realm.personality.adapters import AstrologicalAdapter
            # Default wraps the existing embedder so behavior is unchanged.
            adapter = AstrologicalAdapter(self._embedder)
        self._adapter = adapter
        if calibrator is None:
            from realm.personality.calibration import TraitCalibrator
            calibrator = TraitCalibrator(adapter_type=self._adapter.adapter_type)
        self._calibrator = calibrator
        # Sprint 14 WP2: optional category-aware trait nudges applied after
        # the political_spectrum override. Validation of zero-sum + magnitude
        # is enforced at config-load time by CategoryRouter._validate_categories;
        # we still clamp per-trait to [0, 1] here as a runtime safety net.
        self._seed_offsets: dict[str, float] = dict(seed_offsets or {})

    def build(self, profile: DemographicProfile) -> Agent:
        from realm.core.exceptions import PersonalityEmbeddingError
        from realm.core.types import NatalChart

        chart: NatalChart | None = None
        at = self._adapter.adapter_type
        if at == "astrological":
            chart = self._astro.calculate_natal_chart(
                birth_dt=profile.birth_datetime,
                latitude=profile.birth_latitude,
                longitude=profile.birth_longitude,
                timezone=profile.birth_timezone,
            )
            raw = self._adapter.build(chart)
        elif at == "big_five":
            scores = profile.big_five_scores
            if scores is None:
                raise PersonalityEmbeddingError(
                    f"BigFiveAdapter needs profile.big_five_scores "
                    f"but profile {profile.agent_id} has none",
                )
            raw = self._adapter.build(scores)
        elif at == "demographic":
            raw = self._adapter.build(profile)
        elif at == "blended":
            from realm.personality.adapters import BlendedInput
            component_types = {c.adapter_type for c in self._adapter.components}
            if "astrological" in component_types:
                chart = self._astro.calculate_natal_chart(
                    birth_dt=profile.birth_datetime,
                    latitude=profile.birth_latitude,
                    longitude=profile.birth_longitude,
                    timezone=profile.birth_timezone,
                )
            bf_scores = (
                profile.big_five_scores
                if "big_five" in component_types
                else None
            )
            if "big_five" in component_types and bf_scores is None:
                raise PersonalityEmbeddingError(
                    f"BlendedAdapter with big_five component needs "
                    f"profile.big_five_scores but profile "
                    f"{profile.agent_id} has none",
                )
            blended_input = BlendedInput(
                natal_chart=chart,
                big_five_scores=bf_scores,
                demographic_profile=(
                    profile if "demographic" in component_types else None
                ),
                agent_seed=_seed_from_agent_id(profile.agent_id),
            )
            raw = self._adapter.build(blended_input)
        else:
            raise PersonalityEmbeddingError(
                f"unsupported adapter_type {at!r}",
            )

        cultured = (
            self._culture.apply(raw, profile)
            if self._adapter.applies_cultural_modifier
            else raw
        )
        calibrated = self._calibrator.apply(cultured)
        # Sprint 12: country-level political_spectrum override fires LAST so
        # every adapter path (astrological / big_five / blended / demographic)
        # exhibits Hofstede pdi+idv proxy variance instead of the TraitVector
        # default 0.5. The production default adapter is AstrologicalAdapter,
        # which leaves political_spectrum at 0.5 by design. This override is
        # the single source of truth for the trait once an Agent is built.
        from dataclasses import replace as _replace_dc

        from realm.personality.adapters.demographic import (
            _political_spectrum_from_hofstede,
        )
        final_traits = _replace_dc(
            calibrated,
            political_spectrum=_political_spectrum_from_hofstede(profile.country),
        )
        # Sprint 14 WP2: category-aware seed offsets, applied AFTER the
        # political_spectrum override so the per-country variance is
        # preserved. Each offset is added to the current trait value and
        # clamped to [0, 1].
        if self._seed_offsets:
            updates: dict[str, float] = {}
            for trait, offset in self._seed_offsets.items():
                current = float(getattr(final_traits, trait, 0.5))
                updates[trait] = max(0.0, min(1.0, current + float(offset)))
            if updates:
                final_traits = _replace_dc(final_traits, **updates)
        return Agent(profile=profile, natal_chart=chart, traits=final_traits)

    def build_batch(
        self, profiles: list[DemographicProfile],
    ) -> list[Agent]:
        agents: list[Agent] = []
        skipped = 0
        for p in profiles:
            try:
                agents.append(self.build(p))
            except AstroCalculationError as e:
                skipped += 1
                logger.warning("Skipping %s (%s): %s", p.agent_id, p.country, e)
        if skipped:
            logger.warning(
                "AgentFactory: %d of %d profiles skipped due to astro errors",
                skipped, len(profiles),
            )
        return agents
