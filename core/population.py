"""A population of chromosomes with cached fitness evaluation."""
from __future__ import annotations

from typing import Callable

import numpy as np

from core.chromosome import Chromosome
from core.fitness import FitnessBreakdown
from simulation.farm_simulator import FarmContext


class FitnessCache:
    def __init__(self, context: FarmContext, fitness_fn: Callable[[FarmContext, np.ndarray], FitnessBreakdown]):
        self.context = context
        self.fitness_fn = fitness_fn
        self._store: dict[bytes, FitnessBreakdown] = {}

    def __call__(self, chromosome: Chromosome) -> FitnessBreakdown:
        key = chromosome.key
        if key not in self._store:
            self._store[key] = self.fitness_fn(self.context, chromosome.genes)
        return self._store[key]

    def __len__(self) -> int:
        return len(self._store)


class Population:
    def __init__(self, members: list[Chromosome]):
        if not members:
            raise ValueError("Population must not be empty")
        self.members = members
        self.results: list[FitnessBreakdown] = []
        self.scores = np.array([])

    @classmethod
    def initial(cls, context: FarmContext, size: int, rng: np.random.Generator,
                seeds: list[np.ndarray] | None = None) -> "Population":
        members = [Chromosome(g.copy()) for g in (seeds or [])][:size]
        while len(members) < size:
            members.append(Chromosome.random(context, rng))
        return cls(members)

    def evaluate(self, cache: FitnessCache) -> np.ndarray:
        self.results = [cache(m) for m in self.members]
        self.scores = np.array([r.fitness for r in self.results])
        return self.scores

    def best(self) -> tuple[Chromosome, FitnessBreakdown]:
        i = int(np.argmax(self.scores))
        return self.members[i], self.results[i]

    def stats(self) -> dict:
        return {
            "mean_fitness": float(self.scores.mean()),
            "worst_fitness": float(self.scores.min()),
            "feasible_share": float(np.mean([r.feasible for r in self.results])),
            "diversity": len({m.key for m in self.members}) / len(self.members),
        }

    def __len__(self) -> int:
        return len(self.members)
