"""Sprint 14 WP3: V-Dem political polarization integration tests.

Verifies that:
1. V-Dem JSON loads with full 66-country coverage matching Hofstede.
2. The blended political_spectrum spread is wider than the Sprint 11
   Hofstede-only baseline (>= 0.41).
3. Pearson correlation between Hofstede-only and blended values is high
   (>= 0.7) — the blend re-weights, it does not replace.
4. Scandinavian-vs-Gulf extreme ordering is preserved (Denmark < China).
5. The DemographicAdapter use_vdem=False flag falls back to Sprint 11.
"""

from __future__ import annotations

import math
import statistics

from realm.demographics.country_data import load_hofstede, load_vdem
from realm.personality.adapters.demographic import (
    _political_spectrum_from_hofstede,
)


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx * dy else 0.0


def test_vdem_loads_full_coverage() -> None:
    """V-Dem JSON must cover every country in hofstede_scores.json."""
    hof = set(load_hofstede().keys())
    vdem = set(load_vdem().keys())
    missing = hof - vdem
    assert not missing, f"V-Dem missing {len(missing)} countries: {sorted(missing)}"
    # And no V-Dem-only stragglers (we want the same 66 ISO2 set).
    extras = vdem - hof
    assert not extras, f"V-Dem has {len(extras)} extras not in Hofstede: {sorted(extras)}"


def test_vdem_fields_in_unit_interval() -> None:
    """Every V-Dem score must be in [0, 1]."""
    for iso, scores in load_vdem().items():
        for field in ("libdem", "partipdem", "polyarchy", "eqdr"):
            v = scores.get(field)
            assert v is not None, f"{iso}.{field} is missing"
            assert 0.0 <= float(v) <= 1.0, f"{iso}.{field}={v} outside [0,1]"


def test_blend_widens_political_spectrum_spread() -> None:
    """The Hofstede(0.6) + (1-V-Dem.libdem)(0.4) blend must produce a wider
    political_spectrum spread than Sprint 11 Hofstede-only (0.41)."""
    countries = list(load_hofstede().keys())
    hof_only = [_political_spectrum_from_hofstede(c, use_vdem=False) for c in countries]
    blend = [_political_spectrum_from_hofstede(c, use_vdem=True) for c in countries]

    hof_spread = max(hof_only) - min(hof_only)
    blend_spread = max(blend) - min(blend)

    # Sanity: Sprint 11 baseline still holds with use_vdem=False.
    assert hof_spread >= 0.40
    # Blend widens it.
    assert blend_spread > hof_spread, (
        f"blend spread {blend_spread:.3f} not wider than Hofstede {hof_spread:.3f}"
    )
    assert blend_spread >= 0.45, (
        f"blend spread {blend_spread:.3f} below 0.45 target — V-Dem under-weighting"
    )


def test_pearson_correlation_above_threshold() -> None:
    """Pearson correlation between Hofstede-only and blended political_spectrum
    must be high (>=0.7) — the blend re-weights, it does not replace."""
    countries = list(load_hofstede().keys())
    hof_only = [_political_spectrum_from_hofstede(c, use_vdem=False) for c in countries]
    blend = [_political_spectrum_from_hofstede(c, use_vdem=True) for c in countries]
    r = _pearson(hof_only, blend)
    assert r > 0.7, f"Pearson {r:.3f} below 0.7 threshold — blend has flipped semantic"


def test_scandinavia_below_china_extreme_ordering() -> None:
    """Scandinavian countries (Denmark, Sweden, Norway) — liberal democracies —
    should sit at the LOW end of political_spectrum (away from authority pole).
    Gulf states / one-party regimes (China, Saudi Arabia, Iran) at the HIGH end.
    """
    scandinavia = [
        _political_spectrum_from_hofstede(c, use_vdem=True)
        for c in ("DK", "SE", "NO")
    ]
    authoritarian = [
        _political_spectrum_from_hofstede(c, use_vdem=True)
        for c in ("CN", "SA", "IR", "RU")
    ]
    # Every Scandinavian value must be lower than every authoritarian value.
    assert max(scandinavia) < min(authoritarian), (
        f"ordering broken: max scand {max(scandinavia):.3f} >= "
        f"min authoritarian {min(authoritarian):.3f}"
    )


def test_use_vdem_false_recovers_sprint11_baseline() -> None:
    """Pass use_vdem=False to recover the Sprint 11 Hofstede-only formula
    bit-for-bit. This is how the regression test suite asserts no surprise
    breakage to the Sprint 11 baseline numbers."""
    # A handful of canonical Sprint 11 values from the milestone report.
    # If these change, the Hofstede-only formula has been altered — flag it.
    val_us = _political_spectrum_from_hofstede("US", use_vdem=False)
    val_dk = _political_spectrum_from_hofstede("DK", use_vdem=False)
    val_jp = _political_spectrum_from_hofstede("JP", use_vdem=False)
    # Known production values (Sprint 11 Hofstede-only formula with the
    # _PS_PDI_COEFF=0.35 / _PS_IDV_COEFF=0.25 production coefficients):
    #   US ~ 0.363, DK ~ 0.328, JP ~ 0.524
    assert abs(val_us - 0.363) < 0.005
    assert abs(val_dk - 0.328) < 0.005
    assert abs(val_jp - 0.524) < 0.005


def test_demographic_adapter_use_vdem_flag_routes_correctly() -> None:
    """DemographicAdapter(use_vdem=False) must produce the Sprint 11 baseline
    political_spectrum; default DemographicAdapter() blends V-Dem in."""
    from datetime import UTC, datetime

    from realm.demographics.interfaces import DemographicProfile
    from realm.personality.adapters import DemographicAdapter

    profile = DemographicProfile(
        agent_id="t",
        name_first="T", name_last="A", gender="X",
        country="DK", city="Copenhagen",
        birth_datetime=datetime(1990, 1, 1, 12, 0, tzinfo=UTC),
        birth_latitude=55.68, birth_longitude=12.57,
        birth_timezone="Europe/Copenhagen",
        age_years=35,
        profession_code="2-T", profession_name="engineer",
        income_annual_usd=80000.0, education_level="bachelor",
        marginal_flag=False, marginal_category=None,
        primary_religion="non-religious", region="europe",
    )
    a_default = DemographicAdapter()
    a_no_vdem = DemographicAdapter(use_vdem=False)
    blended = a_default.build(profile).political_spectrum
    hof_only = a_no_vdem.build(profile).political_spectrum
    # Denmark: Hofstede-only ≈ 0.328; blend (with V-Dem libdem ~0.89) drops
    # toward the liberal pole, so blend < Hofstede-only.
    assert blended < hof_only
    assert hof_only > 0.30
    assert blended < 0.30
