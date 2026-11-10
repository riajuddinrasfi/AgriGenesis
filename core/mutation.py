"""Mutation operators that keep every gene within the season's allowed crops."""
from __future__ import annotations

import numpy as np

SWAP_PROBABILITY = 0.1


def random_reset(genes: np.ndarray, allowed: list[list[int]], rate: float,
                 rng: np.random.Generator) -> np.ndarray:
    genes = genes.copy()
    hits = rng.random(genes.shape) < rate
    for plot, season in zip(*np.nonzero(hits)):
        genes[plot, season] = rng.choice(allowed[season])
    return genes


def swap_plots(genes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Exchange the crops of two plots in one season."""
    genes = genes.copy()
    if genes.shape[0] > 1:
        a, b = rng.choice(genes.shape[0], size=2, replace=False)
        s = rng.integers(genes.shape[1])
        genes[[a, b], s] = genes[[b, a], s]
    return genes


def mutate(genes: np.ndarray, allowed: list[list[int]], rate: float,
           rng: np.random.Generator) -> np.ndarray:
    genes = random_reset(genes, allowed, rate, rng)
    if rng.random() < SWAP_PROBABILITY:
        genes = swap_plots(genes, rng)
    return genes
