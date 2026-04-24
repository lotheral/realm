"""Emit a draft per-facet coefficient proposal for big_five_derivation.

Deliverable B of Sprint 5 WP3. For each of the 13 sourced derived traits:

1. Compute REALM's synthetic trait value from Johnson-derived domain scores.
2. Regress that synthetic value against all 30 facet scores (OLS).
3. For each domain with a non-zero REALM coefficient, pick the facet that
   best predicts the trait WITHIN that domain (highest |β|) and assign it
   the domain-level coefficient. This "1-facet-per-domain" simplification
   keeps the draft coefficients interpretable and avoids the multicollinearity
   artifacts of spreading a domain's signal across 6 correlated facets.
4. Record the full OLS betas + t-stats alongside each retained facet so a
   future sprint can revisit the choice.

Writes `data/personality/big_five_derivation_facets_draft.json` with
`_draft_status: "proposal"`. This is a BACKLOG ARTIFACT, not shipped into
the BigFiveAdapter. A future sprint would consume it if REALM adopted
facet-level BigFive inputs.
"""

from __future__ import annotations

import contextlib as _ctx
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with _ctx.suppress(Exception):
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv()

from realm.personality.adapters import BigFiveAdapter  # noqa: E402
from realm.personality.validation.facet_scorer import (  # noqa: E402
    DEFAULT_DAT_PATH,
    DOMAINS,
    FACET_CODES,
    FACET_TO_DOMAIN,
    load_ipip120,
    score_dataset,
)

DERIVATION_PATH = ROOT / "data" / "personality" / "big_five_derivation.json"
DRAFT_PATH = ROOT / "data" / "personality" / "big_five_derivation_facets_draft.json"

DOMAIN_TO_KEY: dict[str, str] = {
    "O": "openness",
    "C": "conscientiousness",
    "E": "extraversion",
    "A": "agreeableness",
    "N": "neuroticism",
}

ABS_BETA_MIN = 0.10
P_THRESHOLD = 0.01


def _ols_with_t(
    X: np.ndarray,  # noqa: N803
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Ordinary least squares. Returns (betas, t-stats, R^2).

    X: (N, K) design matrix with intercept already included as column 0.
    y: (N,)
    """
    n_obs, n_coefs = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ beta
    rss = float((residuals ** 2).sum())
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - rss / max(tss, 1e-12)

    sigma2 = rss / max(n_obs - n_coefs, 1)
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.abs(np.diag(xtx_inv)) * sigma2)
    t = beta / np.maximum(se, 1e-12)
    return beta, t, r2


def _p_from_t(t: np.ndarray, dof: int) -> np.ndarray:
    """Approximate two-tailed p-value from t-statistics."""
    # For large dof, t approx standard normal. Our N is huge so this is fine.
    from math import erfc, sqrt
    return np.array([erfc(abs(tv) / sqrt(2)) for tv in t])


def _ipip_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    max_rows = None
    for arg in argv[1:]:
        if arg.startswith("--max-rows="):
            max_rows = int(arg.split("=", 1)[1])

    print(f"Loading IPIP120.dat (max_rows={max_rows or 'all'})...")
    t0 = time.perf_counter()
    records = load_ipip120(max_rows=max_rows)
    print(f"  loaded {len(records):,} records in {time.perf_counter() - t0:.1f}s")

    facets, domains, kept = score_dataset(records)
    N = len(kept)  # noqa: N806 - math convention for sample size
    print(f"  scored {N:,} records")

    # REALM synthetic trait values from domain scores
    deriv = json.loads(DERIVATION_PATH.read_text(encoding="utf-8"))
    traits_block = deriv.get("traits", {})
    sourced_traits = [t for t, e in traits_block.items()
                      if e.get("coefficients")]
    adapter = BigFiveAdapter()

    trait_values: dict[str, np.ndarray] = {
        t: np.zeros(N, dtype=np.float64) for t in sourced_traits
    }
    for i in range(N):
        scores = {DOMAIN_TO_KEY[d]: float(domains[i, di])
                  for di, d in enumerate(DOMAINS)}
        tv = adapter.build(scores)
        for t in sourced_traits:
            if hasattr(tv, t):
                trait_values[t][i] = getattr(tv, t)

    # OLS per trait against the 30 facets
    X_base = np.column_stack([np.ones(N), facets.astype(np.float64)])  # noqa: N806
    dof = N - X_base.shape[1]

    draft_traits: dict[str, dict] = {}
    for trait in sourced_traits:
        y = trait_values[trait]
        beta, tstats, r2 = _ols_with_t(X_base, y)
        facet_betas = beta[1:]  # skip intercept
        facet_t = tstats[1:]
        pvals = _p_from_t(facet_t, dof)
        p_adj = np.minimum(pvals * 30, 1.0)

        orig_coeffs = traits_block[trait].get("coefficients", {})

        # Record full OLS betas for each facet (diagnostic)
        full_betas = {
            FACET_CODES[i]: {
                "beta": round(float(facet_betas[i]), 4),
                "t": round(float(facet_t[i]), 2),
                "p_adj": round(float(p_adj[i]), 4),
            }
            for i in range(len(FACET_CODES))
        }

        # Per domain, pick best-predicting facet with sign agreeing with
        # original domain coefficient. Assign that facet the domain-level
        # coefficient value.
        retained: dict[str, float] = {}
        rationale: dict[str, str] = {}
        for d in DOMAINS:
            domain_key = DOMAIN_TO_KEY[d]
            target = float(orig_coeffs.get(domain_key, 0.0))
            if abs(target) < 1e-9:
                continue  # original derivation doesn't use this domain
            # Candidate facets in this domain
            cand_idx = [
                i for i, f in enumerate(FACET_CODES)
                if FACET_TO_DOMAIN[f] == d
            ]
            # Filter to those with sign-matching beta AND p_adj < threshold
            valid = [
                i for i in cand_idx
                if np.sign(facet_betas[i]) == np.sign(target)
                and p_adj[i] < P_THRESHOLD
            ]
            if not valid:
                # Fall back to full domain coefficient — no facet refinement
                retained[f"{d}*"] = target
                rationale[f"{d}*"] = (
                    "no facet within this domain passed the sign + "
                    "Bonferroni filter; kept domain-level coefficient"
                )
                continue
            # Pick facet with max |beta|
            best_i = max(valid, key=lambda i: abs(facet_betas[i]))
            best_facet = FACET_CODES[best_i]
            retained[best_facet] = round(target, 3)
            rationale[best_facet] = (
                f"chosen from {d} facets: |β|={abs(facet_betas[best_i]):.3f}, "
                f"p_adj={p_adj[best_i]:.3g}"
            )

        draft_traits[trait] = {
            "coefficients": retained,
            "rationale": rationale,
            "r2_full_ols": round(r2, 3),
            "full_ols_betas": full_betas,
            "source": "draft derived via scripts/draft_facet_coefficients.py",
            "confidence": "draft",
            "note": (
                f"OLS on {N:,} Johnson IPIP-NEO-120 respondents. For each "
                f"domain present in the original derivation, the best "
                f"single facet (by |β|, sign-matched, Bonferroni "
                f"p<{P_THRESHOLD}) is chosen to carry the domain-level "
                "coefficient. Fallback: domain-level '*' key if no facet "
                "passes the filter. Full OLS table in full_ols_betas."
            ),
        }

    dat_sha = _ipip_sha256(DEFAULT_DAT_PATH)
    out = {
        "_draft_status": "proposal",
        "_provenance": {
            "script": "scripts/draft_facet_coefficients.py",
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ipip120_dat_sha256": dat_sha,
            "n_respondents": N,
            "abs_beta_min": ABS_BETA_MIN,
            "p_threshold_bonferroni": P_THRESHOLD,
        },
        "_formula": (
            "value = 0.5 + sum(coeff_facet * (facet_score - 0.5)) for "
            "facet in IPIP-NEO facet scores (30 facets); clamp to [0, 1]"
        ),
        "_status": (
            "NOT SHIPPED. This is a backlog artifact for a future sprint "
            "that migrates BigFiveAdapter to facet-level inputs. Current "
            "BigFiveAdapter reads domain scores only."
        ),
        "traits": draft_traits,
    }
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRAFT_PATH.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {DRAFT_PATH}")
    total_retained = sum(
        len(t["coefficients"]) for t in draft_traits.values()
    )
    print(f"Drafted {len(draft_traits)} traits, "
          f"{total_retained} retained facet-coefficients total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
