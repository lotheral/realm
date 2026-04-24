"""Checkpoint / resume.

Determinism contract: given (master_seed, n_agents, sim_epoch) the demographic
population and astro charts are reproducible. Therefore a checkpoint only needs
to save mutable simulation state:

    - current tick
    - history list
    - post counter
    - full platform state (posts, engagements, per-tick indexes)

Resume rebuilds the reproducible layers (agents, network, modulator) and
restores the mutable layers from the saved file.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from realm.core.logging import get_logger
from realm.simulation.engine import SimulationEngine

logger = get_logger(__name__)


CHECKPOINT_VERSION = 1


@dataclass
class CheckpointPayload:
    """Serializable envelope stored on disk."""

    version: int
    master_seed: int
    n_agents: int
    tick: int
    post_counter: int
    history: list[Any]                # list[TickStats]
    platform_states: list[dict[str, Any]]


def save(sim: SimulationEngine, path: str | Path) -> Path:
    """Write `sim`'s mutable state to `path`. Returns the resolved path.

    The file is a pickled CheckpointPayload — readable only via load().
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    payload = CheckpointPayload(
        version=CHECKPOINT_VERSION,
        master_seed=sim.clock.master_seed,
        n_agents=len(sim.agents),
        tick=sim.clock.tick,
        post_counter=sim._post_counter,
        history=list(sim.history),
        platform_states=[_serialize_platform(pl) for pl in sim.platforms],
    )
    with p.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Checkpoint saved: tick=%d → %s", sim.clock.tick, p)
    return p


def load(path: str | Path) -> CheckpointPayload:
    """Read a checkpoint file. Does not construct a SimulationEngine — the caller
    rebuilds agents/network/modulator/platforms from master_seed and then calls
    `restore_into()`.
    """
    p = Path(path)
    with p.open("rb") as f:
        payload = pickle.load(f)
    if not isinstance(payload, CheckpointPayload):
        raise ValueError(f"not a REALM checkpoint: {p}")
    if payload.version != CHECKPOINT_VERSION:
        raise ValueError(
            f"checkpoint version mismatch: file={payload.version} "
            f"code={CHECKPOINT_VERSION}"
        )
    return payload


def restore_into(sim: SimulationEngine, payload: CheckpointPayload) -> None:
    """Patch a freshly-built SimulationEngine with saved mutable state.

    Preconditions:
        - sim built with same master_seed and n_agents as the saved payload.
        - sim.clock already at tick 0.
        - Same number of platforms in the same order.
    """
    if sim.clock.master_seed != payload.master_seed:
        raise ValueError(
            f"master_seed mismatch: sim={sim.clock.master_seed} "
            f"checkpoint={payload.master_seed}"
        )
    if len(sim.agents) != payload.n_agents:
        raise ValueError(
            f"agent count mismatch: sim={len(sim.agents)} "
            f"checkpoint={payload.n_agents}"
        )
    if len(sim.platforms) != len(payload.platform_states):
        raise ValueError(
            f"platform count mismatch: sim={len(sim.platforms)} "
            f"checkpoint={len(payload.platform_states)}"
        )

    sim.clock.tick = payload.tick
    sim._post_counter = payload.post_counter
    sim.history = list(payload.history)
    for plat, state in zip(sim.platforms, payload.platform_states, strict=True):
        _restore_platform(plat, state)
    logger.info("Checkpoint restored: tick=%d", sim.clock.tick)


# ---- Platform serialization helpers ---------------------------------------
# Platforms currently have simple dataclass fields. Pickle the relevant
# attributes directly; skip _tick_window (deque, reconstructed on first advance).

def _serialize_platform(platform) -> dict[str, Any]:
    from collections import deque
    state = {}
    for attr, value in platform.__dict__.items():
        # Convert deque back to plain list for portability
        if isinstance(value, deque):
            state[attr] = list(value)
        else:
            state[attr] = value
    return state


def _restore_platform(platform, state: dict[str, Any]) -> None:
    from collections import deque
    for attr, value in state.items():
        if attr == "_tick_window":
            # Rebuild deque with the original maxlen
            maxlen = getattr(platform, "memory_ticks", 5)
            platform._tick_window = deque(value, maxlen=maxlen)
        else:
            setattr(platform, attr, value)
