"""Evolution Agent: configures and runs the Genetic Algorithm.

Optimisation is pure deterministic Python: Gemini is never called while evolving.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import GAConfig
from core.chromosome import Chromosome
from core.fitness import FitnessEvaluator, FitnessResult
from core.genetic_algorithm import GAResult, GeneticAlgorithm, ProgressCallback
from simulation.farm_simulator import FarmContext
from simulation.weather_simulator import Scenario


@dataclass
class EvolutionOutput:
    ga: GAResult
    weights: dict[str, float]
    profit_ceiling: float

    @property
    def best(self) -> Chromosome:
        return self.ga.best

    @property
    def best_fitness(self) -> FitnessResult:
        return self.ga.best_fitness

    @property
    def ranked(self) -> list[tuple[Chromosome, FitnessResult]]:
        return self.ga.ranked

    @property
    def history(self) -> list[dict]:
        """Per-generation convergence rows (best, mean and worst fitness, diversity, evaluations)."""
        return self.ga.history


class EvolutionAgent:
    def run(self, context: FarmContext, scenarios: list[Scenario], weights: dict[str, float],
            config: GAConfig | None = None, progress: ProgressCallback | None = None,
            crossover_method: str = "uniform") -> EvolutionOutput:
        """Evolve strategies; fitness calls the simulator for every scenario of every candidate."""
        if not any(context.options.values()):
            raise ValueError("No feasible crops: adjust the farm setup before optimising")
        evaluator = FitnessEvaluator(context, scenarios, weights)
        ga = GeneticAlgorithm(evaluator, config or GAConfig(), crossover_method).run(progress)
        return EvolutionOutput(ga, evaluator.weights, evaluator.profit_ceiling)
