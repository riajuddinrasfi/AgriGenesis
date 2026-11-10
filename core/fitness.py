"""Fitness of a strategy: risk-adjusted profit plus soil health minus penalties."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.constraints import check_constraints
from simulation.farm_simulator import FarmContext, simulate
from utils.calculations import weighted_mean_std


@dataclass
class FitnessBreakdown:
    fitness: float
    expected_profit: float
    profit_std: float
    worst_case_profit: float
    soil_health: float
    penalty: float
    feasible: bool

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def risk_aversion(context: FarmContext) -> float:
    """Configured risk aversion scaled by the farm's own risk tolerance (0.5 = neutral)."""
    base = float(context.config.get("fitness", {}).get("risk_aversion", 0.5))
    tolerance = float(context.farm.get("risk_tolerance", 0.5))
    return base * 2.0 * (1.0 - tolerance)


def evaluate(context: FarmContext, genes: np.ndarray) -> FitnessBreakdown:
    cfg = context.config.get("fitness", {})
    result = simulate(context, genes, context.scenarios)
    probs = context.scenarios["probability"].to_numpy(dtype=float)
    profits = result.total_profit
    expected, std = weighted_mean_std(profits, probs)
    final_nitrogen, _ = weighted_mean_std(result.final_nitrogen, probs)
    nitrogen_change = final_nitrogen - float(context.farm["soil_nitrogen"])
    total_area = context.n_plots * context.plot_area
    soil = nitrogen_change * total_area * float(cfg.get("soil_health_weight", 20.0))
    constraints = check_constraints(context, genes)
    fitness = expected - risk_aversion(context) * std + soil - constraints.penalty
    return FitnessBreakdown(
        fitness=float(fitness),
        expected_profit=expected,
        profit_std=std,
        worst_case_profit=float(profits.min()),
        soil_health=float(soil),
        penalty=float(constraints.penalty),
        feasible=constraints.feasible,
    )
