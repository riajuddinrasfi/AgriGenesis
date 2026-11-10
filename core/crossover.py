"""Crossover operators for plot-by-season crop plans."""
from __future__ import annotations

import numpy as np


def plot_crossover(a: np.ndarray, b: np.ndarray, rng: np.random.Generator):
    """Swap whole plot rotations, keeping each plot's sequence intact."""
    mask = np.broadcast_to(rng.random((a.shape[0], 1)) < 0.5, a.shape)
    return np.where(mask, a, b), np.where(mask, b, a)


def uniform_crossover(a: np.ndarray, b: np.ndarray, rng: np.random.Generator):
    mask = rng.random(a.shape) < 0.5
    return np.where(mask, a, b), np.where(mask, b, a)


def crossover(a: np.ndarray, b: np.ndarray, rate: float, rng: np.random.Generator):
    """With probability ``rate`` apply plot or uniform crossover (50/50); otherwise copy."""
    if rng.random() >= rate:
        return a.copy(), b.copy()
    operator = plot_crossover if rng.random() < 0.5 else uniform_crossover
    return operator(a, b, rng)
