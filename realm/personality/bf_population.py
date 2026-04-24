"""Synthetic Big Five (OCEAN) population sampler.

Samples N Big Five score vectors from a multivariate normal with population
norms (Costa & McCrae adult, mean=0.50, std=0.17 on the [0,1] scale) and a
literature-documented intercorrelation matrix. Output is clamped to [0, 1].

Used by validity-study scripts that need to feed BigFiveAdapter a realistic
synthetic population. Real human Big Five data should always be preferred
when available; this module exists for controlled studies where REALM needs
a known input distribution to test the BigFive path end-to-end.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

OCEAN: tuple[str, ...] = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)

# Literature-documented Big Five intercorrelation pairs (median of meta-analyses
# on 0.0-1.0 normalized scale). Sources: DeYoung et al. 2007 BFAS, Costa &
# McCrae 1992 NEO-PI-R manual, plus replications in van der Linden et al. 2010
# (general factor of personality). Pairs not listed default to 0.0.
DEFAULT_CORRELATIONS: dict[tuple[str, str], float] = {
    ("openness", "extraversion"): +0.15,
    ("openness", "conscientiousness"): -0.10,
    ("conscientiousness", "agreeableness"): +0.20,
    ("conscientiousness", "neuroticism"): -0.25,
    ("extraversion", "agreeableness"): +0.15,
    ("extraversion", "neuroticism"): -0.20,
}


def sample_bf_population(
    n: int,
    seed: int = 42,
    correlations: Mapping[tuple[str, str], float] | None = None,
    target_mean: float = 0.50,
    target_std: float = 0.17,
) -> list[dict[str, float]]:
    """Sample N OCEAN dicts from correlated multivariate normal, clamped to [0,1].

    Args:
        n: number of samples to generate (>= 1).
        seed: RNG seed for reproducibility.
        correlations: dict mapping (trait_a, trait_b) tuples to Pearson r.
            Pairs may be specified in either order; diagonal forced to 1.0.
            Pairs not present default to 0.0. Defaults to DEFAULT_CORRELATIONS.
        target_mean: per-trait mean before clamp (default 0.50, Costa & McCrae).
        target_std: per-trait std before clamp (default 0.17, Costa & McCrae).

    Returns:
        List of n dicts with keys {openness, conscientiousness, extraversion,
        agreeableness, neuroticism}, each value in [0.0, 1.0].

    Raises:
        ValueError: n < 1, target_std <= 0, unknown trait name, or correlation
            matrix is not positive semi-definite.

    Notes:
        Clamping to [0,1] truncates ~0.33% of samples per tail when (mean=0.5,
        std=0.17), which slightly compresses observed std below target.
        Acceptable for validity-study purposes; use truncated normal sampling
        if exact std preservation is required.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if target_std <= 0:
        raise ValueError(f"target_std must be positive, got {target_std}")

    corrs = dict(correlations) if correlations is not None else dict(DEFAULT_CORRELATIONS)

    corr_matrix = _build_correlation_matrix(corrs)
    cov_matrix = corr_matrix * (target_std ** 2)

    # Validate PSD via Cholesky factorization.
    try:
        np.linalg.cholesky(cov_matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"Correlation matrix is not positive semi-definite: {corrs}",
        ) from exc

    rng = np.random.default_rng(seed)
    means = np.full(len(OCEAN), target_mean)
    samples = rng.multivariate_normal(means, cov_matrix, size=n)
    samples = np.clip(samples, 0.0, 1.0)

    return [
        {trait: float(samples[i, j]) for j, trait in enumerate(OCEAN)}
        for i in range(n)
    ]


def _build_correlation_matrix(
    correlations: Mapping[tuple[str, str], float],
) -> np.ndarray:
    """Build symmetric 5x5 correlation matrix from pair dict.

    Pairs may be in either order (a, b) or (b, a). Diagonal forced to 1.0.
    Missing pairs default to 0.0. Unknown trait names raise ValueError.
    """
    n = len(OCEAN)
    idx = {trait: i for i, trait in enumerate(OCEAN)}
    mat = np.eye(n)
    for (a, b), r in correlations.items():
        if a not in idx or b not in idx:
            raise ValueError(
                f"Unknown trait in correlation pair ({a}, {b}); "
                f"expected one of {OCEAN}",
            )
        if a == b:
            continue
        ia, ib = idx[a], idx[b]
        mat[ia, ib] = r
        mat[ib, ia] = r
    return mat
