"""End-to-end QA path without Gemini: sample farm -> validation -> population -> GA -> scenarios -> comparison -> report."""
from __future__ import annotations

import numpy as np
import pytest

from agents.orchestrator import Orchestrator
from config import GAConfig, GeminiSettings
from core.chromosome import Chromosome
from core.constraints import check_constraints, repair
from core.population import initialize_population
from services.data_loader import farm_row_to_input, load_farms, load_sample_farm
from services.gemini_service import GeminiService
from services.report_service import build_markdown_report, save_report
from services.strategy_service import comparison_frame, save_result

ALL_SCENARIOS = ["normal", "drought", "excess_rainfall", "input_price_shock", "market_price_drop"]


@pytest.fixture(scope="module")
def orch():
    return Orchestrator(gemini=GeminiService(GeminiSettings("", "unused")))


def test_end_to_end_without_gemini(orch, tmp_path):
    farm = load_sample_farm()
    profile, agronomy, context = orch.prepare(farm, use_gemini=False)
    assert agronomy.ok and profile.farm_name == farm["farm_name"]

    population = initialize_population(context, 20, np.random.default_rng(7), repair)
    assert len(population) == 20 and all(check_constraints(context, c).feasible for c in population)

    result = orch.run(farm, ga_config=GAConfig(population_size=20, generations=6, seed=7),
                      scenario_ids=ALL_SCENARIOS, use_gemini=False)
    history = result["fitness_history"]
    assert len(history) == 6 and history[-1]["best_fitness"] >= history[0]["best_fitness"]
    assert result["validation_results"]["best_strategy_constraints"]["feasible"]
    assert result["best_fitness"] == result["ranked_strategies"][0]["fitness"]

    evaluation = orch.evaluate_strategy(result["farm_profile"], result["best_strategy"]["genes"],
                                        orch.scenario.select(ALL_SCENARIOS, []))
    assert set(evaluation["results"]) == set(ALL_SCENARIOS)
    normal = evaluation["results"]["normal"].totals
    assert normal["net_profit"] == pytest.approx(result["best_strategy"]["metrics"]["net_profit"])
    assert normal["net_profit"] == pytest.approx(normal["revenue"] - normal["total_cost"])

    frame = comparison_frame(result["ranked_strategies"])
    assert len(frame) == len(result["ranked_strategies"]) >= 2
    assert list(frame["fitness"]) == sorted(frame["fitness"], reverse=True)

    report = result["research_report"]
    assert report["source"] == "deterministic" and not result["ai_status"]["available"]
    markdown = build_markdown_report(result)
    assert result["farm_profile"]["farm_name"] in markdown and "synthetic" in markdown.lower()
    assert save_report(markdown, tmp_path).exists() and save_result(result, tmp_path).exists()


@pytest.mark.parametrize("seed", [1, 2])
def test_every_ranked_strategy_respects_constraints_on_all_farms(orch, seed):
    for _, row in load_farms().iterrows():
        result = orch.run(farm_row_to_input(row), ga_config=GAConfig(population_size=14, generations=4, seed=seed),
                          use_gemini=False)
        _, _, context = orch.prepare(result["farm_profile"])
        budget, water = result["farm_profile"]["budget_usd"], result["farm_profile"]["available_water_m3"]
        for strategy in result["ranked_strategies"]:
            report = check_constraints(context, Chromosome.from_records(strategy["genes"]))
            assert report.feasible, (row["farm_id"], report.violations)
            assert report.total_cost <= budget + 1e-6 and report.water_demand_m3 <= water + 1e-6
            assert strategy["metrics"]["total_cost"] <= budget + 1e-6
