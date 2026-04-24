"""AstroCore interface contracts.

The IAstroEngine ABC is the single source of truth for natal chart and transit
calculations. Concrete implementations (Kerykeion, Skyfield, fixture-based) live
next to this file and are selected via `realm.astro.factory.get_astro_engine()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from realm.core.types import NatalChart, TransitSnapshot


class IAstroEngine(ABC):
    """Astrological calculation engine."""

    @abstractmethod
    def calculate_natal_chart(
        self,
        birth_dt: datetime,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> NatalChart:
        """Compute a full natal chart.

        Args:
            birth_dt: timezone-aware birth datetime. Naive datetimes are rejected.
            latitude: degrees, north positive, range [-90, 90]
            longitude: degrees, east positive, range [-180, 180]
            timezone: IANA timezone string (e.g. "Europe/Istanbul")

        Raises:
            AstroCalculationError: bad birth data or ephemeris computation failed.
        """

    @abstractmethod
    def calculate_transits(
        self,
        natal: NatalChart,
        target_dt: datetime,
    ) -> TransitSnapshot:
        """Compute transits at a given moment against a natal chart."""

    @abstractmethod
    def calculate_transit_range(
        self,
        natal: NatalChart,
        start_dt: datetime,
        end_dt: datetime,
        interval_hours: int = 24,
    ) -> list[TransitSnapshot]:
        """Compute a time series of transit snapshots."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Backend identifier, e.g. 'kerykeion', 'skyfield', 'fixture'."""
