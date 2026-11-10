"""Genetic algorithm that evolves plot-by-season crop plans."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Callable

import numpy as np
import pandas as pd

from core.chromosome import Chromosome
from core.crossover import crossover
from core.fitness import FitnessBreakdown, evaluate
from core.mutation import mutate
from core.population import FitnessCache, Population
from core.selection import elite_indices, tournament
from simulation.farm_simulator import FarmContext
from utils.random_generator import make_rng


@dataclass
class GAParams:
    population_size: int = 60
    generations: int = 80
    crossover_rate: float = 0.85
    mutation_rate: float = 0.08
    tournament_size: int = 3
    elitism: int = 2
    seed: int | None = 42
    patience: int | None = 30
    seed_with_baselines: bool = True

    @classmethod
    def from_config(cls, config: dict, **overrides) -> "GAParams":
        names = {f.name for f in fields(cls)}
        values = {k: v for k, v in config.get("genetic_algorithm", {}).items() if k in names}
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)

    def validate(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size must be at least 2")
        if self.generations < 1:
            raise ValueError("generations must be at least 1")
        if not 0 <= self.crossover_rate <= 1 or not 0 <= self.mutation_rate <= 1:
            raise ValueError("crossover_rate and mutation_rate must be within [0, 1]")
        if not 1 <= self.tournament_size <= self.population_size:
            raise ValueError("tournament_size must be between 1 and population_size")
        if not 0 <= self.elitism < self.population_size:
            raise ValueError("elitism must be between 0 and population_size - 1")


@dataclass
class GAResult:
    best_genes: np.ndarray
    best: FitnessBreakdown
    history: pd.DataFrame
    evaluations: int
    generations_run: int
    params: GAParams = field(default_factory=GAParams)


class GeneticAlgorithm:
    def __init__(
        self,
        context: FarmContext,
        params: GAParams | None = None,
        fitness_fn: Callable[[FarmContext, np.ndarray], FitnessBreakdown] = evaluate,
        seed_strategies: list[np.ndarray] | None = None,
    ):
        self.context = context
        self.params = params or GAParams()
        self.params.validate()
        self.cache = FitnessCache(context, fitness_fn)
        self.rng = make_rng(self.params.seed)
        self.seed_strategies = list(seed_strategies or []) if self.params.seed_with_baselines else []

    def _breed(self, population: Population) -> Population:
        p, scores = self.params, population.scores
        members = [population.members[i].copy() for i in elite_indices(scores, p.elitism)]
        while len(members) < p.population_size:
            a = population.members[tournament(scores, p.tournament_size, self.rng)].genes
            b = population.members[tournament(scores, p.tournament_size, self.rng)].genes
            for child in crossover(a, b, p.crossover_rate, self.rng):
                if len(members) < p.population_size:
                    members.append(Chromosome(mutate(child, self.context.allowed, p.mutation_rate, self.rng)))
        return Population(members)

    def run(self, callback: Callable[[int, float], None] | None = None) -> GAResult:
        p = self.params
        population = Population.initial(self.context, p.population_size, self.rng, self.seed_strategies)
        history, best_genes, best, stale, generation = [], None, None, 0, 0
        for generation in range(1, p.generations + 1):
            population.evaluate(self.cache)
            leader, leader_fit = population.best()
            if best is None or leader_fit.fitness > best.fitness + 1e-9:
                best_genes, best, stale = leader.genes.copy(), leader_fit, 0
            else:
                stale += 1
            history.append({"generation": generation, "best_fitness": best.fitness,
                            "best_expected_profit": best.expected_profit, **population.stats()})
            if callback:
                callback(generation, best.fitness)
            if (p.patience and stale >= p.patience) or generation == p.generations:
                break
            population = self._breed(population)
        return GAResult(best_genes, best, pd.DataFrame(history), len(self.cache), generation, p)
