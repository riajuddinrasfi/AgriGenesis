"""Population initialisation, selection, crossover, mutation and full GA runs."""
from __future__ import annotations

import numpy as np

from config import DEFAULT_WEIGHTS, GAConfig
from core.constraints import check_constraints, repair
from core.crossover import crossover, single_point_crossover, uniform_crossover
from core.fitness import FitnessEvaluator
from core.genetic_algorithm import GeneticAlgorithm
from core.mutation import mutate
from core.population import initialize_population, random_chromosome
from core.selection import elite_indices, tournament_select


def test_default_config_matches_spec():
    cfg = GAConfig()
    assert (cfg.population_size, cfg.generations, cfg.seed, cfg.tournament_size) == (50, 20, 42, 3)
    assert (cfg.crossover_probability, cfg.mutation_probability, cfg.elitism) == (0.80, 0.10, 2)


def test_population_initialisation(context, rng):
    population = initialize_population(context, 20, rng, repair)
    assert len(population) == 20
    assert len({c.key for c in population}) > 1
    assert all(check_constraints(context, c).feasible for c in population)


def test_crossover_mixes_parent_genes(context, rng):
    a, b = random_chromosome(context, rng), random_chromosome(context, rng)
    for operator in (uniform_crossover, single_point_crossover):
        c1, c2 = operator(a, b, rng)
        for i, (g1, g2) in enumerate(zip(c1.genes, c2.genes)):
            assert {g1, g2} == {a.genes[i], b.genes[i]}
            assert (g1.plot_id, g1.season) == (a.genes[i].plot_id, a.genes[i].season)
    c1, c2 = crossover(a, b, 0.0, rng)
    assert c1.key == a.key and c2.key == b.key


def test_mutation(context, rng):
    chrom = random_chromosome(context, rng)
    assert mutate(context, chrom, 0.0, rng).key == chrom.key
    mutated = mutate(context, chrom, 1.0, rng)
    assert mutated.key != chrom.key
    assert [(g.plot_id, g.season) for g in mutated.genes] == context.slots


def test_selection():
    rng = np.random.default_rng(0)
    population, fitnesses = ["a", "b", "c", "d"], [0.1, 0.9, 0.5, 0.2]
    assert elite_indices(fitnesses, 2) == [1, 2]
    picks = [tournament_select(population, fitnesses, 4, rng) for _ in range(5)]
    assert picks == ["b"] * 5


def _run(context, scenarios, seed=42):
    evaluator = FitnessEvaluator(context, list(scenarios.values()), DEFAULT_WEIGHTS)
    return GeneticAlgorithm(evaluator, GAConfig(population_size=20, generations=8, seed=seed)).run()


def test_ga_improves_and_is_reproducible(context, scenarios):
    result = _run(context, scenarios)
    best = [h["best_fitness"] for h in result.history]
    assert len(best) == 8
    assert all(b2 >= b1 for b1, b2 in zip(best, best[1:]))  # elitism: best never gets worse
    assert result.best_fitness.feasible and result.best_fitness.fitness == best[-1]
    assert check_constraints(context, result.best).feasible
    assert len(result.ranked) == 5 and result.ranked[0][1].fitness == result.best_fitness.fitness
    assert _run(context, scenarios).best.key == result.best.key


def test_orchestrator_end_to_end(sample_input):
    from agents.orchestrator import Orchestrator
    from services.gemini_service import GeminiService
    from config import GeminiSettings

    result = Orchestrator(gemini=GeminiService(GeminiSettings("", "x"))).run(
        sample_input, ga_config=GAConfig(population_size=12, generations=3))
    for key in ("farm_profile", "validation_results", "scenarios", "best_strategy", "ranked_strategies",
                "best_fitness", "fitness_history", "simulation_metrics", "scenario_results", "research_report",
                "assumptions"):
        assert key in result
    assert result["research_report"]["source"] == "deterministic"
    assert len(result["scenario_results"]["best"]) == 5
