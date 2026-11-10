"""Operator invariants, elitism, seeds and a full default-configuration GA run."""
from __future__ import annotations

from pathlib import Path

import pytest

from agents.evolution_agent import EvolutionAgent
from config import DEFAULT_WEIGHTS, FALLOW, GAConfig
from core.constraints import check_constraints, repair
from core.crossover import crossover, uniform_crossover
from core.chromosome import Chromosome
from core.fitness import FitnessEvaluator
from core.genetic_algorithm import GeneticAlgorithm
from core.mutation import mutate
from core.population import initialize_population, random_chromosome

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def default_run(datasets):
    from simulation.farm_simulator import sample_context
    from simulation.scenario_engine import scenarios_from_frame
    context = sample_context(datasets)
    agent = EvolutionAgent()
    return context, agent.run(context, list(scenarios_from_frame(datasets.scenarios).values()), DEFAULT_WEIGHTS)


def test_population_is_distinct_and_feasible(context, rng):
    population = initialize_population(context, 50, rng, repair)
    assert len(population) == 50 and len({c.key for c in population}) == 50
    for chrom in population:
        assert [(g.plot_id, g.season) for g in chrom.genes] == context.slots
        assert check_constraints(context, chrom).feasible


def test_mutation_keeps_genes_valid(context, rng):
    chrom = random_chromosome(context, rng)
    for _ in range(50):
        chrom = mutate(context, chrom, 0.5, rng)
        for g in chrom.genes:
            assert 0.0 <= g.water_level <= 1.0 and 0.0 <= g.fertilizer_level <= 1.0
            assert g.crop_id == FALLOW or g.crop_id in context.options[g.season]
            assert g.planting_window in context.windows_for(g.crop_id, g.season)


def test_crossover_rejects_misaligned_parents(context, rng):
    a = random_chromosome(context, rng)
    with pytest.raises(ValueError, match="layout"):
        uniform_crossover(a, Chromosome(a.genes[::-1]), rng)
    c1, c2 = crossover(a, a, 1.0, rng)
    assert c1.key == c2.key == a.key


def test_elites_survive_unchanged(context, scenarios, rng):
    evaluator = FitnessEvaluator(context, list(scenarios.values()))
    ga = GeneticAlgorithm(evaluator, GAConfig(population_size=10, generations=2))
    population = initialize_population(context, 10, rng, repair)
    fitnesses = [evaluator.evaluate(c).fitness for c in population]
    top = sorted(range(10), key=lambda i: fitnesses[i], reverse=True)[:2]
    children = ga._next_generation(population, fitnesses)
    assert len(children) == 10 and [c.key for c in children[:2]] == [population[i].key for i in top]


@pytest.mark.parametrize("bad", [dict(population_size=2), dict(generations=0), dict(tournament_size=1),
                                 dict(crossover_probability=1.5), dict(mutation_probability=-0.1),
                                 dict(elitism=50), dict(seed=-1), dict(seed=1.5)])
def test_invalid_config_rejected(context, scenarios, bad):
    with pytest.raises(ValueError):
        GeneticAlgorithm(FitnessEvaluator(context, list(scenarios.values())), GAConfig(**bad))


def test_default_run_actually_evolves(default_run):
    context, out = default_run
    history = out.history
    assert out.ga.config == GAConfig() and len(history) == 20
    assert history[-1]["best_fitness"] > history[0]["best_fitness"]
    assert history[-1]["mean_fitness"] > history[0]["mean_fitness"]
    assert all(b >= a for a, b in zip([h["best_fitness"] for h in history], [h["best_fitness"] for h in history][1:]))
    assert out.ga.evaluations > GAConfig().population_size
    assert out.best_fitness.feasible and check_constraints(context, out.best).feasible
    assert out.best_fitness.fitness == pytest.approx(sum(out.best_fitness.contributions.values()))


def test_ranked_candidates_are_distinct_and_sorted(default_run):
    _, out = default_run
    fits = [r.fitness for _, r in out.ranked]
    assert len(out.ranked) == 5 and fits == sorted(fits, reverse=True)
    assert len({c.key for c, _ in out.ranked}) == 5 and out.ranked[0][0].key == out.best.key


def test_resilience_uses_every_scenario(default_run):
    _, out = default_run
    profits = out.best_fitness.scenario_profits
    assert set(profits) == {"normal", "drought", "excess_rainfall", "input_price_shock", "market_price_drop"}
    assert 0.0 <= out.best_fitness.components["resilience"] <= 1.0


def test_seed_controls_the_run(context, scenarios):
    def run(seed):
        evaluator = FitnessEvaluator(context, list(scenarios.values()))
        return GeneticAlgorithm(evaluator, GAConfig(population_size=12, generations=4, seed=seed)).run()
    a, b, c = run(1), run(1), run(2)
    assert [h["best_fitness"] for h in a.history] == [h["best_fitness"] for h in b.history]
    assert a.best.key == b.best.key
    assert [h["mean_fitness"] for h in a.history] != [h["mean_fitness"] for h in c.history]


def test_optimisation_never_touches_gemini(context, scenarios, monkeypatch):
    for path in [*sorted((ROOT / "core").glob("*.py")), ROOT / "agents" / "evolution_agent.py"]:
        source = path.read_text(encoding="utf-8").lower()
        assert "import" not in source or "gemini_service" not in source, path.name
    from services import gemini_service

    def boom(*_, **__):
        raise AssertionError("Gemini called during optimisation")
    monkeypatch.setattr(gemini_service.GeminiService, "generate_text", boom)
    monkeypatch.setattr(gemini_service.GeminiService, "generate_json", boom)
    out = EvolutionAgent().run(context, list(scenarios.values()), DEFAULT_WEIGHTS,
                               GAConfig(population_size=8, generations=2))
    assert len(out.history) == 2
