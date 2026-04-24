"""Structured logging helpers for REALM.

All REALM loggers live under the "realm" namespace. Use get_logger(__name__)
inside modules for automatic hierarchical naming.
"""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def setup_logging(level: str | None = None, *, force: bool = False) -> None:
    """Configure root logging once.

    Safe to call multiple times — subsequent calls are no-ops unless force=True.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    lvl_name = (level or os.environ.get("REALM_LOG_LEVEL", "INFO")).upper()
    lvl = getattr(logging, lvl_name, logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-7s  %(name)-32s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(lvl)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a REALM-namespaced logger.

    If `name` starts with 'realm' it is used verbatim; otherwise it is prefixed.
    """
    if name == "realm" or name.startswith("realm."):
        return logging.getLogger(name)
    return logging.getLogger(f"realm.{name}")
