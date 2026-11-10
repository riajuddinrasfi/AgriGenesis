"""Orchestrator: Farm Input -> Validation -> Agronomy -> Scenarios -> Evolution -> Simulation -> Research."""
from __future__ import annotations

from dataclasses import asdict

from agents.agronomy_agent import AgronomyAgent, AgronomyReport
from agents.evolution_agent import EvolutionAgent
from agents.farm_input_agent import FarmInputAgent
from agents.research_agent import ResearchAgent
from agents.scenario_agent import ScenarioAgent
from agents.simulation_agent import SimulationAgent
from config import DEFAULT_WEIGHTS, SEASONS, SYNTHETIC_DATA_NOTICE, GAConfig
from core.chromosome import Chromosome
from core.constraints import check_constraints
from core.genetic_algorithm import ProgressCallback
from services.data_loader import Datasets, load_datasets
from services.gemini_service import GeminiService
from services.strategy_service import ranked_records, strategy_record
from services.validation_service import FarmProfile
from simulation.farm_simulator import FarmContext, build_context
from simulation.weather_simulator import Scenario

ASSUMPTIONS = [
    SYNTHETIC_DATA_NOTICE,
    "Yield = area x base yield x water factor x soil factor x weather factor x nutrient factor.",
    "Water supply above 100% of the crop requirement adds no yield; above 110% a waterlogging penalty applies.",
    "Each plot has equal area; soil health carries over between seasons on the same plot.",
    "Costs = seed + fertilizer + labour + irrigation; profit = revenue - total cost.",
    "Budget and water limits are checked against the normal scenario; adverse scenarios test resilience.",
    "AI text explains these numbers only; all numbers come from the deterministic simulator.",
]


class Orchestrator:
    def __init__(self, datasets: Datasets | None = None, gemini: GeminiService | None = None):
        self.datasets = datasets or load_datasets()
        self.gemini = gemini or GeminiService()
        self.farm_input = FarmInputAgent(self.datasets, self.gemini)
        self.agronomy = AgronomyAgent(self.datasets)
        self.scenario = ScenarioAgent(self.datasets, self.gemini)
        self.simulation = SimulationAgent()
        self.evolution = EvolutionAgent()
        self.research = ResearchAgent(self.gemini)

    def prepare(self, farm_input: dict | FarmProfile) -> tuple[FarmProfile, AgronomyReport, FarmContext]:
        """Validate input, run agronomy checks and build the simulation context."""
        profile = farm_input if isinstance(farm_input, FarmProfile) else self.farm_input.from_form(farm_input)
        agronomy = self.agronomy.assess(profile)
        context = build_context(profile, self.datasets, agronomy.feasible_options)
        return profile, agronomy, context

    def evaluate_strategy(self, farm_input: dict | FarmProfile, genes: list[dict],
                          scenarios: list[Scenario]) -> dict:
        """Re-simulate a saved strategy under any scenarios (no optimisation)."""
        _, _, context = self.prepare(farm_input)
        return self.simulation.evaluate_scenarios(context, Chromosome.from_records(genes), scenarios)

    @staticmethod
    def _facts(profile: FarmProfile, best: dict, scenarios: list[Scenario], weights: dict) -> dict:
        names = {s.scenario_id: s.scenario_name for s in scenarios}
        return {
            "farm": {k: v for k, v in profile.to_dict().items() if k != "rainfall_mm"},
            "weights": weights,
            "best_fitness": best["fitness"],
            "fitness_components": best["components"],
            "best_metrics": best["metrics"],
            "allocation": {SEASONS[s]["name"]: crops for s, crops in best["allocation"].items()},
            "plan": best["plan"],
            "scenario_profits": {names.get(k, k): v for k, v in best["scenario_profits"].items()},
            "data_note": SYNTHETIC_DATA_NOTICE,
        }

    def run(self, farm_input: dict | FarmProfile, weights: dict | None = None,
            ga_config: GAConfig | None = None, scenario_ids: list[str] | None = None,
            custom_scenarios: list[Scenario] | None = None, use_gemini: bool = True,
            progress: ProgressCallback | None = None) -> dict:
        profile, agronomy, context = self.prepare(farm_input)
        if not agronomy.ok:
            raise ValueError("; ".join(m["message"] for m in agronomy.messages if m["level"] == "error"))
        scenarios = self.scenario.select(scenario_ids, custom_scenarios)
        evolution = self.evolution.run(context, scenarios, weights or DEFAULT_WEIGHTS, ga_config, progress)
        ga = evolution.ga

        best = strategy_record(context, 1, ga.best, ga.best_fitness)
        ranked = ranked_records(context, ga.ranked)
        evaluation = self.simulation.evaluate_scenarios(context, ga.best, scenarios)
        baseline = evaluation["results"]["normal"]
        constraints = check_constraints(context, ga.best, scenarios[0])
        scenario_results = {
            f"#{s['rank']}": self.simulation.evaluate_scenarios(
                context, Chromosome.from_records(s["genes"]), scenarios)["table"].to_dict("records")
            for s in ranked
        }
        research = self.research.explain(self._facts(profile, best, scenarios, evolution.weights), use_gemini)
        return {
            "farm_profile": profile.to_dict(),
            "validation_results": {
                "farm_valid": True,
                "messages": agronomy.messages,
                "feasible_options": agronomy.feasible_options,
                "suitability": agronomy.table.to_dict("records"),
                "best_strategy_constraints": {
                    "feasible": constraints.feasible, "violations": constraints.violations,
                    "land_used_ha": constraints.land_used_ha, "total_cost": constraints.total_cost,
                    "water_demand_m3": constraints.water_demand_m3,
                },
            },
            "scenarios": {s.scenario_id: s.to_dict() for s in scenarios},
            "best_strategy": best,
            "ranked_strategies": ranked,
            "best_fitness": ga.best_fitness.fitness,
            "fitness_history": ga.history,
            "simulation_metrics": {"totals": baseline.totals, "gene_results": baseline.gene_results,
                                   "resilience": evaluation["resilience"], "retention": evaluation["retention"]},
            "scenario_results": {"best": evaluation["table"].to_dict("records"), "ranked": scenario_results},
            "research_report": research,
            "assumptions": ASSUMPTIONS,
            "optimization": {"config": asdict(ga.config), "weights": evolution.weights,
                             "evaluations": ga.evaluations, "runtime_s": ga.runtime_s,
                             "profit_ceiling": evolution.profit_ceiling},
        }
