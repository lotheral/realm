"""Sprint 14 WP2: AgentFactory seed_offsets tests.

Verifies that:
1. seed_offsets is applied AFTER the political_spectrum override, so country
   variance is preserved while the population reflects the question's domain.
2. Each offset is added clamped to [0, 1].
3. seed_offsets=None / {} preserves pre-Sprint-14 behavior bit-for-bit.
4. Per-agent application is deterministic (same seed → same traits).
"""

from __future__ import annotations

from realm.agents.factory import AgentFactory
from realm.demographics.world_generator import WorldGenerator


def _build_population(seed: int = 42, n: int = 30, *, seed_offsets=None):
    profiles = WorldGenerator(master_seed=seed).generate(n)
    return AgentFactory(seed_offsets=seed_offsets).build_batch(profiles)


def test_no_offsets_default_behavior() -> None:
    """Without seed_offsets, AgentFactory.build_batch() is bit-identical to
    the pre-Sprint-14 path. Same seed → same trait vectors."""
    a = _build_population(seed=7, n=20)
    b = _build_population(seed=7, n=20, seed_offsets={})
    c = _build_population(seed=7, n=20, seed_offsets=None)
    assert len(a) == len(b) == len(c) == 20
    for ag_a, ag_b, ag_c in zip(a, b, c, strict=True):
        for trait in ("risk_appetite", "openness", "loss_aversion", "political_spectrum"):
            assert getattr(ag_a.traits, trait) == getattr(ag_b.traits, trait) == getattr(ag_c.traits, trait)


def test_positive_offset_lifts_population_mean() -> None:
    """An offset of +0.04 on a trait should lift the population mean by ~0.04
    (within clamp tails). The political_spectrum override is unaffected by
    risk_appetite offsets."""
    base = _build_population(seed=42, n=80)
    shifted = _build_population(seed=42, n=80, seed_offsets={"risk_appetite": 0.04})

    base_mean = sum(a.traits.risk_appetite for a in base) / len(base)
    shifted_mean = sum(a.traits.risk_appetite for a in shifted) / len(shifted)
    delta = shifted_mean - base_mean
    # Most agents have risk_appetite well inside [0,1] — clamp tails are rare,
    # so the population delta should be very close to the offset.
    assert 0.030 < delta < 0.045, (
        f"expected ~+0.04 lift, got {delta:+.4f}"
    )


def test_negative_offset_lowers_population_mean() -> None:
    base = _build_population(seed=99, n=80)
    shifted = _build_population(seed=99, n=80, seed_offsets={"loss_aversion": -0.03})
    base_mean = sum(a.traits.loss_aversion for a in base) / len(base)
    shifted_mean = sum(a.traits.loss_aversion for a in shifted) / len(shifted)
    delta = shifted_mean - base_mean
    assert -0.040 < delta < -0.020, (
        f"expected ~-0.03 lift, got {delta:+.4f}"
    )


def test_offsets_clamp_to_unit_interval() -> None:
    """An extreme offset (technically rejected by config-load validation but
    we still defend at the AgentFactory layer) should never push a trait
    outside [0, 1]. Use a synthetic large offset to force the clamp path."""
    population = _build_population(seed=1, n=40, seed_offsets={"openness": 0.5})
    for ag in population:
        assert 0.0 <= ag.traits.openness <= 1.0


def test_political_spectrum_country_variance_preserved() -> None:
    """seed_offsets must NOT touch political_spectrum because that override
    fires immediately before offsets in AgentFactory.build(). Country-level
    variance from the Hofstede proxy stays intact."""
    base = _build_population(seed=11, n=80)
    shifted = _build_population(seed=11, n=80, seed_offsets={"risk_appetite": 0.04, "openness": 0.03})
    base_ps = [a.traits.political_spectrum for a in base]
    shifted_ps = [a.traits.political_spectrum for a in shifted]
    # political_spectrum vectors must be identical (country-keyed override
    # only depends on profile.country, which is determined by master_seed).
    assert base_ps == shifted_ps
    # And it must show country variance, not all-0.5.
    assert max(base_ps) - min(base_ps) > 0.10


def test_multiple_offsets_independently_applied() -> None:
    """Two simultaneous offsets must each be applied; they don't interfere."""
    pop = _build_population(seed=2, n=40, seed_offsets={
        "risk_appetite": 0.04,
        "patience": -0.03,
    })
    base = _build_population(seed=2, n=40)

    risk_delta = (
        sum(a.traits.risk_appetite for a in pop) / len(pop)
        - sum(a.traits.risk_appetite for a in base) / len(base)
    )
    patience_delta = (
        sum(a.traits.patience for a in pop) / len(pop)
        - sum(a.traits.patience for a in base) / len(base)
    )
    assert 0.030 < risk_delta < 0.045
    assert -0.040 < patience_delta < -0.020


def test_deterministic_under_same_seed() -> None:
    a = _build_population(seed=5, n=15, seed_offsets={"openness": 0.03})
    b = _build_population(seed=5, n=15, seed_offsets={"openness": 0.03})
    for ag_a, ag_b in zip(a, b, strict=True):
        assert ag_a.traits.openness == ag_b.traits.openness
        assert ag_a.traits.political_spectrum == ag_b.traits.political_spectrum


def test_categories_load_with_seed_offsets() -> None:
    """The production prediction_categories.json must load cleanly with the
    Sprint 14 schema (drift_event_weights + trait_seed_offsets)."""
    from realm.output.category_router import CategoryRouter

    router = CategoryRouter()  # default path
    crypto = router._by_id["crypto"]
    assert "trait_seed_offsets" in crypto
    offsets = crypto["trait_seed_offsets"]
    assert "risk_appetite" in offsets
    # Zero-sum invariant
    assert abs(sum(offsets.values())) < 0.01
    # Magnitude cap
    assert max(abs(v) for v in offsets.values()) <= 0.05


def test_categories_reject_non_zero_sum_offsets(tmp_path) -> None:
    """Config-load validation rejects offset maps that violate zero-sum."""
    import json

    from realm.output.category_router import load_categories

    bad_config = {
        "schema_version": 2,
        "categories": [
            {
                "id": "broken",
                "label": "broken",
                "trait_weights": {
                    "primary": ["risk_appetite"],
                    "secondary": [],
                    "suppressed": [],
                },
                "trait_seed_offsets": {
                    "risk_appetite": 0.04,  # not balanced by anything
                },
                "keywords": [],
                "default_horizon_ticks": 30,
                "subcategories": [],
            },
            {
                "id": "balanced",
                "label": "fallback",
                "trait_weights": {"primary": [], "secondary": ["openness"], "suppressed": []},
                "keywords": [],
                "default_horizon_ticks": 30,
                "subcategories": [],
            },
        ],
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad_config), encoding="utf-8")

    try:
        load_categories(p)
    except ValueError as e:
        assert "zero-sum" in str(e).lower() or "trait_seed_offsets" in str(e)
        return
    raise AssertionError("expected ValueError for non-zero-sum offsets")


def test_categories_reject_oversized_offsets(tmp_path) -> None:
    """Config-load validation rejects per-trait magnitudes > 0.05."""
    import json

    from realm.output.category_router import load_categories

    bad_config = {
        "schema_version": 2,
        "categories": [
            {
                "id": "broken",
                "label": "broken",
                "trait_weights": {
                    "primary": ["risk_appetite"],
                    "secondary": [],
                    "suppressed": [],
                },
                "trait_seed_offsets": {
                    "risk_appetite": 0.10,  # too large
                    "patience": -0.10,      # also too large; sum is zero
                },
                "keywords": [],
                "default_horizon_ticks": 30,
                "subcategories": [],
            },
            {
                "id": "balanced",
                "label": "fallback",
                "trait_weights": {"primary": [], "secondary": ["openness"], "suppressed": []},
                "keywords": [],
                "default_horizon_ticks": 30,
                "subcategories": [],
            },
        ],
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad_config), encoding="utf-8")

    try:
        load_categories(p)
    except ValueError as e:
        msg = str(e).lower()
        assert "magnitude" in msg or "0.05" in msg
        return
    raise AssertionError("expected ValueError for oversized offset")
