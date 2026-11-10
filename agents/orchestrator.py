"""Coordinates the agents into one planning run:

farm input -> agronomy -> scenarios -> evolution (GA) -> simulation -> research.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from agents.agronomy_agent import AgronomyAgent
from agents.evolution_agent import EvolutionAgent
from agents.farm_input_agent import FarmInputAgent
from agents.research_agent import ResearchAgent
from agents.scenario_agent import ScenarioAgent
from agents.simulation_agent import SimulationAgent, StrategyEvaluation
from core.chromosome import Chromosome
from core.genetic_algorithm import GAParams, GAResult
from services.data_loader import DataLoader
from services.gemini_service import GeminiService
from simulation.farm_simulator import FarmContext


@dataclass
class PlanningReport:
    context: FarmContext
    ga_result: GAResult
    plan: pd.DataFrame
    evaluation: StrategyEvaluation
    comparison: pd.DataFrame
    insights: list[str]
    warnings: list[str]
    narrative: str | None = None
    narrative_source: str = "rule-based"

    def __getattr__(self, name):
        # details, scenarios, usage, violations, monte_carlo, risk
        if name != "evaluation" and "evaluation" in self.__dict__:
            return getattr(self.evaluation, name)
        raise AttributeError(name)


class Orchestrator:
    def __init__(self, data_dir: str | None = None, gemini: GeminiService | None = None):
        self.loader = DataLoader(data_dir)
        self.farm_agent = FarmInputAgent(self.loader)
        self.config = {k: v for k, v in self.farm_agent.config.items() if k != "farm"}
        self.agronomy_agent = AgronomyAgent(self.loader)
        self.scenario_agent = ScenarioAgent(self.loader)
        self.simulation_agent = SimulationAgent()
        self.evolution_agent = EvolutionAgent()
        self.research_agent = ResearchAgent(gemini)

    def build_context(
        self,
        farm_id: str,
        scenario_names: list[str] | None = None,
        farm_overrides: dict | None = None,
        fitness_overrides: dict | None = None,
        scenarios: pd.DataFrame | None = None,
    ) -> tuple[FarmContext, list[str]]:
        farm, warnings = self.farm_agent.prepare(farm_id, farm_overrides)
        config = copy.deepcopy(self.config)
        config.setdefault("fitness", {}).update(fitness_overrides or {})
        seasons = config["seasons"]
        context = FarmContext(
            farm=farm,
            crops=self.agronomy_agent.crops,
            seasons=seasons,
            scenarios=scenarios if scenarios is not None else self.scenario_agent.select(scenario_names),
            rotation=self.agronomy_agent.rotation_matrix(config.get("rotation")),
            allowed=self.agronomy_agent.allowed_genes(farm, seasons),
            config=config,
        )
        return context, warnings

    def plan(
        self,
        farm_id: str,
        ga_params: GAParams | None = None,
        scenario_names: list[str] | None = None,
        farm_overrides: dict | None = None,
        fitness_overrides: dict | None = None,
        progress: Callable[[int, float], None] | None = None,
        use_gemini: bool = False,
    ) -> PlanningReport:
        context, warnings = self.build_context(farm_id, scenario_names, farm_overrides, fitness_overrides)
        params = ga_params or GAParams.from_config(self.config)
        result = self.evolution_agent.evolve(context, params, progress)
        genes = result.best_genes
        plan = Chromosome(genes).to_frame(context)
        evaluation = self.simulation_agent.evaluate(context, genes, seed=params.seed)
        comparison = self.evolution_agent.benchmark(context, result)
        insights = self.research_agent.insights(
            context, plan, comparison, evaluation.scenarios, evaluation.usage, evaluation.violations)
        report = PlanningReport(context, result, plan, evaluation, comparison, insights, warnings)
        if use_gemini:
            self.write_narrative(report)
        return report

    def write_narrative(self, report: PlanningReport) -> PlanningReport:
        summary = self.research_agent.summary(
            report.context, report.plan, report.comparison, report.scenarios, report.risk, report.insights)
        report.narrative, report.narrative_source = self.research_agent.narrative(summary)
        return report
