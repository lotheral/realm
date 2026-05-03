"""Run the AstrologicalAdapter on 20 celebrity natal charts.

Loads data/validation/celebrity_profiles.json, computes a NatalChart per
figure (local time -> UTC via zoneinfo), runs it through AstrologicalAdapter
(and optionally BlendedAdapter with neutral BigFive + synthesized demographic
inputs for noise-floor reference), and emits:

    outputs/celebrity_astro_profiles.json

Usage:
    python scripts/generate_celebrity_astro_profiles.py
    python scripts/generate_celebrity_astro_profiles.py --include-blended
    python scripts/generate_celebrity_astro_profiles.py --engine=skyfield
    python scripts/generate_celebrity_astro_profiles.py --calibration=none
    python scripts/generate_celebrity_astro_profiles.py --calibration=full

Calibration modes (--calibration=...):
  - `none` (default) — emit raw adapter output. **Best choice for this
    celebrity validation study.** A Sprint 8 grid search confirmed raw output
    beats every variance-expansion width on DA, Pearson, and CW-DA: the raw
    adapter clusters individuals tightly in direction-correct bands, and any
    variance expansion amplifies within-band noise rather than signal.
  - `variance` — per-trait variance expansion around the raw observed mean
    using `config/trait_calibration_astrological.json`. Adaptive mean-
    boundary shift prevents clamping for traits whose raw mean sits near 1.0.
    Intended use: improving magnitude spread for simulation agents when the
    target is to resemble the general-population BF std ~0.17, NOT validation.
  - `full` — the standard TraitCalibrator pipeline (shifts mean AND std
    toward target_mean=0.50, target_std=0.17). Correct for general population
    simulation (5K+ agents); destructive for celebrity validation because
    celebrities are a selection-biased subsample with skewed expected means.

Skyfield backend covers 1899-07-29..2053-10-09 only; Kerykeion ("auto" default)
covers ~13,000 BCE..~17,000 CE and handles all historical figures in the set.
"""

from __future__ import annotations

import contextlib as _ctx
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.astro.factory import get_astro_engine  # noqa: E402
from realm.core.types import NatalChart  # noqa: E402
from realm.personality.adapters.astrological import AstrologicalAdapter  # noqa: E402
from realm.personality.calibration import TraitCalibrator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

PROFILES_IN = ROOT / "data" / "validation" / "celebrity_profiles.json"
OUT_PATH = ROOT / "outputs" / "celebrity_astro_profiles.json"


VALID_CAL_MODES = ("variance", "full", "none")


def _parse_argv(argv: list[str]) -> tuple[str, bool, str]:
    backend = "auto"
    include_blended = False
    cal_mode = "none"
    for arg in argv:
        if arg.startswith("--engine="):
            backend = arg.split("=", 1)[1]
        elif arg == "--include-blended":
            include_blended = True
        elif arg.startswith("--calibration="):
            cal_mode = arg.split("=", 1)[1].strip()
            if cal_mode not in VALID_CAL_MODES:
                print(f"Invalid --calibration value {cal_mode!r}; use one of {VALID_CAL_MODES}",
                      file=sys.stderr)
                raise SystemExit(2)
        elif arg == "--no-calibration":  # legacy alias
            cal_mode = "none"
        elif arg in ("-h", "--help"):
            print(__doc__)
            raise SystemExit(0)
    return backend, include_blended, cal_mode


def _local_to_utc(local_iso: str, tz_name: str) -> datetime:
    """Convert naive local ISO datetime to UTC tz-aware."""
    naive = datetime.fromisoformat(local_iso)
    local = naive.replace(tzinfo=ZoneInfo(tz_name))
    return local.astimezone(UTC)


def _chart_summary(chart: NatalChart) -> dict:
    """Compact chart summary for report context — signs of luminaries + ASC/MC."""
    planet_index = {p.name: p for p in chart.planets}
    sun = planet_index.get("Sun")
    moon = planet_index.get("Moon")

    def _sign_from_lon(lon: float) -> str:
        signs = (
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
        )
        return signs[int(lon // 30) % 12]

    return {
        "sun_sign": sun.sign if sun else None,
        "moon_sign": moon.sign if moon else None,
        "asc_sign": _sign_from_lon(chart.ascendant),
        "mc_sign": _sign_from_lon(chart.midheaven),
        "element_balance": dict(chart.element_balance),
        "modality_balance": dict(chart.modality_balance),
        "n_aspects": len(chart.aspects),
    }


def _load_astro_stats() -> dict[str, tuple[float, float]] | None:
    """Load per-trait (mean, std) from config/trait_calibration_astrological.json."""
    stats_path = ROOT / "config" / "trait_calibration_astrological.json"
    if not stats_path.exists():
        return None
    with stats_path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (float(v[0]), float(v[1])) for k, v in raw["per_trait"].items()}


def _apply_variance_expansion(
    tv: TraitVector,
    stats: dict[str, tuple[float, float]],
    target_std: float = 0.17,
    min_obs_std: float = 1e-4,
) -> TraitVector:
    """Per-trait variance expansion with adaptive mean-boundary shift.

    Expands each trait's distribution around its observed mean by
    `target_std / obs_std`. Crucially, if `obs_mean` lies outside
    `[target_std, 1 - target_std]` it is shifted inward to that boundary
    BEFORE expansion — this prevents the [0, 1] clamp from eating the
    expanded signal for traits whose raw distribution sits near a ceiling
    (e.g. astrological empathy at raw μ=0.98). Traits whose raw mean is
    already within the safe band are left untouched, so well-calibrated
    traits (like `loss_aversion` after the Sprint 8 mapping fix) don't
    drift away from their principled value.
    """
    updated: dict[str, float] = {}
    safe_low = target_std
    safe_high = 1.0 - target_std
    for trait in TraitVector.trait_names():
        raw = getattr(tv, trait)
        obs = stats.get(trait)
        if obs is None:
            updated[trait] = raw
            continue
        obs_mean, obs_std = obs
        if obs_std < min_obs_std:
            updated[trait] = raw
            continue
        # Adaptive mean anchor: only shift if raw mean would cause 1σ clamping
        if obs_mean > safe_high:
            new_mean = safe_high
        elif obs_mean < safe_low:
            new_mean = safe_low
        else:
            new_mean = obs_mean
        # Variance expand around the (possibly shifted) mean, preserving
        # individual deviations from raw_mean.
        new_val = new_mean + (raw - obs_mean) * (target_std / obs_std)
        updated[trait] = max(0.0, min(1.0, new_val))
    return TraitVector.from_dict(updated)


def _run_astro(
    adapter: AstrologicalAdapter,
    chart: NatalChart,
    cal_mode: str,
    full_calibrator: TraitCalibrator | None,
    astro_stats: dict[str, tuple[float, float]] | None,
) -> dict[str, float]:
    tv = adapter.build(chart)
    if cal_mode == "full" and full_calibrator is not None and full_calibrator.enabled:
        tv = full_calibrator.apply(tv)
    elif cal_mode == "variance" and astro_stats is not None:
        tv = _apply_variance_expansion(tv, astro_stats, target_std=0.17)
    return tv.to_dict()


def _run_blended_neutral(
    chart: NatalChart, agent_seed: int,
) -> dict[str, float] | None:
    """Optional Blended run with neutral BigFive + synthesized demographics.

    Returns None if required components are unavailable. The purpose is noise-
    floor reference only — not primary validation, since we have no real BF or
    demographic data for historical figures.
    """
    try:
        from realm.demographics.interfaces import DemographicProfile  # noqa: PLC0415
        from realm.personality.adapters import get_input_adapter  # noqa: PLC0415
        from realm.personality.adapters.blended import (  # noqa: PLC0415
            BlendedAdapter,
            BlendedComponent,
            BlendedInput,
        )
    except ImportError:
        return None

    try:
        astro = get_input_adapter("astrological")
        bf = get_input_adapter("big_five")
        demo = get_input_adapter("demographic")
    except Exception:
        return None

    blended = BlendedAdapter(
        components=[
            BlendedComponent(adapter=astro, weight=0.6),
            BlendedComponent(adapter=bf, weight=0.25),
            BlendedComponent(adapter=demo, weight=0.15),
        ],
        noise_sigma=0.05,
    )
    neutral_bf = dict.fromkeys(
        ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"),
        0.5,
    )
    try:
        # Minimal DemographicProfile — keeping None lets BlendedAdapter skip
        # the demographic component without weight issues.
        bi = BlendedInput(
            natal_chart=chart,
            big_five_scores=neutral_bf,
            demographic_profile=None,
            agent_seed=agent_seed,
        )
        tv = blended.build(bi)
        return tv.to_dict()
    except Exception:
        return None
    finally:
        del DemographicProfile  # silence unused import warning


def main(argv: list[str]) -> int:
    backend, include_blended, cal_mode = _parse_argv(argv)
    with PROFILES_IN.open(encoding="utf-8") as f:
        source = json.load(f)

    engine = get_astro_engine(backend)
    adapter = AstrologicalAdapter()
    full_calibrator = (
        TraitCalibrator(enabled=True, adapter_type="astrological")
        if cal_mode == "full" else None
    )
    astro_stats = _load_astro_stats() if cal_mode == "variance" else None
    if cal_mode == "variance" and astro_stats is None:
        print("WARNING: --calibration=variance requested but "
              "config/trait_calibration_astrological.json not found; "
              "falling back to raw output.", file=sys.stderr)
        cal_mode = "none"

    all_traits = list(TraitVector.trait_names())
    out: dict[str, object] = {
        "schema_version": "1.1",
        "engine_backend": engine.backend_name,
        "embedder_mode": adapter.embedder_mode,
        "calibration": {
            "mode": cal_mode,
            "target_std": 0.17 if cal_mode == "variance" else None,
            "stats_path": ("config/trait_calibration_astrological.json"
                           if cal_mode in ("variance", "full") else None),
        },
        "source": str(PROFILES_IN.relative_to(ROOT)).replace("\\", "/"),
        "trait_scope": {
            "all_traits": all_traits,
            "validated_traits": [t for t in all_traits if t != "political_spectrum"],
            "excluded_from_astro": ["political_spectrum"],
        },
        "figures": {},
    }
    figures_out = out["figures"]

    ok = 0
    failed: list[tuple[str, str]] = []
    for fid, fig in source["figures"].items():
        b = fig["birth"]
        try:
            birth_utc = _local_to_utc(b["local_iso"], b["timezone"])
            chart = engine.calculate_natal_chart(
                birth_dt=birth_utc,
                latitude=b["latitude"],
                longitude=b["longitude"],
                timezone=b["timezone"],
            )
            astro_dict = _run_astro(
                adapter, chart, cal_mode, full_calibrator, astro_stats,
            )
            blended_dict = None
            if include_blended:
                blended_dict = _run_blended_neutral(
                    chart, agent_seed=hash(fid) & 0xFFFFFFFF,
                )
            figures_out[fid] = {
                "name": fig["name"],
                "era": fig.get("era"),
                "occupation": fig.get("occupation"),
                "birth_utc": birth_utc.isoformat(),
                "birth_time_confidence": b.get("birth_time_confidence"),
                "astro_databank_rating": b.get("astro_databank_rating"),
                "chart_summary": _chart_summary(chart),
                "astro_only": astro_dict,
                "blended": blended_dict,
                "expected": fig["expected_traits"],
                "status": "ok",
            }
            ok += 1
            print(f"[ok]   {fid:24s} sun={figures_out[fid]['chart_summary']['sun_sign']:<12s}"
                  f" asc={figures_out[fid]['chart_summary']['asc_sign']}")
        except Exception as e:
            failed.append((fid, str(e)))
            figures_out[fid] = {
                "name": fig["name"],
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
            }
            print(f"[FAIL] {fid:24s} {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()

    out["summary"] = {
        "total": len(source["figures"]),
        "ok": ok,
        "failed": [f[0] for f in failed],
        "blended_included": include_blended,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print()
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Success: {ok}/{len(source['figures'])}")
    if failed:
        print(f"Failed: {[fid for fid, _ in failed]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
