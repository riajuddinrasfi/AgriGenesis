"""Random gene/chromosome generation and initial population."""
from __future__ import annotations

from typing import Callable

import numpy as np

from config import FALLOW
from core.chromosome import Chromosome, Gene, fallow_gene
from simulation.farm_simulator import FarmContext
from utils.random_generator import choice, random_level

FALLOW_PROBABILITY = 0.10


def random_gene(context: FarmContext, plot_id: int, season: str, rng: np.random.Generator,
                fallow_probability: float = FALLOW_PROBABILITY) -> Gene:
    options = context.options.get(season, [])
    if not options or rng.random() < fallow_probability:
        return fallow_gene(plot_id, season)
    crop_id = choice(rng, options)
    return Gene(plot_id, season, crop_id, random_level(rng, 0.3, 1.0), random_level(rng, 0.3, 1.0),
                choice(rng, context.windows_for(crop_id, season)))


def random_chromosome(context: FarmContext, rng: np.random.Generator) -> Chromosome:
    return Chromosome([random_gene(context, p, s, rng) for p, s in context.slots])


def initialize_population(context: FarmContext, size: int, rng: np.random.Generator,
                          repair_fn: Callable[[FarmContext, Chromosome, np.random.Generator], Chromosome],
                          max_attempts_factor: int = 5) -> list[Chromosome]:
    """``size`` repaired, distinct random strategies (duplicates allowed only if unavoidable)."""
    population, seen = [], set()
    attempts = 0
    while len(population) < size and attempts < size * max_attempts_factor:
        attempts += 1
        candidate = repair_fn(context, random_chromosome(context, rng), rng)
        if candidate.key in seen:
            continue
        seen.add(candidate.key)
        population.append(candidate)
    while len(population) < size:
        population.append(repair_fn(context, random_chromosome(context, rng), rng))
    return population


def planted_share(chromosome: Chromosome) -> float:
    if not chromosome.genes:
        return 0.0
    return sum(g.crop_id != FALLOW for g in chromosome.genes) / len(chromosome.genes)
