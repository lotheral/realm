"""BlendedAdapter — weighted blend of multiple IInputAdapter outputs.

Rationale: single adapters hit a variance ceiling (~0.068 std on derived
traits). Blending two or more adapters on independent signal sources lifts
per-agent trait variance. A deterministic Gaussian noise layer keyed on
agent_seed further decorrelates adapters whose lookups are coarse-grained
(e.g., DemographicAdapter's country-level Hofstede lookup).

Input is a BlendedInput composite dataclass carrying one payload per possible
component (natal_chart for astrological, big_five_scores for big_five,
demographic_profile for demographic). AgentFactory assembles it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from realm.core.exceptions import PersonalityEmbeddingError
from realm.core.types import NatalChart
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector

from .interfaces import IInputAdapter


@dataclass(frozen=True, slots=True)
class BlendedInput:
    """Composite input carrying one payload per possible component adapter.

    AgentFactory populates the fields that correspond to configured
    components; unused fields stay None and their components are skipped
    (with weight renormalization on the remaining present components).
    """

    natal_chart: NatalChart | None = None
    big_five_scores: Mapping[str, float] | None = None
    demographic_profile: DemographicProfile | None = None
    agent_seed: int | None = None


_COMPONENT_FIELD: dict[str, str] = {
    "astrological": "natal_chart",
    "big_five": "big_five_scores",
    "demographic": "demographic_profile",
}


@dataclass(frozen=True, slots=True)
class BlendedComponent:
    """A single component within a blend: its adapter and its weight."""

    adapter: IInputAdapter
    weight: float

    @property
    def adapter_type(self) -> str:
        return self.adapter.adapter_type


class BlendedAdapter(IInputAdapter):
    """Weighted blend of multiple IInputAdapter outputs, with optional noise.

    Args:
        components: list of (adapter, weight) pairs. Weights may sum to any
            positive value; they are normalized across the components whose
            corresponding input field is populated at build() time.
        noise_sigma: per-trait Gaussian noise magnitude, applied AFTER blend.
            Set to 0.0 to disable noise entirely.
    """

    def __init__(
        self,
        components: list[BlendedComponent],
        noise_sigma: float = 0.05,
    ) -> None:
        if not components:
            raise PersonalityEmbeddingError(
                "BlendedAdapter requires at least one component",
            )
        for c in components:
            if c.weight <= 0:
                raise PersonalityEmbeddingError(
                    f"BlendedAdapter component {c.adapter_type!r} has "
                    f"non-positive weight {c.weight}",
                )
            if c.adapter_type not in _COMPONENT_FIELD:
                raise PersonalityEmbeddingError(
                    f"BlendedAdapter does not know how to route input for "
                    f"adapter_type {c.adapter_type!r}",
                )
        self._components = list(components)
        self._noise_sigma = float(noise_sigma)

    @property
    def adapter_type(self) -> str:
        return "blended"

    @property
    def applies_cultural_modifier(self) -> bool:
        # If any component opts out of cultural modifier (e.g. DemographicAdapter,
        # which bakes Hofstede in directly), the blend as a whole must opt out
        # to avoid double-counting cultural signal.
        return all(c.adapter.applies_cultural_modifier for c in self._components)

    @property
    def noise_sigma(self) -> float:
        return self._noise_sigma

    @property
    def components(self) -> tuple[BlendedComponent, ...]:
        return tuple(self._components)

    def build(self, input_data: Any) -> TraitVector:
        if not isinstance(input_data, BlendedInput):
            raise PersonalityEmbeddingError(
                f"BlendedAdapter expects BlendedInput, got "
                f"{type(input_data).__name__}",
            )

        trait_names = TraitVector.trait_names()

        # 1. Run each component whose input field is populated, collecting
        #    (trait_dict, weight) pairs.
        per_component: list[tuple[dict[str, float], float]] = []
        for component in self._components:
            field = _COMPONENT_FIELD[component.adapter_type]
            payload = getattr(input_data, field)
            if payload is None:
                continue
            tv = component.adapter.build(payload)
            per_component.append((tv.to_dict(), component.weight))

        if not per_component:
            raise PersonalityEmbeddingError(
                "BlendedAdapter received BlendedInput with no populated "
                "component fields; at least one must be provided",
            )

        # 2. Normalize weights of PRESENT components so they sum to 1.0.
        total_weight = sum(w for _, w in per_component)
        normalized = [(td, w / total_weight) for td, w in per_component]

        # 3. Per-trait weighted average.
        blended: dict[str, float] = {}
        for trait in trait_names:
            blended[trait] = sum(td.get(trait, 0.5) * w for td, w in normalized)

        # 4. Optional Gaussian noise (deterministic via agent_seed).
        if self._noise_sigma > 0 and input_data.agent_seed is not None:
            rng = np.random.default_rng(int(input_data.agent_seed))
            for trait in trait_names:
                blended[trait] += float(rng.normal(0.0, self._noise_sigma))

        # 5. TraitVector.from_dict clamps to [0, 1].
        return TraitVector.from_dict(blended)
