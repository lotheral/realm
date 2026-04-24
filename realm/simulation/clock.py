"""Simulation clock.

Advances discrete ticks mapping to real-world time intervals. Tick 0 = `epoch`.
Tick_interval is configured in realm.yaml (`"1h"` | `"4h"` | `"1d"`).

Deterministic: given (epoch, tick_interval, tick), sim_time is a pure function.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from realm.core.config import derive_seed, load_realm_config

_INTERVAL_MAP: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


def parse_interval(s: str) -> timedelta:
    if s in _INTERVAL_MAP:
        return _INTERVAL_MAP[s]
    raise ValueError(f"Unsupported tick_interval {s!r}; choose from {list(_INTERVAL_MAP)}")


@dataclass
class Clock:
    """Mutable simulation clock. One instance per SimulationEngine."""

    epoch: datetime
    interval: timedelta
    tick: int = 0
    master_seed: int = 42
    _rng_cache: dict[str, random.Random] = field(default_factory=dict, repr=False)

    @classmethod
    def from_config(
        cls,
        epoch: datetime | None = None,
        config: dict | None = None,
    ) -> Clock:
        cfg = config or load_realm_config()
        sim = cfg["realm"]["simulation"]
        interval = parse_interval(sim.get("tick_interval", "1d"))
        master_seed = int(sim.get("master_seed", 42))
        e = epoch or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        return cls(epoch=e, interval=interval, master_seed=master_seed)

    @property
    def sim_time(self) -> datetime:
        """Wall-clock time corresponding to the current tick."""
        return self.epoch + self.interval * self.tick

    def advance(self, n: int = 1) -> None:
        if n < 1:
            raise ValueError("advance(n) requires n>=1")
        self.tick += n
        # Tick-local RNG cache must be invalidated on advance so tick-level
        # subsystems re-derive their per-tick random streams.
        self._rng_cache.clear()

    def rng(self, subsystem: str) -> random.Random:
        """Return a deterministic Random seeded from (master_seed, tick, subsystem).

        Cached within a tick so callers asking twice get the same stream — no
        risk of double-drawing from a misused RNG.
        """
        if subsystem not in self._rng_cache:
            key = f"{self.tick}:{subsystem}"
            seed = derive_seed(self.master_seed, key)
            self._rng_cache[subsystem] = random.Random(seed)
        return self._rng_cache[subsystem]
