"""Runs the genetic algorithm, seeded with baseline strategies, and benchmarks the result."""
from __future__ import annotations

from typing import Callable

import pandas as pd

from core.genetic_algorithm import GAParams, GAResult, GeneticAlgorithm
from services.strategy_service import baseline_strategies, compare_with_baselines, parameter_sweep
from simulation.farm_simulator import FarmContext


class EvolutionAgent:
    def evolve(self, context: FarmContext, params: GAParams | None = None,
               progress: Callable[[int, float], None] | None = None) -> GAResult:
        params = params or GAParams.from_config(context.config)
        seeds = list(baseline_strategies(context).values())
        return GeneticAlgorithm(context, params, seed_strategies=seeds).run(callback=progress)

    @staticmethod
    def benchmark(context: FarmContext, result: GAResult) -> pd.DataFrame:
        return compare_with_baselines(context, result)

    @staticmethod
    def sweep(context: FarmContext, params: GAParams, name: str, values: list,
              seeds: list[int] = (0, 1, 2)) -> pd.DataFrame:
        return parameter_sweep(context, params, name, values, list(seeds))
