"""DemographicAdapter — Hofstede + religion + region as PRIMARY trait source.

Differs from CulturalModifier (which applies demographic signal as a small
additive overlay at blend_ratio=0.3). This adapter uses the same
compose_modifiers() result but at full magnitude, treating demographic data
as the primary signal rather than a secondary nudge. Consequently, AgentFactory
does NOT apply CulturalModifier after this adapter — doing so would
double-count Hofstede.
"""

from __future__ import annotations

from typing import Any

from realm.core.exceptions import PersonalityEmbeddingError
from realm.culture.modifier import compose_modifiers
from realm.demographics.country_data import get_hofstede, get_vdem
from realm.demographics.interfaces import DemographicProfile
from realm.personality.trait_vector import TraitVector

from .interfaces import IInputAdapter

# Coefficients for the political_spectrum offset derived from Hofstede pdi+idv.
# These produce variance across countries WITHOUT claiming left/right labels —
# the goal is dispersion in how agents respond to political stimuli, not a
# polarization measurement. Calibrated to keep the 66-country range roughly
# inside [0.32, 0.68] (a ~0.36 spread vs the prior 0.0).
_PS_PDI_COEFF = 0.35
_PS_IDV_COEFF = 0.25

# Sprint 14 WP3: V-Dem blend weights. The Hofstede component preserves the
# Sprint 11 production coefficients exactly — the V-Dem term is added on top
# at 40% weight to widen spread while keeping the Hofstede baseline a strong
# anchor.
#
# Semantic alignment: in the existing Hofstede formulation, HIGH
# political_spectrum is the authority-compliant pole (high PDI, low IDV).
# V-Dem libdem points the OPPOSITE way (high libdem = liberal democracy).
# To stack them rather than cancel them, the V-Dem contribution is inverted
# (`1 - libdem`) so authoritarian regimes pull political_spectrum UP and
# liberal democracies pull it DOWN — matching the Hofstede direction.
_PS_HOFSTEDE_WEIGHT = 0.6
_PS_VDEM_WEIGHT = 0.4

# Module-level toggle for the V-Dem blend. Tests can flip this off to assert
# the Sprint 11 Hofstede-only baseline still computes; production code paths
# (AgentFactory + DemographicAdapter) consult the same flag so they stay in
# sync without per-call plumbing.
_USE_VDEM_BLEND = True


def _political_spectrum_from_hofstede(country: str, *, use_vdem: bool | None = None) -> float:
    """Return a political_spectrum value in [0, 1] for the given ISO2 country.

    Sprint 11 (Hofstede-only): High PDI (authority-respecting) and low IDV
    (collectivist) shift toward the authority-compliant pole; low PDI / high
    IDV shifts the other way. Production coefficients (0.35 / 0.25) are
    preserved bit-for-bit.

    Sprint 14 WP3 (Hofstede + V-Dem blend): when ``use_vdem`` is True (the
    module default), the Hofstede value is blended 60/40 with `1 - V-Dem
    libdem` for the same country. The inversion matters: in the Hofstede
    formula HIGH political_spectrum is the authority-compliant pole, and
    high libdem indicates a liberal democracy — the OPPOSITE pole. By using
    `1 - libdem` the two signals stack instead of cancel, widening
    dispersion. Pass ``use_vdem=False`` to fall back to the Sprint 11
    Hofstede-only formula (used by the regression test suite).
    """
    enable_vdem = _USE_VDEM_BLEND if use_vdem is None else bool(use_vdem)
    scores = get_hofstede(country)
    pdi = float(scores.get("pdi", 50)) / 100.0
    idv = float(scores.get("idv", 50)) / 100.0
    delta = _PS_PDI_COEFF * (pdi - 0.5) - _PS_IDV_COEFF * (idv - 0.5)
    hofstede_ps = max(0.0, min(1.0, 0.5 + delta))
    if not enable_vdem:
        return hofstede_ps
    vdem = get_vdem(country)
    libdem = max(0.0, min(1.0, float(vdem.get("libdem", 0.5))))
    vdem_ps = 1.0 - libdem  # invert so authoritarian → high, liberal → low
    blended = _PS_HOFSTEDE_WEIGHT * hofstede_ps + _PS_VDEM_WEIGHT * vdem_ps
    return max(0.0, min(1.0, blended))


# Public alias — Sprint 14 WP3 documented name; the underscore-prefixed alias
# above is preserved as the import path used by AgentFactory + tests.
_political_spectrum_for_country = _political_spectrum_from_hofstede


class DemographicAdapter(IInputAdapter):
    """Build a TraitVector from a DemographicProfile alone.

    Sprint 14 WP3: ``__init__(use_vdem=True)`` routes the political_spectrum
    override through the V-Dem blend (60% Hofstede pdi+idv proxy + 40%
    V-Dem libdem). Pass ``use_vdem=False`` to revert to the Sprint 11
    Hofstede-only baseline; this is also exercised by the regression tests.
    """

    def __init__(self, *, use_vdem: bool = True) -> None:
        self._use_vdem = use_vdem

    def build(self, input_data: Any) -> TraitVector:
        if not isinstance(input_data, DemographicProfile):
            raise PersonalityEmbeddingError(
                f"DemographicAdapter expects DemographicProfile, got {type(input_data).__name__}",
            )
        # Start at neutral 0.5 and apply compose_modifiers at FULL weight.
        # TraitVector.from_dict clamps to [0, 1].
        neutral = dict.fromkeys(TraitVector.trait_names(), 0.5)
        deltas = compose_modifiers(input_data)
        for trait, delta in deltas.items():
            if trait in neutral:
                neutral[trait] += float(delta)
        # Sprint 11: political_spectrum gets a country-level baseline derived
        # from Hofstede pdi + idv. compose_modifiers() does NOT touch this trait
        # because the planet/Hofstede coefficient tables omit it by design;
        # without this override every agent worldwide would stay at 0.5.
        # Sprint 14 WP3: optionally blends in V-Dem libdem at 40% weight.
        neutral["political_spectrum"] = _political_spectrum_from_hofstede(
            input_data.country, use_vdem=self._use_vdem,
        )
        return TraitVector.from_dict(neutral)

    @property
    def adapter_type(self) -> str:
        return "demographic"

    @property
    def applies_cultural_modifier(self) -> bool:
        # Hofstede is the primary signal here; applying CulturalModifier
        # after would re-add the same delta at blend_ratio * 0.3.
        return False
