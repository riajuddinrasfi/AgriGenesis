"""Normalised weighted fitness."""
from __future__ import annotations

import pytest

from config import DEFAULT_WEIGHTS
from core.chromosome import Chromosome, fallow_gene
from core.constraints import repair
from core.fitness import FitnessEvaluator
from core.population import random_chromosome


def test_default_weights_match_spec():
    assert DEFAULT_WEIGHTS == {"profit": 0.35, "yield": 0.20, "water": 0.15, "soil": 0.15, "resilience": 0.15}


def test_fitness_is_weighted_sum_of_normalised_components(context, scenarios, rng):
    evaluator = FitnessEvaluator(context, list(scenarios.values()), DEFAULT_WEIGHTS)
    result = evaluator.evaluate(repair(context, random_chromosome(context, rng), rng))
    assert set(result.components) == set(DEFAULT_WEIGHTS)
    assert all(0.0 <= v <= 1.0 for v in result.components.values())
    expected = sum(DEFAULT_WEIGHTS[k] * result.components[k] for k in DEFAULT_WEIGHTS)
    assert result.fitness == pytest.approx(expected)
    assert 0.0 <= result.fitness <= 1.0 and result.feasible


def test_weights_change_the_score(context, scenarios, rng):
    chrom = repair(context, random_chromosome(context, rng), rng)
    profit_only = FitnessEvaluator(context, list(scenarios.values()),
                                   {"profit": 1, "yield": 0, "water": 0, "soil": 0, "resilience": 0})
    soil_only = FitnessEvaluator(context, list(scenarios.values()),
                                 {"profit": 0, "yield": 0, "water": 0, "soil": 1, "resilience": 0})
    a, b = profit_only.evaluate(chrom), soil_only.evaluate(chrom)
    assert a.fitness == pytest.approx(a.components["profit"])
    assert b.fitness == pytest.approx(b.components["soil"])


def test_planted_plan_beats_all_fallow(context, scenarios, rng):
    evaluator = FitnessEvaluator(context, list(scenarios.values()), DEFAULT_WEIGHTS)
    fallow = evaluator.evaluate(Chromosome([fallow_gene(p, s) for p, s in context.slots]))
    planted = max(evaluator.evaluate(repair(context, random_chromosome(context, rng), rng)).fitness for _ in range(10))
    assert planted > fallow.fitness


def test_evaluation_cache(context, scenarios, rng):
    evaluator = FitnessEvaluator(context, list(scenarios.values()), DEFAULT_WEIGHTS)
    chrom = repair(context, random_chromosome(context, rng), rng)
    first = evaluator.evaluate(chrom)
    assert evaluator.evaluate(chrom.copy()) is first and evaluator.evaluations == 1
