"""Evaluates a strategy: per-plot details, scenarios, resources, constraints and Monte Carlo risk."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.constraints import check_constraints
from core.fitness import FitnessBreakdown, evaluate
from simulation.farm_simulator import (
    FarmContext, monte_carlo, resource_usage, scenario_breakdown, simulate,
)
from utils.calculations import risk_metrics


@dataclass
class StrategyEvaluation:
    fitness: FitnessBreakdown
    details: pd.DataFrame
    scenarios: pd.DataFrame
    usage: pd.DataFrame
    violations: pd.DataFrame
    monte_carlo: pd.DataFrame
    risk: dict


class SimulationAgent:
    def evaluate(self, context: FarmContext, genes: np.ndarray, seed: int | None = 0,
                 n_runs: int | None = None) -> StrategyEvaluation:
        runs = n_runs or int(context.config.get("simulation", {}).get("monte_carlo_runs", 500))
        mc = monte_carlo(context, genes, n_runs=runs, seed=seed)
        return StrategyEvaluation(
            fitness=evaluate(context, genes),
            details=simulate(context, genes, detailed=True).details,
            scenarios=scenario_breakdown(context, genes),
            usage=resource_usage(context, genes),
            violations=check_constraints(context, genes).to_frame(),
            monte_carlo=mc,
            risk=risk_metrics(mc["profit"]),
        )

    @staticmethod
    def what_if(context: FarmContext, genes: np.ndarray, scenario: pd.DataFrame) -> pd.DataFrame:
        """Per-plot results of ``genes`` under one ad-hoc scenario."""
        return simulate(context, genes, scenario, detailed=True).details
