"""Parent selection operators."""
from __future__ import annotations

import numpy as np

from core.chromosome import Chromosome


def tournament_select(population: list[Chromosome], fitnesses: list[float], tournament_size: int,
                      rng: np.random.Generator) -> Chromosome:
    """Pick ``tournament_size`` random members and return the fittest one."""
    if len(population) != len(fitnesses) or not population:
        raise ValueError("population and fitnesses must be non-empty and the same length")
    size = min(tournament_size, len(population))
    contenders = rng.choice(len(population), size=size, replace=False)
    winner = max(contenders, key=lambda i: fitnesses[i])
    return population[int(winner)]


def elite_indices(fitnesses: list[float], count: int) -> list[int]:
    """Indices of the ``count`` best members, best first."""
    return sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)[:count]
