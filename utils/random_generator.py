"""Seeded random number generation so every run is reproducible."""
from __future__ import annotations

import numpy as np


def make_rng(seed: int | None = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


def random_level(rng: np.random.Generator, low: float = 0.0, high: float = 1.0) -> float:
    """A management factor in ``[low, high]`` rounded to 2 decimals."""
    return round(float(rng.uniform(low, high)), 2)


def choice(rng: np.random.Generator, options: list):
    """Pick one element of a non-empty list."""
    if not options:
        raise ValueError("Cannot choose from an empty list")
    return options[int(rng.integers(len(options)))]
