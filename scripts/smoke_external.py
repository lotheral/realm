"""External-surface smoke test — verify every third-party dependency REALM
talks to is still alive and shaped the way our code expects.

Run this first thing when reviving the project after a dormant period:

    python scripts/smoke_external.py

Checks (each degrades to a labelled FAIL, never raises):
  1. OpenAI API key valid + configured model id resolves
  2. Moonshot API key valid + configured model id resolves
  3. Tavily search key valid (1-result query)
  4. Polymarket Gamma API reachable + schema still parses into ResolvedMarket
  5. GeoNames account active (Kerykeion online geocoding)

Exit code: 0 if everything passed or was skipped, 1 if anything failed.
Cost: two ~1-token LLM calls + three free API hits, well under $0.01.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:  # pragma: no cover - dotenv is a declared dependency
    pass

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def _check_backend(backend_cls: type, key_env: str) -> tuple[str, str]:
    """Round-trip through REALM's own backend class so the smoke test
    exercises the exact production code path (param-name selection,
    temperature fallback, retries)."""
    if not os.getenv(key_env):
        return SKIP, f"no {key_env} in environment"
    try:
        backend = backend_cls()
        # 64 tokens: reasoning-family models (kimi-k2*) can burn a small
        # budget on hidden thinking and return empty content otherwise.
        resp = backend.complete("You are a ping responder.", "ping", max_tokens=64)
        model = getattr(backend, "_model", "?")
        return PASS, f"model '{model}' answered ({len(resp.content or '')} chars)"
    except Exception as exc:  # noqa: BLE001 - smoke test reports, never raises
        return FAIL, f"{type(exc).__name__}: {exc}"


def check_openai() -> tuple[str, str]:
    from realm.llm.openai_backend import OpenAIBackend

    return _check_backend(OpenAIBackend, "OPENAI_API_KEY")


def check_moonshot() -> tuple[str, str]:
    from realm.llm.openai_backend import MoonshotBackend

    return _check_backend(MoonshotBackend, "MOONSHOT_API_KEY")


def check_tavily() -> tuple[str, str]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return SKIP, "no TAVILY_API_KEY in environment"
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": "test", "max_results": 1},
            timeout=30.0,
        )
        if resp.status_code == 200:
            n = len(resp.json().get("results", []))
            return PASS, f"search ok ({n} result)"
        return FAIL, f"HTTP {resp.status_code}: {resp.text[:120]}"
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"{type(exc).__name__}: {exc}"


def check_polymarket() -> tuple[str, str]:
    """Reach Gamma AND exercise our schema-coupled parser end to end."""
    try:
        from realm.validation.polymarket import PolymarketClient

        client = PolymarketClient()
        markets = client.fetch_resolved_markets(
            limit=3, min_volume=10000.0, max_pages=2
        )
        if markets:
            return PASS, f"schema parses ({len(markets)} clean markets, e.g. {markets[0].question[:50]!r})"
        # Reachable-but-zero-parse is the exact silent failure mode we
        # documented — flag it loudly.
        raw = client.fetch_raw_closed_markets(limit=3)
        if raw:
            return FAIL, f"Gamma reachable but 0 of {len(raw)} raw markets parsed — SCHEMA DRIFT LIKELY"
        return FAIL, "Gamma returned no closed markets at all"
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        if "10054" in str(exc) or "ConnectError" in type(exc).__name__:
            detail += (
                " — TLS-level reset from this network; likely a regional ISP "
                "block (Polymarket is blocked in some countries). Set "
                "HTTPS_PROXY / use a VPN, or run backtests from a cloud host."
            )
        return FAIL, detail


def check_geonames() -> tuple[str, str]:
    user = os.getenv("KERYKEION_GEONAMES_USERNAME")
    if not user:
        return SKIP, "no KERYKEION_GEONAMES_USERNAME in environment"
    try:
        resp = httpx.get(
            "http://api.geonames.org/searchJSON",
            params={"q": "Istanbul", "maxRows": 1, "username": user},
            timeout=30.0,
        )
        data = resp.json()
        if data.get("geonames"):
            return PASS, "account active, geocoding works"
        status = data.get("status", {})
        return FAIL, f"GeoNames error: {status.get('message', data)}"
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"{type(exc).__name__}: {exc}"


CHECKS = [
    ("OpenAI LLM", check_openai),
    ("Moonshot LLM", check_moonshot),
    ("Tavily search", check_tavily),
    ("Polymarket Gamma", check_polymarket),
    ("GeoNames", check_geonames),
]


def main() -> int:
    print("REALM external-surface smoke test")
    print("=" * 60)
    worst = 0
    for name, fn in CHECKS:
        status, detail = fn()
        print(f"  [{status}] {name:<18} {detail}")
        if status == FAIL:
            worst = 1
    print("=" * 60)
    print("RESULT:", "FAIL — see above" if worst else "all live surfaces OK")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
