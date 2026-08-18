# Sprint 21 — Reaction-Distribution Output Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the reaction distribution (stance shares + shift + segment breakdown over a per-question target population) REALM's first-class output, per design decision #1 and #2.

**Architecture:** Three new surfaces on top of the existing pipeline: (1) `PopulationSpec` constrains `WorldGenerator` sampling so every branch sim runs on the question's target population; (2) a new `realm/output/reaction.py` module pools per-agent deviations across ALL branch sims into a `ReactionDistribution` (stances + segments by country/region/age-band/gender), replacing the last-branch-only bucket in `api/predict.py`; (3) the API response and the v2 dashboard surface the distribution, with probability demoted to derived output.

**Tech Stack:** Python 3.11, FastAPI/pydantic, pytest, vanilla-JS single-file dashboard (`outputs/realm_dashboard_v2.html`).

**Spec:** `docs/superpowers/specs/2026-08-18-reaction-distribution-repositioning-design.md` (§2, §5 row "21").

## Global Constraints

- Python 3.11; run everything with `.venv/Scripts/python.exe` (Windows venv).
- Test command: `.venv/Scripts/python.exe -m pytest <path> -q` (full suite must stay green: 923 tests before this sprint).
- Lint: `.venv/Scripts/python.exe -m ruff check .` must stay clean; line-length and style per existing `pyproject.toml`.
- Determinism contract: given (master_seed, spec, n_agents) population generation is byte-identical; an **unrestricted** spec must consume the RNG identically to no spec at all.
- No renaming / no README identity rewrite (design doc §6 — repositioning surface waits for Study A).
- Version: bump to `0.21.0` only in `pyproject.toml` (single source; `realm.__version__` reads importlib.metadata — refresh editable install with `pip install -e . --no-deps`).
- Use the Edit/Write tools for file changes, never PowerShell pipelines (mojibake hazard). No `"` inside PS-passed commit messages — use Bash tool for git commits.
- Commit after every task with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: `PopulationSpec` dataclass

**Files:**
- Create: `realm/demographics/population_spec.py`
- Test: `realm/demographics/tests/test_population_spec.py`

**Interfaces:**
- Consumes: `realm.demographics.country_data.load_countries()` — returns `list[dict]`, each dict has keys `iso2`, `population`, `region` (15 region values like `europe_west`, `mena`, `asia_east`, `oceania`…; 66 countries).
- Produces: `PopulationSpec` frozen dataclass with `resolve_countries() -> list[dict]`, `is_unrestricted() -> bool`, `describe() -> str`. Task 2, 3, 5 import `from realm.demographics.population_spec import PopulationSpec`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for PopulationSpec — per-question target population (Sprint 21)."""

import pytest

from realm.demographics.population_spec import PopulationSpec


class TestValidation:
    def test_empty_spec_is_unrestricted(self):
        spec = PopulationSpec()
        assert spec.is_unrestricted()
        assert len(spec.resolve_countries()) == 66

    def test_country_filter_resolves_subset(self):
        spec = PopulationSpec(countries=("TR", "DE"))
        isos = {c["iso2"] for c in spec.resolve_countries()}
        assert isos == {"TR", "DE"}
        assert not spec.is_unrestricted()

    def test_region_filter_resolves_member_countries(self):
        spec = PopulationSpec(regions=("mena",))
        resolved = spec.resolve_countries()
        assert resolved
        assert all(c["region"] == "mena" for c in resolved)

    def test_countries_and_regions_are_unioned(self):
        spec = PopulationSpec(countries=("TR",), regions=("mena",))
        isos = {c["iso2"] for c in spec.resolve_countries()}
        mena_only = {c["iso2"] for c in PopulationSpec(regions=("mena",)).resolve_countries()}
        assert isos == mena_only | {"TR"}

    def test_unknown_country_raises(self):
        with pytest.raises(ValueError, match="unknown country"):
            PopulationSpec(countries=("XX",)).resolve_countries()

    def test_unknown_region_raises(self):
        with pytest.raises(ValueError, match="unknown region"):
            PopulationSpec(regions=("atlantis",)).resolve_countries()

    def test_inverted_age_range_raises(self):
        with pytest.raises(ValueError, match="age_min"):
            PopulationSpec(age_min=60, age_max=30).validate()

    def test_unknown_gender_raises(self):
        with pytest.raises(ValueError, match="gender"):
            PopulationSpec(genders=("Q",)).validate()

    def test_unknown_education_raises(self):
        with pytest.raises(ValueError, match="education"):
            PopulationSpec(education_levels=("phd",)).validate()

    def test_valid_filters_pass_validate(self):
        PopulationSpec(
            countries=("TR",), age_min=18, age_max=29,
            genders=("F",), education_levels=("bachelor", "graduate"),
        ).validate()


class TestDescribe:
    def test_unrestricted_describes_as_global(self):
        assert PopulationSpec().describe() == "global"

    def test_describe_lists_active_filters(self):
        spec = PopulationSpec(countries=("TR", "DE"), age_min=18, age_max=29, genders=("F",))
        desc = spec.describe()
        assert "TR" in desc and "DE" in desc
        assert "18-29" in desc
        assert "F" in desc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest realm/demographics/tests/test_population_spec.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'realm.demographics.population_spec'`

- [ ] **Step 3: Write the implementation**

```python
"""PopulationSpec — per-question target population (Sprint 21, design decision #2).

A question's population is defined by the request, not assumed to be "the
world": country and/or region restriction (union semantics), age band,
gender, and education filters. An empty spec means the full 66-country
world sample and MUST leave generation byte-identical to the pre-Sprint-21
pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from realm.demographics.country_data import load_countries

VALID_GENDERS = ("M", "F", "X")
VALID_EDUCATION_LEVELS = ("primary", "secondary", "bachelor", "graduate")

_AGE_FLOOR = 18
_AGE_CEIL = 90


@dataclass(frozen=True, slots=True)
class PopulationSpec:
    """Target population for one question. All fields optional; empty = world.

    ``countries`` (ISO2) and ``regions`` (country-data region keys) are
    UNIONED: the candidate set is every listed country plus every country
    in a listed region. Age/gender/education act as per-agent sampling
    constraints inside the candidate countries.
    """

    countries: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    age_min: int | None = None
    age_max: int | None = None
    genders: tuple[str, ...] = ()
    education_levels: tuple[str, ...] = ()
    label: str = ""

    def is_unrestricted(self) -> bool:
        return not (
            self.countries or self.regions
            or self.age_min is not None or self.age_max is not None
            or self.genders or self.education_levels
        )

    def validate(self) -> None:
        """Raise ValueError on any filter value the data layer cannot honor."""
        lo = self.age_min if self.age_min is not None else _AGE_FLOOR
        hi = self.age_max if self.age_max is not None else _AGE_CEIL
        if lo > hi:
            raise ValueError(f"age_min ({lo}) must be <= age_max ({hi})")
        for g in self.genders:
            if g not in VALID_GENDERS:
                raise ValueError(f"unknown gender {g!r} (valid: {VALID_GENDERS})")
        for e in self.education_levels:
            if e not in VALID_EDUCATION_LEVELS:
                raise ValueError(
                    f"unknown education level {e!r} (valid: {VALID_EDUCATION_LEVELS})"
                )
        self.resolve_countries()

    def resolve_countries(self) -> list[dict]:
        """Return the candidate country dicts, validating ISO2/region names."""
        all_countries = load_countries()
        if not self.countries and not self.regions:
            return list(all_countries)
        by_iso = {c["iso2"]: c for c in all_countries}
        known_regions = {c["region"] for c in all_countries}
        for iso in self.countries:
            if iso not in by_iso:
                raise ValueError(f"unknown country ISO2 {iso!r}")
        for region in self.regions:
            if region not in known_regions:
                raise ValueError(f"unknown region {region!r} (valid: {sorted(known_regions)})")
        picked: dict[str, dict] = {iso: by_iso[iso] for iso in self.countries}
        for c in all_countries:
            if c["region"] in self.regions:
                picked.setdefault(c["iso2"], c)
        return list(picked.values())

    def describe(self) -> str:
        if self.label:
            return self.label
        if self.is_unrestricted():
            return "global"
        parts: list[str] = []
        if self.countries:
            parts.append("+".join(self.countries))
        if self.regions:
            parts.append("+".join(self.regions))
        if self.age_min is not None or self.age_max is not None:
            lo = self.age_min if self.age_min is not None else _AGE_FLOOR
            hi = self.age_max if self.age_max is not None else _AGE_CEIL
            parts.append(f"{lo}-{hi}")
        if self.genders:
            parts.append("/".join(self.genders))
        if self.education_levels:
            parts.append("/".join(self.education_levels))
        return ", ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest realm/demographics/tests/test_population_spec.py -q`
Expected: all PASS

- [ ] **Step 5: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check realm/demographics
git add realm/demographics/population_spec.py realm/demographics/tests/test_population_spec.py
git commit -m "feat(sprint21): PopulationSpec — per-question target population

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `WorldGenerator` honors `PopulationSpec`

**Files:**
- Modify: `realm/demographics/world_generator.py`
- Test: `realm/demographics/tests/test_world_generator_population_spec.py` (new file; leave existing `test_world_generator.py` untouched)

**Interfaces:**
- Consumes: `PopulationSpec` from Task 1 (`resolve_countries()`, field access).
- Produces: `WorldGenerator.__init__(..., population_spec: PopulationSpec | None = None)`; `generate(n_agents)` unchanged signature. Task 3 relies on the keyword name `population_spec` exactly.

**Sampling rules (locked here):**
- Country candidates come from `spec.resolve_countries()`; weights stay national-population-proportional within the subset.
- Age / gender / education are constrained via **bounded rejection resampling** (max 200 draws from the same `rng`, then a deterministic fallback: age → clamp into the allowed band; gender → `spec.genders[0]`; education → `spec.education_levels[0]`). Deterministic for a given (seed, spec).
- When the spec is `None` **or** the field's filter is empty, call the existing sampler exactly once — identical RNG consumption, byte-identical output.

- [ ] **Step 1: Write the failing tests**

```python
"""WorldGenerator + PopulationSpec constrained sampling (Sprint 21)."""

from realm.demographics.population_spec import PopulationSpec
from realm.demographics.world_generator import WorldGenerator


class TestPopulationSpecSampling:
    def test_none_spec_and_empty_spec_are_byte_identical(self):
        base = WorldGenerator(master_seed=42).generate(40)
        empty = WorldGenerator(master_seed=42, population_spec=PopulationSpec()).generate(40)
        assert base == empty

    def test_same_spec_same_seed_is_deterministic(self):
        spec = PopulationSpec(countries=("TR", "DE"), age_min=18, age_max=29)
        a = WorldGenerator(master_seed=7, population_spec=spec).generate(30)
        b = WorldGenerator(master_seed=7, population_spec=spec).generate(30)
        assert a == b

    def test_country_restriction_applies_to_every_agent(self):
        spec = PopulationSpec(countries=("TR",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(25)
        assert profiles
        assert all(p.country == "TR" for p in profiles)

    def test_region_restriction_applies_to_every_agent(self):
        spec = PopulationSpec(regions=("mena",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(25)
        assert profiles
        assert all(p.region == "mena" for p in profiles)

    def test_age_band_applies_to_every_agent(self):
        spec = PopulationSpec(age_min=18, age_max=29)
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(40)
        assert all(18 <= p.age_years <= 29 for p in profiles)

    def test_gender_filter_applies_to_every_agent(self):
        spec = PopulationSpec(genders=("F",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(40)
        assert all(p.gender == "F" for p in profiles)

    def test_education_filter_applies_to_every_agent(self):
        spec = PopulationSpec(education_levels=("bachelor", "graduate"))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(40)
        assert all(p.education_level in ("bachelor", "graduate") for p in profiles)

    def test_rare_gender_filter_terminates(self):
        # X is sampled at 2% — the 200-draw cap plus deterministic fallback
        # must still return n agents, all X.
        spec = PopulationSpec(genders=("X",))
        profiles = WorldGenerator(master_seed=42, population_spec=spec).generate(15)
        assert len(profiles) == 15
        assert all(p.gender == "X" for p in profiles)

    def test_combined_filters(self):
        spec = PopulationSpec(countries=("TR",), age_min=30, age_max=44, genders=("M",))
        profiles = WorldGenerator(master_seed=11, population_spec=spec).generate(20)
        assert all(
            p.country == "TR" and 30 <= p.age_years <= 44 and p.gender == "M"
            for p in profiles
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest realm/demographics/tests/test_world_generator_population_spec.py -q`
Expected: FAIL with `TypeError: WorldGenerator.__init__() got an unexpected keyword argument 'population_spec'`

- [ ] **Step 3: Implement in `world_generator.py`**

Add import near the other `.interfaces` import:

```python
from .population_spec import PopulationSpec
```

Extend `__init__` (add the parameter and store it; leave existing body intact):

```python
    def __init__(
        self,
        master_seed: int | None = None,
        sim_epoch: datetime | None = None,
        rural_ratio: float = 0.30,
        rural_offset_deg: float = 1.0,
        population_spec: PopulationSpec | None = None,
    ) -> None:
        ...existing body...
        self._spec = population_spec
```

In `generate()`, replace the two lines that build the candidate list:

```python
        countries = load_countries()
```
becomes
```python
        # Sprint 21: per-question target population. An unrestricted spec
        # resolves to the full country list, keeping RNG consumption and
        # output byte-identical to the no-spec pipeline.
        if self._spec is not None:
            countries = self._spec.resolve_countries()
        else:
            countries = load_countries()
```
(the following `country_isos` / `country_weights` lines stay unchanged).

In `_generate_one()`, replace the three direct sampler calls:

```python
        age = sample_age(iso2, rng)
        gender = sample_gender(rng)
        ...
        education = sample_education(iso2, rng)
```
with constrained versions:

```python
        age = self._constrained_age(iso2, rng)
        gender = self._constrained_gender(rng)
        ...
        education = self._constrained_education(iso2, rng)
```

and add the three helpers to the class:

```python
    _MAX_RESAMPLE = 200

    def _constrained_age(self, iso2: str, rng: random.Random) -> int:
        spec = self._spec
        if spec is None or (spec.age_min is None and spec.age_max is None):
            return sample_age(iso2, rng)
        lo = spec.age_min if spec.age_min is not None else 18
        hi = spec.age_max if spec.age_max is not None else 90
        for _ in range(self._MAX_RESAMPLE):
            age = sample_age(iso2, rng)
            if lo <= age <= hi:
                return age
        return max(lo, min(hi, sample_age(iso2, rng)))

    def _constrained_gender(self, rng: random.Random) -> str:
        spec = self._spec
        if spec is None or not spec.genders:
            return sample_gender(rng)
        for _ in range(self._MAX_RESAMPLE):
            gender = sample_gender(rng)
            if gender in spec.genders:
                return gender
        return spec.genders[0]

    def _constrained_education(self, iso2: str, rng: random.Random) -> str:
        spec = self._spec
        if spec is None or not spec.education_levels:
            return sample_education(iso2, rng)
        for _ in range(self._MAX_RESAMPLE):
            education = sample_education(iso2, rng)
            if education in spec.education_levels:
                return education
        return spec.education_levels[0]
```

- [ ] **Step 4: Run the new tests + the existing demographics suite**

Run: `.venv/Scripts/python.exe -m pytest realm/demographics -q`
Expected: all PASS (existing world-generator determinism tests prove the no-spec path is untouched)

- [ ] **Step 5: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check realm/demographics
git add realm/demographics/world_generator.py realm/demographics/tests/test_world_generator_population_spec.py
git commit -m "feat(sprint21): WorldGenerator constrained sampling from PopulationSpec

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: plumb `population_spec` through `build_branch_sim`

**Files:**
- Modify: `realm/output/predictor.py` (function `build_branch_sim`, lines ~145-257)
- Test: `realm/output/tests/test_predictor_population.py` (new file)

**Interfaces:**
- Consumes: Task 1 `PopulationSpec`, Task 2 `WorldGenerator(master_seed=..., population_spec=...)`.
- Produces: `build_branch_sim(seed, n_agents, *, ..., population_spec: PopulationSpec | None = None)`. Task 5 passes this keyword from the API layer. When `agent_builder` is supplied, `population_spec` is ignored (the builder owns population construction — same contract as `seed_offsets`).

- [ ] **Step 1: Write the failing test**

```python
"""build_branch_sim + PopulationSpec plumbing (Sprint 21)."""

from realm.demographics.population_spec import PopulationSpec
from realm.output.predictor import build_branch_sim


class TestBranchSimPopulation:
    def test_default_builder_honors_population_spec(self):
        spec = PopulationSpec(countries=("TR",), age_min=18, age_max=29)
        sim = build_branch_sim(42, 20, population_spec=spec)
        assert len(sim.agents) == 20
        assert all(a.profile.country == "TR" for a in sim.agents)
        assert all(18 <= a.profile.age_years <= 29 for a in sim.agents)

    def test_no_spec_matches_legacy_population(self):
        base = build_branch_sim(42, 15)
        specd = build_branch_sim(42, 15, population_spec=None)
        assert [a.profile for a in base.agents] == [a.profile for a in specd.agents]

    def test_custom_agent_builder_wins_over_spec(self):
        marker = build_branch_sim(42, 5).agents  # any legacy population
        def builder(seed: int, n: int) -> list:
            return list(marker[:n])
        sim = build_branch_sim(
            42, 5,
            agent_builder=builder,
            population_spec=PopulationSpec(countries=("TR",)),
        )
        assert sim.agents == list(marker[:5])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest realm/output/tests/test_predictor_population.py -q`
Expected: FAIL with `TypeError: build_branch_sim() got an unexpected keyword argument 'population_spec'`

- [ ] **Step 3: Implement**

In `realm/output/predictor.py` add the import at the top with the other realm imports:

```python
from realm.demographics.population_spec import PopulationSpec
```

Extend the `build_branch_sim` signature (after `primary_traits`):

```python
    primary_traits: tuple[str, ...] = (),
    population_spec: PopulationSpec | None = None,
) -> SimulationEngine:
```

Replace the default-builder branch:

```python
    if agent_builder is not None:
        agents = agent_builder(seed, n_agents)
    else:
        agents = AgentFactory(seed_offsets=seed_offsets).build_batch(
            WorldGenerator(master_seed=seed, population_spec=population_spec).generate(n_agents),
        )
```

Append one line to the docstring's Sprint list: `Sprint 21: ``population_spec`` restricts the default WorldGenerator sample to the question's target population; ignored when a custom ``agent_builder`` is supplied (the builder owns population construction).`

- [ ] **Step 4: Run the predictor suites**

Run: `.venv/Scripts/python.exe -m pytest realm/output/tests/test_predictor.py realm/output/tests/test_predictor_weighted.py realm/output/tests/test_predictor_population.py -q`
Expected: all PASS

- [ ] **Step 5: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check realm/output
git add realm/output/predictor.py realm/output/tests/test_predictor_population.py
git commit -m "feat(sprint21): build_branch_sim accepts population_spec

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `realm/output/reaction.py` — the reaction-distribution module

**Files:**
- Create: `realm/output/reaction.py`
- Modify: `realm/api/predict.py` (delete the four private helpers it absorbs; re-import under the old names)
- Test: `realm/output/tests/test_reaction.py`

**Interfaces:**
- Consumes: branch sims (duck-typed: `.agents` list where each agent has `.traits` and `.profile`, optional `.drift_engine` with `current_traits(agent)`), `baseline_means: Mapping[str, float]`, `weights: Mapping[str, float]` from `category_weights(category)`.
- Produces (exact names Task 5 imports):
  - `category_weights(category) -> dict[str, float]` (moved verbatim from `api/predict.py::_category_weights`)
  - `effective_traits(sim, agent)` (moved from `_effective_traits`)
  - `per_agent_deviations(sim, baseline_means, weights) -> list[float]` (moved from `_per_agent_deviations`)
  - `bucket_three_way(devs, threshold=None) -> tuple[float, float, float]` (moved from `_bucket_three_way`, gains optional fixed threshold)
  - `BUCKET_MIN_THRESHOLD = 0.005`
  - `age_band(age: int) -> str` → `"18-29" | "30-44" | "45-59" | "60+"`
  - `StanceShares(support, oppose, neutral)` frozen dataclass
  - `SegmentReaction(dimension, segment, n_agents, shares: StanceShares, mean_deviation)` frozen dataclass
  - `ReactionDistribution(stances, n_agents, mean_deviation, threshold, segments: tuple[SegmentReaction, ...])` frozen dataclass
  - `compute_reaction_distribution(sims, baseline_means, weights, *, min_segment_size=5, max_segments_per_dimension=6) -> ReactionDistribution`
  - `stance_shift(scenario: StanceShares, baseline: StanceShares) -> StanceShares` (element-wise deltas)

**Semantics (locked here):**
- Per-agent deviations are pooled across **all** branch sims (n_branches × n_agents samples), not just the last branch — that is the whole point of the module.
- One global bucket threshold `max(BUCKET_MIN_THRESHOLD, 0.5 * pstdev(pooled))` is computed once and applied to every segment, so segment shares are comparable to each other and to the total.
- Segment dimensions: `country` (`profile.country`), `region` (`profile.region`), `age_band` (`age_band(profile.age_years)`), `gender` (`profile.gender`). Segments with fewer than `min_segment_size` pooled samples are dropped; each dimension keeps at most `max_segments_per_dimension` segments, largest-n first.

- [ ] **Step 1: Write the failing tests**

```python
"""ReactionDistribution — pooled stance shares + segment breakdown (Sprint 21)."""

from datetime import UTC, datetime
from types import SimpleNamespace

from realm.demographics.interfaces import DemographicProfile
from realm.output.reaction import (
    ReactionDistribution,
    StanceShares,
    age_band,
    bucket_three_way,
    compute_reaction_distribution,
    stance_shift,
)


def make_profile(i: int, country: str = "TR", region: str = "mena",
                 age: int = 25, gender: str = "M") -> DemographicProfile:
    return DemographicProfile(
        agent_id=f"AGT_{i:06d}", name_first="A", name_last="B", gender=gender,
        country=country, city="X",
        birth_datetime=datetime(2000, 1, 1, tzinfo=UTC),
        birth_latitude=0.0, birth_longitude=0.0, birth_timezone="UTC",
        age_years=age, profession_code="p", profession_name="P",
        income_annual_usd=1000.0, education_level="secondary",
        marginal_flag=False, marginal_category=None,
        primary_religion="none", region=region,
    )


def make_sim(trait_values: list[float], profiles: list[DemographicProfile]):
    agents = [
        SimpleNamespace(traits=SimpleNamespace(openness=v), profile=p)
        for v, p in zip(trait_values, profiles, strict=True)
    ]
    return SimpleNamespace(agents=agents, drift_engine=None)


BASELINE = {"openness": 0.5}
WEIGHTS = {"openness": 1.0}


class TestAgeBand:
    def test_bands(self):
        assert age_band(18) == "18-29"
        assert age_band(29) == "18-29"
        assert age_band(30) == "30-44"
        assert age_band(45) == "45-59"
        assert age_band(60) == "60+"
        assert age_band(90) == "60+"


class TestBucketThreeWay:
    def test_fixed_threshold_overrides_sigma(self):
        devs = [0.2, 0.2, -0.2, 0.0]
        sup, opp, neu = bucket_three_way(devs, threshold=0.1)
        assert (sup, opp, neu) == (0.5, 0.25, 0.25)

    def test_default_threshold_matches_legacy(self):
        # No threshold arg -> same sigma-based behavior as the old
        # api/predict.py _bucket_three_way.
        sup, opp, neu = bucket_three_way([])
        assert (sup, opp, neu) == (0.34, 0.33, 0.33)


class TestComputeReactionDistribution:
    def test_pools_across_all_branches(self):
        profiles = [make_profile(i) for i in range(4)]
        sim_a = make_sim([0.9, 0.9, 0.9, 0.9], profiles)   # all support
        sim_b = make_sim([0.1, 0.1, 0.1, 0.1], profiles)   # all oppose
        rd = compute_reaction_distribution(
            [sim_a, sim_b], BASELINE, WEIGHTS, min_segment_size=1,
        )
        assert rd.n_agents == 8
        assert abs(rd.stances.support - 0.5) < 1e-9
        assert abs(rd.stances.oppose - 0.5) < 1e-9
        assert abs(rd.stances.support + rd.stances.oppose + rd.stances.neutral - 1.0) < 1e-9

    def test_segments_split_by_country(self):
        profiles = (
            [make_profile(i, country="TR", region="mena") for i in range(3)]
            + [make_profile(i + 3, country="DE", region="europe_west") for i in range(3)]
        )
        # TR agents pushed up, DE agents pushed down
        sim = make_sim([0.9, 0.9, 0.9, 0.1, 0.1, 0.1], profiles)
        rd = compute_reaction_distribution([sim], BASELINE, WEIGHTS, min_segment_size=1)
        by_key = {(s.dimension, s.segment): s for s in rd.segments}
        tr = by_key[("country", "TR")]
        de = by_key[("country", "DE")]
        assert tr.shares.support == 1.0 and tr.shares.oppose == 0.0
        assert de.shares.oppose == 1.0 and de.shares.support == 0.0
        assert tr.mean_deviation > 0 > de.mean_deviation
        assert {"country", "region", "age_band", "gender"} <= {s.dimension for s in rd.segments}

    def test_min_segment_size_drops_small_segments(self):
        profiles = [make_profile(i, country="TR") for i in range(5)]
        profiles.append(make_profile(99, country="DE", region="europe_west"))
        sim = make_sim([0.9] * 6, profiles)
        rd = compute_reaction_distribution([sim], BASELINE, WEIGHTS, min_segment_size=5)
        countries = {s.segment for s in rd.segments if s.dimension == "country"}
        assert "DE" not in countries
        assert "TR" in countries

    def test_empty_sims_returns_neutral_distribution(self):
        rd = compute_reaction_distribution([], BASELINE, WEIGHTS)
        assert isinstance(rd, ReactionDistribution)
        assert rd.n_agents == 0
        assert rd.segments == ()
        assert (rd.stances.support, rd.stances.oppose, rd.stances.neutral) == (0.34, 0.33, 0.33)


class TestStanceShift:
    def test_elementwise_delta(self):
        shift = stance_shift(
            StanceShares(support=0.6, oppose=0.2, neutral=0.2),
            StanceShares(support=0.4, oppose=0.4, neutral=0.2),
        )
        assert abs(shift.support - 0.2) < 1e-9
        assert abs(shift.oppose + 0.2) < 1e-9
        assert abs(shift.neutral) < 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest realm/output/tests/test_reaction.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'realm.output.reaction'`

- [ ] **Step 3: Write `realm/output/reaction.py`**

```python
"""Reaction distribution — REALM's first-class output (Sprint 21).

Design decision #1 (2026-08-18): the product answer to "if event X happens,
how does population P react?" is a distribution — stance shares plus their
shift against the no-event baseline, broken down by segment — with any
probability number derived, not primary.

This module pools per-agent weighted trait deviations across ALL branch
sims (the api layer previously bucketed only the last branch) and derives:

* total stance shares (support / oppose / neutral),
* per-segment shares along country / region / age-band / gender,
* one global bucket threshold so segment shares stay comparable.

The four helpers at the top are the former private functions of
``realm/api/predict.py``; they moved here so the reaction math has a
single owner. ``api/predict.py`` re-imports them under the old names.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

BUCKET_MIN_THRESHOLD = 0.005  # avoids all-neutral degenerate split when σ≈0

_AGE_BANDS: tuple[tuple[int, int, str], ...] = (
    (18, 29, "18-29"),
    (30, 44, "30-44"),
    (45, 59, "45-59"),
    (60, 200, "60+"),
)

SEGMENT_DIMENSIONS = ("country", "region", "age_band", "gender")


def age_band(age: int) -> str:
    for lo, hi, label in _AGE_BANDS:
        if lo <= age <= hi:
            return label
    return _AGE_BANDS[0][2] if age < 18 else _AGE_BANDS[-1][2]


# ---- Helpers moved from realm/api/predict.py (Sprint 21) ------------------


def category_weights(category: Any) -> dict[str, float]:
    weighted: dict[str, float] = {}
    for trait in category.primary_traits:
        weighted[trait] = 2.0
    for trait in category.secondary_traits:
        weighted.setdefault(trait, 1.0)
    for trait in category.suppressed_traits:
        weighted.setdefault(trait, 0.25)
    if not weighted:
        # Pure balanced category — equal weight on every TraitVector axis so
        # the calibrator still has something to compare against.
        from realm.personality.trait_vector import TraitVector

        weighted = dict.fromkeys(TraitVector.trait_names(), 1.0)
    return weighted


def effective_traits(sim: Any, agent: Any):
    """Drift-applied trait vector when an ExperienceDriftEngine is attached,
    else the raw immutable traits."""
    eng = getattr(sim, "drift_engine", None)
    if eng is not None:
        return eng.current_traits(agent)
    return agent.traits


def per_agent_deviations(
    sim: Any, baseline_means: Mapping[str, float], weights: Mapping[str, float],
) -> list[float]:
    wsum = sum(weights.values()) or 1.0
    devs: list[float] = []
    for agent in sim.agents:
        eff = effective_traits(sim, agent)
        score = sum(
            w * (float(getattr(eff, t, 0.5)) - baseline_means.get(t, 0.5))
            for t, w in weights.items()
        ) / wsum
        devs.append(score)
    return devs


def bucket_three_way(
    devs: Sequence[float], threshold: float | None = None,
) -> tuple[float, float, float]:
    if not devs:
        return (0.34, 0.33, 0.33)
    if threshold is None:
        sigma = statistics.pstdev(devs) if len(devs) > 1 else 0.0
        threshold = max(BUCKET_MIN_THRESHOLD, 0.5 * sigma)
    sup = sum(1 for d in devs if d > threshold)
    opp = sum(1 for d in devs if d < -threshold)
    neu = len(devs) - sup - opp
    n = float(len(devs))
    return (sup / n, opp / n, neu / n)


# ---- Reaction distribution -------------------------------------------------


@dataclass(frozen=True, slots=True)
class StanceShares:
    support: float
    oppose: float
    neutral: float


@dataclass(frozen=True, slots=True)
class SegmentReaction:
    dimension: str          # "country" | "region" | "age_band" | "gender"
    segment: str            # e.g. "TR", "europe_west", "18-29", "F"
    n_agents: int           # pooled sample count (across all branches)
    shares: StanceShares
    mean_deviation: float


@dataclass(frozen=True, slots=True)
class ReactionDistribution:
    stances: StanceShares
    n_agents: int           # total pooled samples = n_branches * n_agents
    mean_deviation: float
    threshold: float        # the global bucket threshold used everywhere
    segments: tuple[SegmentReaction, ...]


def stance_shift(scenario: StanceShares, baseline: StanceShares) -> StanceShares:
    return StanceShares(
        support=scenario.support - baseline.support,
        oppose=scenario.oppose - baseline.oppose,
        neutral=scenario.neutral - baseline.neutral,
    )


def _segment_key(profile: Any, dimension: str) -> str:
    if dimension == "country":
        return str(profile.country)
    if dimension == "region":
        return str(profile.region)
    if dimension == "age_band":
        return age_band(int(profile.age_years))
    return str(profile.gender)


def compute_reaction_distribution(
    sims: Sequence[Any],
    baseline_means: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    min_segment_size: int = 5,
    max_segments_per_dimension: int = 6,
) -> ReactionDistribution:
    """Pool per-agent deviations across all branch sims into a distribution.

    One global threshold (``max(BUCKET_MIN_THRESHOLD, 0.5σ)`` of the POOLED
    deviations) is applied to the total and to every segment, so segment
    shares are directly comparable.
    """
    pooled: list[tuple[float, Any]] = []
    for sim in sims:
        devs = per_agent_deviations(sim, baseline_means, weights)
        for dev, agent in zip(devs, sim.agents, strict=True):
            pooled.append((dev, agent.profile))

    if not pooled:
        return ReactionDistribution(
            stances=StanceShares(0.34, 0.33, 0.33),
            n_agents=0, mean_deviation=0.0,
            threshold=BUCKET_MIN_THRESHOLD, segments=(),
        )

    all_devs = [d for d, _ in pooled]
    sigma = statistics.pstdev(all_devs) if len(all_devs) > 1 else 0.0
    threshold = max(BUCKET_MIN_THRESHOLD, 0.5 * sigma)
    sup, opp, neu = bucket_three_way(all_devs, threshold=threshold)

    segments: list[SegmentReaction] = []
    for dimension in SEGMENT_DIMENSIONS:
        groups: dict[str, list[float]] = {}
        for dev, profile in pooled:
            groups.setdefault(_segment_key(profile, dimension), []).append(dev)
        sized = sorted(
            ((k, v) for k, v in groups.items() if len(v) >= min_segment_size),
            key=lambda kv: (-len(kv[1]), kv[0]),
        )[:max_segments_per_dimension]
        for segment, devs in sized:
            s_sup, s_opp, s_neu = bucket_three_way(devs, threshold=threshold)
            segments.append(SegmentReaction(
                dimension=dimension, segment=segment, n_agents=len(devs),
                shares=StanceShares(s_sup, s_opp, s_neu),
                mean_deviation=statistics.mean(devs),
            ))

    return ReactionDistribution(
        stances=StanceShares(sup, opp, neu),
        n_agents=len(pooled),
        mean_deviation=statistics.mean(all_devs),
        threshold=threshold,
        segments=tuple(segments),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest realm/output/tests/test_reaction.py -q`
Expected: all PASS

- [ ] **Step 5: De-duplicate `realm/api/predict.py`**

Delete the four function definitions `_effective_traits`, `_per_agent_deviations`, `_bucket_three_way`, `_category_weights` (keep `_trait_means`, `_trait_stdevs`, `_weighted_population_deviation` — they stay local but call the imported helper). Add to the imports block:

```python
from realm.output.reaction import (
    bucket_three_way as _bucket_three_way,
    category_weights as _category_weights,
    effective_traits as _effective_traits,
    per_agent_deviations as _per_agent_deviations,
)
```

Also delete the now-shadowed constant `_BUCKET_MIN_THRESHOLD` line and replace its single use — it was only read inside the old `_bucket_three_way` — verify with: `grep -n "_BUCKET_MIN_THRESHOLD" realm/api/predict.py` (must return nothing after the deletion).

- [ ] **Step 6: Run the API + output suites to prove the move is behavior-neutral**

Run: `.venv/Scripts/python.exe -m pytest realm/api realm/output -q`
Expected: all PASS

- [ ] **Step 7: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check realm
git add realm/output/reaction.py realm/output/tests/test_reaction.py realm/api/predict.py
git commit -m "feat(sprint21): reaction module — pooled stance distribution + segments

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: API surface — `population` request field + `reaction` response field

**Files:**
- Modify: `realm/api/predict.py`
- Test: `realm/api/tests/test_reaction_endpoint.py` (new file)

**Interfaces:**
- Consumes: Task 1 `PopulationSpec`, Task 3 `build_branch_sim(..., population_spec=...)`, Task 4 `compute_reaction_distribution` / `stance_shift` / `ReactionDistribution` / `StanceShares`.
- Produces (dashboard contract for Task 6):
  - `PredictRequest.population: PopulationSpecModel | None` with fields `countries: list[str]`, `regions: list[str]`, `age_min: int|None`, `age_max: int|None`, `genders: list[str]`, `education_levels: list[str]`.
  - `PredictResponse.reaction: ReactionDistributionModel | None` with fields `support/oppose/neutral: float`, `n_agents: int`, `segments: list[{dimension, segment, n_agents, support, oppose, neutral, mean_deviation}]`, `baseline: {support, oppose, neutral} | None`, `shift: {support, oppose, neutral} | None`.
  - `PredictResponse.population_label: str | None` (echo of `PopulationSpec.describe()`, `"global"` when no spec sent).
  - Invalid population → HTTP 400 with the `ValueError` text.
  - **Behavior change (intended):** `agents_supporting/opposing/neutral` now mirror the pooled `reaction` stances (all branches), no longer the last-branch-only bucket.

- [ ] **Step 1: Write the failing tests**

```python
"""Sprint 21 — /api/predict population targeting + reaction distribution."""

import pytest
from fastapi.testclient import TestClient

from realm.api.predict import app

client = TestClient(app)

BASE = {
    "question": "Will inflation fall next quarter?",
    "n_agents": 30, "n_ticks": 5, "n_branches": 2,
    "use_llm": False, "enable_web_research": False,
    "master_seed": 42,
}


@pytest.fixture(scope="module")
def baseline_resp():
    r = client.post("/api/predict", json=BASE)
    assert r.status_code == 200
    return r.json()


class TestReactionField:
    def test_reaction_present_with_pooled_counts(self, baseline_resp):
        rx = baseline_resp["reaction"]
        assert rx is not None
        assert rx["n_agents"] == 30 * 2  # pooled across branches
        assert abs(rx["support"] + rx["oppose"] + rx["neutral"] - 1.0) < 1e-6
        assert rx["baseline"] is None and rx["shift"] is None

    def test_agents_fields_mirror_reaction(self, baseline_resp):
        rx = baseline_resp["reaction"]
        assert baseline_resp["agents_supporting"] == pytest.approx(rx["support"], abs=1e-4)
        assert baseline_resp["agents_opposing"] == pytest.approx(rx["oppose"], abs=1e-4)
        assert baseline_resp["agents_neutral"] == pytest.approx(rx["neutral"], abs=1e-4)

    def test_segments_have_known_dimensions(self, baseline_resp):
        dims = {s["dimension"] for s in baseline_resp["reaction"]["segments"]}
        assert dims <= {"country", "region", "age_band", "gender"}
        assert "gender" in dims  # 60 pooled samples guarantee gender segments

    def test_population_label_defaults_to_global(self, baseline_resp):
        assert baseline_resp["population_label"] == "global"


class TestScenarioShift:
    def test_scenario_reaction_carries_baseline_and_shift(self):
        r = client.post("/api/predict", json={
            **BASE,
            "scenario_feed": "Markets crash as panic selling accelerates and layoffs surge",
        })
        assert r.status_code == 200
        rx = r.json()["reaction"]
        assert rx["baseline"] is not None
        assert rx["shift"] is not None
        for key in ("support", "oppose", "neutral"):
            assert rx["shift"][key] == pytest.approx(rx[key] - rx["baseline"][key], abs=1e-6)


class TestPopulationTargeting:
    def test_population_restricts_segments_to_spec(self):
        r = client.post("/api/predict", json={
            **BASE,
            "population": {"countries": ["TR"], "age_min": 18, "age_max": 29},
        })
        assert r.status_code == 200
        body = r.json()
        assert "TR" in body["population_label"]
        country_segments = {
            s["segment"] for s in body["reaction"]["segments"]
            if s["dimension"] == "country"
        }
        assert country_segments == {"TR"}
        age_segments = {
            s["segment"] for s in body["reaction"]["segments"]
            if s["dimension"] == "age_band"
        }
        assert age_segments == {"18-29"}

    def test_unknown_country_is_400(self):
        r = client.post("/api/predict", json={
            **BASE, "population": {"countries": ["XX"]},
        })
        assert r.status_code == 400
        assert "unknown country" in r.json()["detail"]

    def test_llm_only_path_has_no_reaction(self):
        r = client.post("/api/predict", json={**BASE, "use_sim": False})
        assert r.status_code == 200
        body = r.json()
        assert body["reaction"] is None
        assert body["population_label"] == "global"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest realm/api/tests/test_reaction_endpoint.py -q`
Expected: FAIL (`reaction` key absent / `population` field rejected)

- [ ] **Step 3: Add the request/response models to `realm/api/predict.py`**

Import (top, with other realm imports): `from realm.demographics.population_spec import PopulationSpec` and extend the Task 4 reaction import line with `compute_reaction_distribution, stance_shift, ReactionDistribution, StanceShares` (public names, no aliases).

Above `PredictRequest` add:

```python
class PopulationSpecModel(BaseModel):
    """Per-question target population (Sprint 21, design decision #2)."""

    countries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    age_min: int | None = Field(default=None, ge=18, le=90)
    age_max: int | None = Field(default=None, ge=18, le=90)
    genders: list[str] = Field(default_factory=list)
    education_levels: list[str] = Field(default_factory=list)

    def to_spec(self) -> PopulationSpec:
        return PopulationSpec(
            countries=tuple(c.upper() for c in self.countries),
            regions=tuple(self.regions),
            age_min=self.age_min, age_max=self.age_max,
            genders=tuple(self.genders),
            education_levels=tuple(self.education_levels),
        )
```

Add to `PredictRequest` (after `enable_web_research`):

```python
    # Sprint 21 — per-question target population. None = global (66
    # countries, all demographics), byte-identical to pre-Sprint-21 runs.
    population: PopulationSpecModel | None = None
```

Below `PredictResponse`'s existing fields (end of class) add:

```python
    # Sprint 21 — reaction distribution (the first-class output; the
    # probability above is the derived view). None on the use_sim=False
    # fast path. baseline/shift populated only for scenario runs.
    reaction: ReactionDistributionModel | None = None
    population_label: str | None = None
```

and define, above `PredictResponse`:

```python
class StanceSharesModel(BaseModel):
    support: float
    oppose: float
    neutral: float


class SegmentReactionModel(BaseModel):
    dimension: str
    segment: str
    n_agents: int
    support: float
    oppose: float
    neutral: float
    mean_deviation: float


class ReactionDistributionModel(BaseModel):
    support: float
    oppose: float
    neutral: float
    n_agents: int
    segments: list[SegmentReactionModel]
    baseline: StanceSharesModel | None = None
    shift: StanceSharesModel | None = None
```

Add a converter next to the other synthesis helpers:

```python
def _reaction_to_model(
    reaction: ReactionDistribution,
    baseline: StanceShares | None = None,
) -> ReactionDistributionModel:
    shift = stance_shift(reaction.stances, baseline) if baseline is not None else None
    return ReactionDistributionModel(
        support=round(reaction.stances.support, 4),
        oppose=round(reaction.stances.oppose, 4),
        neutral=round(reaction.stances.neutral, 4),
        n_agents=reaction.n_agents,
        segments=[
            SegmentReactionModel(
                dimension=s.dimension, segment=s.segment, n_agents=s.n_agents,
                support=round(s.shares.support, 4),
                oppose=round(s.shares.oppose, 4),
                neutral=round(s.shares.neutral, 4),
                mean_deviation=round(s.mean_deviation, 4),
            )
            for s in reaction.segments
        ],
        baseline=(
            StanceSharesModel(
                support=round(baseline.support, 4),
                oppose=round(baseline.oppose, 4),
                neutral=round(baseline.neutral, 4),
            ) if baseline is not None else None
        ),
        shift=(
            StanceSharesModel(
                support=round(shift.support, 4),
                oppose=round(shift.oppose, 4),
                neutral=round(shift.neutral, 4),
            ) if shift is not None else None
        ),
    )
```

- [ ] **Step 4: Thread the spec + reaction through the endpoint**

1. `_capture_baseline_means` and `_run_branches`: add keyword `population_spec: PopulationSpec | None = None` to both signatures and forward it into their `build_branch_sim(...)` calls.
2. `_make_perturbed_agent_builder`: add keyword `population_spec: PopulationSpec | None = None`; inside `builder`, change the generation line to `WorldGenerator(master_seed=seed, population_spec=population_spec).generate(n_agents)`.
3. `_calibrated_outcome`: delete its last two lines (the per-agent bucket) and change its return to `return probability, branch_devs` — the bucket now comes from the reaction module. Update its docstring accordingly. Then `grep -n "_calibrated_outcome" realm` and fix every call site's unpacking (there are two in `predict_endpoint`; check `realm/api/tests` for direct callers and update their unpacking too if any exist).
4. In `predict_endpoint`, right after `master_seed = _resolve_seed(req)`:

```python
        population_spec = req.population.to_spec() if req.population is not None else None
        if population_spec is not None:
            try:
                population_spec.validate()
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        population_label = (
            population_spec.describe() if population_spec is not None else "global"
        )
```

5. `use_sim=False` fast path: add `reaction=None, population_label=population_label,` to its `PredictResponse(...)`.
6. Pass `population_spec=population_spec` into: the `_capture_baseline_means(...)` call, both `_run_branches(...)` calls (baseline + scenario), and the `_make_perturbed_agent_builder(...)` call.
7. After the baseline `_calibrated_outcome` call add:

```python
        weights = _category_weights(category)
        baseline_reaction = compute_reaction_distribution(
            baseline_sims, baseline_means, weights,
        )
```

8. In the scenario block, after the scenario `_calibrated_outcome` call add:

```python
            scenario_reaction = compute_reaction_distribution(
                scenario_sims, baseline_means, weights,
            )
```

(declare `scenario_reaction: ReactionDistribution | None = None` next to the other scenario declarations).

9. Replace the old bucket usage. Where the code did `sup, opp, neu = active_buckets`, use:

```python
        active_reaction = scenario_reaction if scenario_reaction is not None else baseline_reaction
        sup = active_reaction.stances.support
        opp = active_reaction.stances.oppose
        neu = active_reaction.stances.neutral
```

Remove the now-unused `baseline_buckets` / `scenario_buckets` variables.

10. In the final `PredictResponse(...)` add:

```python
            reaction=_reaction_to_model(
                active_reaction,
                baseline=(
                    baseline_reaction.stances
                    if scenario_reaction is not None else None
                ),
            ),
            population_label=population_label,
```

- [ ] **Step 5: Run the new tests + full API/output suites**

Run: `.venv/Scripts/python.exe -m pytest realm/api realm/output -q`
Expected: all PASS. If an existing test asserts exact `agents_supporting/opposing/neutral` values, re-derive the expectation from the pooled semantics (the split may legitimately differ from the old last-branch bucket) — verify the new value is stable across two runs before pinning it, and say so in the commit body.

- [ ] **Step 6: Live smoke (no LLM required)**

```bash
.venv/Scripts/python.exe -c "
from fastapi.testclient import TestClient
from realm.api.predict import app
c = TestClient(app)
r = c.post('/api/predict', json={
    'question': 'Will consumer confidence recover?',
    'n_agents': 40, 'n_ticks': 5, 'n_branches': 2, 'use_llm': False,
    'population': {'regions': ['europe_west'], 'age_min': 18, 'age_max': 29},
    'scenario_feed': 'Massive stimulus package boosts optimism and growth surges',
    'master_seed': 42,
})
body = r.json()
print(r.status_code, body['population_label'])
print({k: body['reaction'][k] for k in ('support', 'oppose', 'neutral', 'n_agents')})
print('shift', body['reaction']['shift'])
print('segments', [(s['dimension'], s['segment'], s['n_agents']) for s in body['reaction']['segments']][:8])
"
```
Expected: 200, label mentions `europe_west` and `18-29`, country segments only from europe_west, shift non-null.

- [ ] **Step 7: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check realm
git add realm/api/predict.py realm/api/tests/test_reaction_endpoint.py
git commit -m "feat(sprint21): /api/predict population targeting + ReactionDistribution response

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Dashboard surface (v2)

**Files:**
- Modify: `outputs/realm_dashboard_v2.html`

**Interfaces:**
- Consumes: Task 5 response contract (`reaction`, `population_label`) and request contract (`population`).
- Produces: UI only — no other task depends on it.

No pytest here; verification is a scripted DOM-free check (Step 4) plus the live smoke.

- [ ] **Step 1: Wire the existing Region Focus select + new population inputs**

The `cfg-region` select (line ~458) is currently cosmetic. Add the region map + payload builder near `STATE` (line ~639):

```javascript
// Sprint 21 — coarse dashboard regions -> country-data region keys
const REGION_MAP = {
  global:   [],
  asia:     ['asia_east', 'asia_south', 'asia_southeast', 'oceania'],
  europe:   ['europe_east', 'europe_north', 'europe_south', 'europe_west'],
  americas: ['america_north', 'america_south'],
  mena:     ['mena'],
  africa:   ['africa_central', 'africa_east', 'africa_south', 'africa_west'],
};

function buildPopulationPayload() {
  const pop = {};
  const regions = REGION_MAP[STATE.region] || [];
  if (regions.length) pop.regions = regions;
  const countries = (STATE.countries || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
  if (countries.length) pop.countries = countries;
  if (STATE.ageBand) {
    const [lo, hi] = STATE.ageBand.split('-').map(Number);
    pop.age_min = lo; pop.age_max = hi;
  }
  return Object.keys(pop).length ? pop : null;
}
```

In the setup panel, directly after the `cfg-region` config-group `</div>`, add two more groups:

```html
      <div class="config-group">
        <div class="config-label">Countries (ISO2, optional)</div>
        <input class="config-input" id="cfg-countries" placeholder="e.g. TR,DE,US" style="width:150px;">
      </div>
      <div class="config-group">
        <div class="config-label">Age Band</div>
        <select class="config-input" id="cfg-age">
          <option value="" selected>All (18-90)</option>
          <option value="18-29">18-29</option>
          <option value="30-44">30-44</option>
          <option value="45-59">45-59</option>
          <option value="60-90">60+</option>
        </select>
      </div>
```

In `startSession()` after `STATE.region = ...` add:

```javascript
  STATE.countries = document.getElementById('cfg-countries').value;
  STATE.ageBand = document.getElementById('cfg-age').value;
```

and change the status line to show the resolved target: after the existing `status-region` assignment, append:

```javascript
  const popPreview = buildPopulationPayload();
  if (popPreview) {
    const bits = [];
    if (popPreview.countries) bits.push(popPreview.countries.join('+'));
    else if (popPreview.regions) bits.push(STATE.region);
    if (popPreview.age_min) bits.push(`${popPreview.age_min}-${popPreview.age_max}`);
    document.getElementById('status-region').textContent = bits.join(' · ') || 'global';
  }
```

- [ ] **Step 2: Send `population` in live requests**

In `fetchPrediction`, extend the body object (after `n_branches: STATE.branches,`):

```javascript
      ...(buildPopulationPayload() ? { population: buildPopulationPayload() } : {}),
```

- [ ] **Step 3: Render the reaction block**

In `askQuestion`'s result rendering, replace the three `supporting/opposing/neutral` `tw.addLine` calls with:

```javascript
  // Sprint 21 — reaction distribution is the first-class output.
  const bar = (share) => '█'.repeat(Math.round(share * 24)).padEnd(24, '·');
  const pp = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}pp`;
  const rx = pred.reaction;
  if (rx) {
    tw.addLine(`│  REACTION DISTRIBUTION${pred.population_label && pred.population_label !== 'global' ? '  —  ' + pred.population_label : ''}`, 'label');
    const shiftFor = (k) => (rx.shift ? `  ${pp(rx.shift[k])} vs baseline` : '');
    tw.addLine(`│    support  ${bar(rx.support)} ${(rx.support * 100).toFixed(0)}%${shiftFor('support')}`, '');
    tw.addLine(`│    oppose   ${bar(rx.oppose)} ${(rx.oppose * 100).toFixed(0)}%${shiftFor('oppose')}`, '');
    tw.addLine(`│    neutral  ${bar(rx.neutral)} ${(rx.neutral * 100).toFixed(0)}%${shiftFor('neutral')}`, '');
    const segs = (rx.segments || []).filter(s => s.dimension === 'country' || s.dimension === 'age_band').slice(0, 6);
    if (segs.length) {
      tw.addLine(`│`, '');
      tw.addLine(`│  SEGMENTS (pooled n=${rx.n_agents})`, 'label');
      segs.forEach(s => {
        tw.addLine(`│    ${(s.dimension + ':' + s.segment).padEnd(22)} S ${(s.support * 100).toFixed(0).padStart(3)}%  O ${(s.oppose * 100).toFixed(0).padStart(3)}%  N ${(s.neutral * 100).toFixed(0).padStart(3)}%  (n=${s.n_agents})`, '');
      });
    }
  } else {
    tw.addLine(`│  supporting     ${(pred.agents_supporting * 100).toFixed(0)}% of agents`, '');
    tw.addLine(`│  opposing       ${(pred.agents_opposing * 100).toFixed(0)}% of agents`, '');
    tw.addLine(`│  neutral        ${(pred.agents_neutral * 100).toFixed(0)}% of agents`, '');
  }
  tw.addLine(`│`, '');
```

(the old three lines and their following `tw.addLine('│', '')` are replaced by this block — keep exactly one blank `│` line after it).

- [ ] **Step 4: Extend mock data so demo mode shows the block**

Add a `reaction` object to `SAMPLE_PREDICTIONS.politics`, `SAMPLE_PREDICTIONS.politics_scenario`, and `SAMPLE_PREDICTIONS.balanced` (values consistent with each sample's existing `agents_*` fields). For `politics` (agents 0.43/0.41/0.16):

```javascript
    population_label: 'global',
    reaction: {
      support: 0.43, oppose: 0.41, neutral: 0.16, n_agents: 500,
      baseline: null, shift: null,
      segments: [
        { dimension: 'country', segment: 'US', n_agents: 62, support: 0.40, oppose: 0.45, neutral: 0.15, mean_deviation: -0.004 },
        { dimension: 'country', segment: 'IN', n_agents: 88, support: 0.47, oppose: 0.37, neutral: 0.16, mean_deviation: 0.006 },
        { dimension: 'age_band', segment: '18-29', n_agents: 141, support: 0.49, oppose: 0.36, neutral: 0.15, mean_deviation: 0.008 },
        { dimension: 'age_band', segment: '60+', n_agents: 96, support: 0.36, oppose: 0.47, neutral: 0.17, mean_deviation: -0.007 },
      ],
    },
```

For `politics_scenario` (agents 0.58/0.27/0.15) use the same shape plus:

```javascript
      baseline: { support: 0.43, oppose: 0.41, neutral: 0.16 },
      shift: { support: 0.15, oppose: -0.14, neutral: -0.01 },
```

For `balanced` (agents 0.50/0.34/0.16) mirror its `agents_*` numbers with 2 segments; `baseline: null, shift: null`.

- [ ] **Step 5: Verify the file still parses and the contract keys line up**

```bash
.venv/Scripts/python.exe - <<'EOF'
import io
html = io.open('outputs/realm_dashboard_v2.html', encoding='utf-8').read()
for needle in ['REGION_MAP', 'buildPopulationPayload', 'REACTION DISTRIBUTION',
               'cfg-countries', 'cfg-age', 'population_label', "reaction: {"]:
    assert needle in html, f'missing: {needle}'
assert html.count('function buildPopulationPayload') == 1
print('dashboard surface OK')
EOF
```
Expected: `dashboard surface OK`

- [ ] **Step 6: Live smoke against the real API**

Start the API (background): `.venv/Scripts/python.exe -m uvicorn realm.api.predict:app --host 127.0.0.1 --port 8420` — then open `outputs/realm_dashboard_v2.html`, switch mode to Live, set Region Focus = Europe, Age Band = 18-29, ask a question, and confirm the REACTION DISTRIBUTION block renders with segments and (after a scenario) shift values. In mock mode confirm the politics sample shows the block. Stop the server.

- [ ] **Step 7: Commit**

```bash
git add outputs/realm_dashboard_v2.html
git commit -m "feat(sprint21): v2 dashboard reaction-distribution surface + population targeting

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Version bump, docs, full verification

**Files:**
- Modify: `pyproject.toml` (version `0.20.0` → `0.21.0`)
- Modify: `CHANGELOG.md` (new `## v0.21.0` section, mirror the v0.20.0 section's format)
- Modify: `REALM_CLAUDE.md` (version header + Sprint 21 block; follow the existing sprint-block format)
- Modify: `outputs/realm_dashboard_v2.html` About tab — one factual paragraph: the API now returns a per-question reaction distribution (stance shares, baseline shift, segment breakdown) over a caller-defined target population; probability is the derived view. No renaming (design doc §6).

- [ ] **Step 1: Bump version + refresh editable install**

Edit `pyproject.toml` line 3 to `version = "0.21.0"`, then:

```bash
.venv/Scripts/python.exe -m pip install -e . --no-deps -q
.venv/Scripts/python.exe -c "import realm; print(realm.__version__)"
```
Expected: `0.21.0`

- [ ] **Step 2: Write CHANGELOG + REALM_CLAUDE.md + About updates**

Read each file's existing head/format first, then add: PopulationSpec + constrained WorldGenerator sampling; `realm/output/reaction.py` pooled stance distribution + segments; `/api/predict` `population` request + `reaction`/`population_label` response (note the intended `agents_*` semantics change: pooled across branches); dashboard reaction surface. Update any stale test-count claims found via `grep -rn "923 tests" README.md REALM_CLAUDE.md CHANGELOG.md outputs/realm_dashboard_v2.html` to the new count from Step 3.

- [ ] **Step 3: Full-suite verification**

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
```
Expected: 0 failures, ruff clean. Record the final test count for the docs in Step 2 (amend if needed).

- [ ] **Step 4: Commit + push + watch CI**

```bash
git add pyproject.toml CHANGELOG.md REALM_CLAUDE.md outputs/realm_dashboard_v2.html
git commit -m "docs(sprint21): v0.21.0 — reaction-distribution output layer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push origin main
gh run watch --exit-status || gh run list --limit 1
```
Expected: CI green.
