import numpy as np
import pytest

from core.chromosome import Chromosome
from core.crossover import crossover
from core.genetic_algorithm import GAParams, GeneticAlgorithm
from core.mutation import mutate
from core.selection import elite_indices, roulette, tournament
from services.strategy_service import baseline_strategies

FAST = dict(population_size=20, generations=15, patience=None, seed=1)


def test_params_validation():
    for bad in ({"population_size": 1}, {"mutation_rate": 1.5}, {"tournament_size": 99}, {"elitism": 60}):
        with pytest.raises(ValueError):
            GAParams(**bad).validate()
    assert GAParams.from_config({"genetic_algorithm": {"generations": 5, "unknown": 1}}).generations == 5


def test_selection_operators():
    rng = np.random.default_rng(0)
    scores = np.array([1.0, 5.0, 3.0])
    assert tournament(scores, 3, rng) == 1
    assert list(elite_indices(scores, 2)) == [1, 2]
    assert roulette(scores, rng) in (0, 1, 2)


def test_crossover_and_mutation_respect_parents_and_allowed(context):
    rng = np.random.default_rng(0)
    a, b = Chromosome.random(context, rng).genes, Chromosome.random(context, rng).genes
    c, d = crossover(a, b, 1.0, rng)
    assert ((c == a) | (c == b)).all() and ((d == a) | (d == b)).all()
    m = mutate(a, context.allowed, 1.0, rng)
    for s, options in enumerate(context.allowed):
        assert set(m[:, s]) <= set(options)


def test_chromosome_frame_round_trip(context):
    genes = Chromosome.random(context, np.random.default_rng(3))
    assert (Chromosome.from_frame(context, genes.to_frame(context)).genes == genes.genes).all()


def test_ga_is_reproducible(context):
    a = GeneticAlgorithm(context, GAParams(**FAST)).run()
    b = GeneticAlgorithm(context, GAParams(**FAST)).run()
    assert (a.best_genes == b.best_genes).all() and a.best.fitness == b.best.fitness


def test_ga_best_is_monotonic_and_valid(context):
    result = GeneticAlgorithm(context, GAParams(**FAST)).run()
    best = result.history["best_fitness"].to_numpy()
    assert (np.diff(best) >= -1e-9).all() and len(best) == result.generations_run
    for s, options in enumerate(context.allowed):
        assert set(result.best_genes[:, s]) <= set(options)


def test_ga_beats_or_matches_seeded_baselines(context):
    seeds = list(baseline_strategies(context).values())
    result = GeneticAlgorithm(context, GAParams(**FAST), seed_strategies=seeds).run()
    from core.fitness import evaluate
    assert result.best.fitness >= max(evaluate(context, g).fitness for g in seeds) - 1e-6


def test_early_stopping(context):
    result = GeneticAlgorithm(context, GAParams(population_size=10, generations=200, patience=3, seed=0)).run()
    assert result.generations_run < 200


def test_orchestrator_plan(orchestrator):
    report = orchestrator.plan("F002", GAParams(**FAST))
    assert report.plan.shape == (report.context.n_plots, report.context.n_seasons)
    assert report.comparison["strategy"].iloc[0] == "Genetic algorithm"
    assert report.insights and report.narrative is None and report.narrative_source == "rule-based"
    assert len(report.monte_carlo) > 0 and "p5" in report.risk
