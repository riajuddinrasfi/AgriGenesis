"""Simulation Agent: single entry point for running the deterministic farm simulator."""
from __future__ import annotations

import pandas as pd

from core.chromosome import Chromosome
from simulation.farm_simulator import FarmContext, SimulationResult, simulate_farm
from simulation.scenario_engine import profit_retention, resilience_score, run_scenarios, scenario_table
from simulation.weather_simulator import Scenario


class SimulationAgent:
    def simulate(self, context: FarmContext, chromosome: Chromosome, scenario: Scenario) -> SimulationResult:
        return simulate_farm(context, chromosome, scenario)

    def evaluate_scenarios(self, context: FarmContext, chromosome: Chromosome,
                           scenarios: list[Scenario]) -> dict:
        """Results for every scenario plus the resilience summary."""
        results = run_scenarios(context, chromosome, scenarios)
        lookup = {s.scenario_id: s for s in scenarios}
        return {
            "results": results,
            "table": scenario_table(results, lookup),
            "retention": profit_retention(results),
            "resilience": resilience_score(results),
        }

    @staticmethod
    def plan_table(result: SimulationResult) -> pd.DataFrame:
        columns = ["plot_id", "season", "season_name", "crop_name", "area_ha", "planting_window",
                   "water_level", "fertilizer_level", "irrigation_mm", "water_use_m3", "fertilizer_kg",
                   "yield_t", "revenue", "seed_cost", "fertilizer_cost", "labor_cost", "irrigation_cost",
                   "total_cost", "profit", "water_factor", "soil_factor", "weather_factor",
                   "nutrient_factor", "waterlogged", "soil_health_start", "soil_health_end"]
        return pd.DataFrame(result.gene_results)[columns]
