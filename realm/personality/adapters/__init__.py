"""Input adapter package — pluggable trait sources.

Each adapter transforms a domain-specific input into a 24-trait TraitVector.
AstrologicalAdapter wraps the existing IPersonalityEmbedder; BigFiveAdapter
and DemographicAdapter are peer classes. BlendedAdapter combines two or more
of the above with weighted averaging plus optional per-agent Gaussian noise.
"""

from __future__ import annotations

from .astrological import AstrologicalAdapter
from .big_five import BigFiveAdapter
from .blended import BlendedAdapter, BlendedComponent, BlendedInput
from .demographic import DemographicAdapter
from .factory import get_input_adapter
from .interfaces import IInputAdapter

__all__ = [
    "AstrologicalAdapter",
    "BigFiveAdapter",
    "BlendedAdapter",
    "BlendedComponent",
    "BlendedInput",
    "DemographicAdapter",
    "IInputAdapter",
    "get_input_adapter",
]
