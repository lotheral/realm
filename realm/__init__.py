"""REALM — population-reaction simulation engine.

Simulates a per-question target population (personality-diverse agents
built from pluggable adapters) to project how opinions and tendencies
shift in reaction to events.
"""

from importlib.metadata import PackageNotFoundError, version

# Sprint 20: single source of truth is pyproject.toml — four files used to
# carry four different hardcoded version numbers (0.1.0 / 0.19.2 / 0.2.0 /
# 0.10.0). The fallback covers running from a raw checkout without an
# editable install.
try:
    __version__ = version("realm")
except PackageNotFoundError:  # pragma: no cover - raw checkout
    __version__ = "0.0.0.dev0"
