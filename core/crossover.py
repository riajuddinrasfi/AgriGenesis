"""Crossover operators on aligned plot-season genes."""
from __future__ import annotations

import numpy as np

from core.chromosome import Chromosome


def _aligned(a: Chromosome, b: Chromosome) -> None:
    slots_a = [(g.plot_id, g.season) for g in a.genes]
    slots_b = [(g.plot_id, g.season) for g in b.genes]
    if slots_a != slots_b:
        raise ValueError("Parents must have the same plot-season layout")


def uniform_crossover(a: Chromosome, b: Chromosome, rng: np.random.Generator) -> tuple[Chromosome, Chromosome]:
    """Swap each whole gene between the parents with probability 0.5."""
    _aligned(a, b)
    mask = rng.random(len(a.genes)) < 0.5
    child1 = [gb if m else ga for ga, gb, m in zip(a.genes, b.genes, mask)]
    child2 = [ga if m else gb for ga, gb, m in zip(a.genes, b.genes, mask)]
    return Chromosome(child1), Chromosome(child2)


def single_point_crossover(a: Chromosome, b: Chromosome, rng: np.random.Generator) -> tuple[Chromosome, Chromosome]:
    _aligned(a, b)
    if len(a.genes) < 2:
        return a.copy(), b.copy()
    point = int(rng.integers(1, len(a.genes)))
    return (Chromosome(a.genes[:point] + b.genes[point:]),
            Chromosome(b.genes[:point] + a.genes[point:]))


def crossover(a: Chromosome, b: Chromosome, probability: float, rng: np.random.Generator,
              method: str = "uniform") -> tuple[Chromosome, Chromosome]:
    """Apply crossover with ``probability``; otherwise return copies of the parents."""
    if rng.random() >= probability:
        return a.copy(), b.copy()
    if method == "single_point":
        return single_point_crossover(a, b, rng)
    return uniform_crossover(a, b, rng)
