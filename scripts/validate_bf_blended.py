"""Focused BlendedAdapter validity check — reports criterion #4a.

Criterion #4a (derived-trait narrow variance): for each of the 19 derived
traits, per-population std > 0.05 with calibration OFF.

Mirrors the relevant subset of `scripts/validate_bf_study.py` for the
blended pipeline, without re-running the full 700-line comparator. Writes
`outputs/bf_validity_blended.md`.

Usage:
    python scripts/validate_bf_blended.py [N=10000] [--seed=42]
"""

from __future__ import annotations

import contextlib as _ctx
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.agents.factory import AgentFactory  # noqa: E402
from realm.core.logging import setup_logging  # noqa: E402
from realm.personality.adapters import get_input_adapter  # noqa: E402
from realm.personality.calibration import TraitCalibrator  # noqa: E402
from realm.personality.trait_vector import TraitVector  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from generate_bf_population import build_bf_profiles  # noqa: E402

BIG_FIVE_KEYS = ("openness", "conscientiousness", "extraversion",
                 "agreeableness", "neuroticism")
DERIVED_STD_MIN = 0.05
TARGET_STD_MIN = 0.14
DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"


def _derived_trait_list() -> list[str]:
    """Traits WITH derivation coefficients — the 13 checked by criterion #4a.

    Matches `scripts/validate_bf_study.py`'s "Derived 13 traits" check.
    Excludes the 5 Big Five (pass-through), _excluded_by_design traits
    (political_spectrum) and _unsourced_traits (herd, fomo, individualism,
    tradition, spirituality).
    """
    if not DERIVATION_PATH.exists():
        return []
    raw = json.loads(DERIVATION_PATH.read_text(encoding="utf-8"))
    return [
        t for t, entry in raw.get("traits", {}).items()
        if entry.get("coefficients")
    ]


def run_pipeline(profiles, enable_calibration: bool) -> dict[str, list[float]]:
    adapter = get_input_adapter("blended")
    calibrator = (
        TraitCalibrator(
            enabled=True, target_mean=0.50, target_std=0.17,
            adapter_type="blended",
        )
        if enable_calibration
        else TraitCalibrator(enabled=False)
    )
    factory = AgentFactory(adapter=adapter, calibrator=calibrator)
    agents = factory.build_batch(profiles)
    data: dict[str, list[float]] = {n: [] for n in TraitVector.trait_names()}
    for a in agents:
        for n in TraitVector.trait_names():
            data[n].append(getattr(a.traits, n))
    return data


def _std(vals: list[float]) -> float:
    return statistics.stdev(vals) if len(vals) > 1 else 0.0


def _mean(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else 0.0


def _parse_argv(argv: list[str]) -> tuple[int, int]:
    n = 10000
    seed = 42
    for arg in argv[1:]:
        if arg.startswith("--seed="):
            seed = int(arg.split("=", 1)[1])
        elif arg.isdigit():
            n = int(arg)
    return n, seed


def build_report(
    n: int, seed: int,
    off: dict[str, list[float]], on: dict[str, list[float]],
    blend_config: dict,
) -> str:
    trait_names = TraitVector.trait_names()
    derived = _derived_trait_list()

    lines: list[str] = []
    lines.append("# BlendedAdapter validity study")
    lines.append("")
    lines.append(f"N={n}, seed={seed}.\n")
    lines.append(
        "Blend config: "
        + ", ".join(
            f"{c['type']}={c['weight']}" for c in blend_config["components"]
        )
        + f", σ={blend_config['noise_sigma']}.\n",
    )

    lines.append("## Per-trait distribution (cal OFF vs cal ON)\n")
    lines.append("| trait | mean off | std off | mean on | std on | meets >0.05? |")
    lines.append("|-------|----------|---------|---------|--------|--------------|")
    for t in trait_names:
        m_off, s_off = _mean(off[t]), _std(off[t])
        m_on, s_on = _mean(on[t]), _std(on[t])
        ok = "yes" if t in BIG_FIVE_KEYS or s_off > DERIVED_STD_MIN else "no"
        lines.append(
            f"| {t} | {m_off:.3f} | {s_off:.3f} | {m_on:.3f} | {s_on:.3f} | {ok} |",
        )
    lines.append("")

    # Criteria 1 (mean std cal ON), 4a (derived std > 0.05 cal OFF), 4b (cal ON)
    stds_on = [_std(on[t]) for t in trait_names]
    mean_std_on = _mean(stds_on)
    criterion_1 = mean_std_on >= TARGET_STD_MIN

    derived_off = [_std(off[t]) for t in derived]
    derived_on_stds = [_std(on[t]) for t in derived]
    criterion_4a = all(s > DERIVED_STD_MIN for s in derived_off)
    criterion_4b = all(s > DERIVED_STD_MIN for s in derived_on_stds)

    lines.append("## Success criteria (blended pipeline)\n")
    lines.append("| # | criterion | measurement | result |")
    lines.append("|---|-----------|-------------|--------|")
    lines.append(
        f"| 1 | Mean trait std >= 0.14 (cal ON) | {mean_std_on:.3f} | "
        f"{'PASS' if criterion_1 else 'FAIL'} |",
    )
    lines.append(
        f"| 4a | Derived {len(derived)} traits all std > 0.05 (cal OFF) | "
        f"min = {min(derived_off):.3f} | "
        f"{'PASS' if criterion_4a else 'FAIL'} |",
    )
    lines.append(
        f"| 4b | Derived {len(derived)} traits all std > 0.05 (cal ON) | "
        f"min = {min(derived_on_stds):.3f} | "
        f"{'PASS' if criterion_4b else 'FAIL'} |",
    )
    lines.append("")

    passed = sum([criterion_1, criterion_4a, criterion_4b])
    lines.append(f"**{passed}/3 criteria passed.**\n")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    setup_logging(level="WARNING")
    argv = argv if argv is not None else sys.argv
    n, seed = _parse_argv(argv)

    adapter = get_input_adapter("blended")
    blend_config = {
        "components": [
            {"type": c.adapter_type, "weight": c.weight}
            for c in adapter.components
        ],
        "noise_sigma": adapter.noise_sigma,
    }

    print(f"BlendedAdapter validity study: N={n}, seed={seed}")
    print(f"Blend: {blend_config}")
    print("Output: outputs/bf_validity_blended.md\n")

    t0 = time.perf_counter()
    profiles = build_bf_profiles(n, seed=seed)
    print(f"[1/3] Built {len(profiles)} BF profiles in "
          f"{time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    off = run_pipeline(profiles, enable_calibration=False)
    print(f"[2/3] Blended pipeline cal OFF in {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    on = run_pipeline(profiles, enable_calibration=True)
    print(f"[3/3] Blended pipeline cal ON  in {time.perf_counter() - t0:.1f}s")

    report = build_report(n, seed, off, on, blend_config)
    out_path = ROOT / "outputs" / "bf_validity_blended.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {out_path}")

    # Print key verdict to stdout
    derived = _derived_trait_list()
    derived_off_stds = [_std(off[t]) for t in derived]
    if all(s > DERIVED_STD_MIN for s in derived_off_stds):
        print(
            f"\n#4a: PASS (all {len(derived)} derived traits std > 0.05; "
            f"min={min(derived_off_stds):.3f})",
        )
    else:
        failing = [
            (t, _std(off[t])) for t in derived if _std(off[t]) <= DERIVED_STD_MIN
        ]
        print(f"\n#4a: FAIL — {len(failing)} traits below 0.05:")
        for t, s in failing:
            print(f"   - {t}: {s:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
