"""REALM exception hierarchy."""

from __future__ import annotations


class REALMError(Exception):
    """Base class for every REALM-specific error."""


class ConfigError(REALMError):
    """Configuration file missing, malformed, or invalid."""


class DataError(REALMError):
    """Static data (JSON mappings, seed lists) missing or malformed."""


class AstroCalculationError(REALMError):
    """Natal or transit computation failed (bad birth data, ephemeris miss, etc.)."""


class PersonalityEmbeddingError(REALMError):
    """Converting a natal chart to a TraitVector failed."""
