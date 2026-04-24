"""Select the best available astro engine.

Default preference order:
    1. kerykeion  (Swiss Ephemeris, Placidus, Chiron) — needs MSVC on Windows
    2. skyfield   (JPL DE421, Equal House)            — Phase 1 default
"""

from __future__ import annotations

from realm.core.exceptions import AstroCalculationError
from realm.core.logging import get_logger

from .interfaces import IAstroEngine

logger = get_logger(__name__)


def get_astro_engine(backend: str = "auto") -> IAstroEngine:
    """Return a ready-to-use IAstroEngine instance.

    Args:
        backend: "auto" | "kerykeion" | "skyfield".
    """
    if backend == "kerykeion":
        from .kerykeion_engine import KerykeionEngine
        return KerykeionEngine()

    if backend == "skyfield":
        from .skyfield_engine import SkyfieldEngine
        return SkyfieldEngine()

    if backend == "auto":
        try:
            from .kerykeion_engine import KerykeionEngine
            engine = KerykeionEngine()
            logger.info("Using Kerykeion astrological backend")
            return engine
        except AstroCalculationError:
            from .skyfield_engine import SkyfieldEngine
            logger.info("Kerykeion unavailable; using Skyfield backend")
            return SkyfieldEngine()

    raise AstroCalculationError(f"Unknown astro backend: {backend!r}")
