"""Evolution Agent: configures and runs the Genetic Algorithm."""
from __future__ import annotations

from dataclasses import dataclass

from config import GAConfig
from core.fitness import FitnessEvaluator
from core.genetic_algorithm import GAResult, GeneticAlgorithm, ProgressCallback
from simulation.farm_simulator import FarmContext
from simulation.weather_simulator import Scenario


@dataclass
class EvolutionOutput:
    ga: GAResult
    weights: dict[str, float]
    profit_ceiling: float


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
