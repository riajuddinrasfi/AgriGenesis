"""Seeded random number helpers so every run is reproducible."""
from __future__ import annotations

import numpy as np


def make_rng(seed: int | None = None) -> np.random.Generator:
    return np.random.default_rng(seed)


def spawn_seeds(seed: int | None, n: int) -> list[int]:
    return [int(s) for s in make_rng(seed).integers(0, 2**31 - 1, size=n)]


def mean_one_lognormal(rng: np.random.Generator, sd: float, size) -> np.ndarray:
    """Multiplicative noise with expected value 1."""
    if sd <= 0:
        return np.ones(size)
    return rng.lognormal(-0.5 * sd**2, sd, size=size)
