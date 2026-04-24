"""YAML config + static data loading.

All paths default to the project's `config/` and `data/` directories. Tests can
override by passing absolute paths.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError, DataError

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"


def _resolve(path: str | Path, base: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def load_yaml(path: str | Path, base: Path = CONFIG_DIR) -> dict[str, Any]:
    """Load a YAML file. Returns {} if empty. Raises ConfigError if missing/invalid."""
    p = _resolve(path, base)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {p}: {e}") from e
    return data or {}


def load_json(path: str | Path, base: Path = DATA_DIR) -> Any:
    """Load a JSON file from the data/ directory."""
    p = _resolve(path, base)
    if not p.exists():
        raise DataError(f"Data file not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise DataError(f"Invalid JSON in {p}: {e}") from e


@lru_cache(maxsize=1)
def load_realm_config() -> dict[str, Any]:
    """Load config/realm.yaml (cached)."""
    return load_yaml("realm.yaml")


@lru_cache(maxsize=1)
def load_astrology_config() -> dict[str, Any]:
    """Load config/astrology.yaml (cached)."""
    return load_yaml("astrology.yaml")


def get_master_seed(config: dict[str, Any] | None = None) -> int:
    """Master seed. Environment REALM_MASTER_SEED overrides the config file."""
    env = os.environ.get("REALM_MASTER_SEED")
    if env:
        try:
            return int(env)
        except ValueError as e:
            raise ConfigError(f"REALM_MASTER_SEED must be int, got {env!r}") from e
    cfg = config if config is not None else load_realm_config()
    try:
        return int(cfg["realm"]["simulation"]["master_seed"])
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError("realm.simulation.master_seed missing in config") from e


def derive_seed(master_seed: int, subsystem: str) -> int:
    """Derive a per-subsystem seed from the master. Deterministic, collision-resistant.

    Uses Python's stable hash via hashlib so results are reproducible across runs
    (Python's built-in hash() is randomized for strings).
    """
    import hashlib
    h = hashlib.blake2b(f"{master_seed}:{subsystem}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big", signed=False) % (2**31 - 1)
