"""Single-objective Genetic Algorithm with tournament selection, elitism and repair."""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Callable

from config import GAConfig
from core.chromosome import Chromosome
from core.constraints import repair
from core.crossover import crossover
from core.fitness import FitnessEvaluator, FitnessResult
from core.mutation import mutate
from core.population import initialize_population
from core.selection import elite_indices, tournament_select
from utils.random_generator import make_rng

ProgressCallback = Callable[[int, int, dict], None]


@dataclass
class GAResult:
    best: Chromosome
    best_fitness: FitnessResult
    history: list[dict]
    ranked: list[tuple[Chromosome, FitnessResult]]
    evaluations: int
    runtime_s: float
    config: GAConfig


class GeneticAlgorithm:
    def __init__(self, evaluator: FitnessEvaluator, config: GAConfig | None = None,
                 crossover_method: str = "uniform"):
        self.evaluator = evaluator
        self.context = evaluator.context
        self.config = config or GAConfig()
        self.config.validate()
        self.crossover_method = crossover_method
        self.rng = make_rng(self.config.seed)

    def _repair(self, context, chromosome, rng) -> Chromosome:
        return repair(context, chromosome, rng, self.evaluator.baseline)

    def _next_generation(self, population: list[Chromosome], fitnesses: list[float]) -> list[Chromosome]:
        cfg = self.config
        children = [population[i] for i in elite_indices(fitnesses, cfg.elitism)]
        while len(children) < cfg.population_size:
            mother = tournament_select(population, fitnesses, cfg.tournament_size, self.rng)
            father = tournament_select(population, fitnesses, cfg.tournament_size, self.rng)
            for child in crossover(mother, father, cfg.crossover_probability, self.rng, self.crossover_method):
                child = mutate(self.context, child, cfg.mutation_probability, self.rng)
                children.append(self._repair(self.context, child, self.rng))
                if len(children) == cfg.population_size:
                    break
        return children

    def run(self, progress: ProgressCallback | None = None) -> GAResult:
        """Evolve for ``config.generations`` generations and return the best strategies."""
        cfg = self.config
        start = time.perf_counter()
        population = initialize_population(self.context, cfg.population_size, self.rng, self._repair)
        history: list[dict] = []
        best: tuple[Chromosome, FitnessResult] | None = None
        for generation in range(1, cfg.generations + 1):
            results = [self.evaluator.evaluate(c) for c in population]
            fitnesses = [r.fitness for r in results]
            leader = max(range(len(results)), key=lambda i: fitnesses[i])
            if best is None or fitnesses[leader] > best[1].fitness:
                best = (population[leader], results[leader])
            row = {
                "generation": generation,
                "best_fitness": best[1].fitness,
                "generation_best": fitnesses[leader],
                "mean_fitness": statistics.fmean(fitnesses),
                "worst_fitness": min(fitnesses),
                "best_profit": best[1].metrics["net_profit"],
                "feasible_share": sum(r.feasible for r in results) / len(results),
                "unique_strategies": len({c.key for c in population}),
                "evaluations": self.evaluator.evaluations,
            }
            history.append(row)
            if progress:
                progress(generation, cfg.generations, row)
            if generation < cfg.generations:
                population = self._next_generation(population, fitnesses)
        return GAResult(best[0], best[1], history, self.evaluator.ranked(cfg.top_k),
                        self.evaluator.evaluations, time.perf_counter() - start, cfg)
