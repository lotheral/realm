"""Sprint 18 — pytest hermeticity guard.

Sprint 17 added module-level ``load_dotenv`` to ``realm/api/predict.py``
so realm_start.bat picks up LLM keys without an extra launcher. That
load also injects ``REALM_LLM_CATEGORY_BACKEND=1`` into ``os.environ``
when ``.env`` is present, which would silently flip the entire test
suite into LLM-active mode — breaking calibration regression
(geopolitics 49.20%) and routing tests that assume keyword-only behavior.

This conftest pops the LLM-gate env var BEFORE any realm.* import so
tests stay hermetic by default. Tests that explicitly want LLM-active
behavior should construct their own router with an injected
``MockLLMBackend`` (the pattern used by Sprint 17's analyzer tests).
"""

from __future__ import annotations

import os

# Ran at pytest startup, before test collection.
# Set to empty string (not pop) so the subsequent dotenv auto-load in
# realm/api/predict.py treats the var as "already present" under
# override=False semantics and does NOT re-inject the .env value.
os.environ["REALM_LLM_CATEGORY_BACKEND"] = ""
