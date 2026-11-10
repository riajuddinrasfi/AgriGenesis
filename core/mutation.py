"""Mutation operator: changes crop, water, fertilizer or planting window of a gene."""
from __future__ import annotations

import numpy as np

from config import FALLOW
from core.chromosome import Chromosome, Gene, fallow_gene
from simulation.farm_simulator import FarmContext
from utils.normalization import clip
from utils.random_generator import choice

ATTRIBUTES = ("crop", "water", "fertilizer", "window")
STEP_SD = 0.2


def mutate_gene(context: FarmContext, gene: Gene, rng: np.random.Generator) -> Gene:
    attribute = "crop" if gene.is_fallow else choice(rng, list(ATTRIBUTES))
    if attribute == "crop":
        options = [c for c in context.options.get(gene.season, []) if c != gene.crop_id]
        if not gene.is_fallow:
            options.append(FALLOW)
        new_crop = choice(rng, options) if options else gene.crop_id
        if new_crop == FALLOW:
            return fallow_gene(gene.plot_id, gene.season)
        windows = context.windows_for(new_crop, gene.season)
        window = gene.planting_window if gene.planting_window in windows else choice(rng, windows)
        water = gene.water_level if not gene.is_fallow else 0.7
        fert = gene.fertilizer_level if not gene.is_fallow else 0.7
        return Gene(gene.plot_id, gene.season, new_crop, water, fert, window)
    if attribute == "water":
        return gene.with_changes(water_level=round(clip(gene.water_level + rng.normal(0, STEP_SD)), 2))
    if attribute == "fertilizer":
        return gene.with_changes(fertilizer_level=round(clip(gene.fertilizer_level + rng.normal(0, STEP_SD)), 2))
    windows = [w for w in context.windows_for(gene.crop_id, gene.season) if w != gene.planting_window]
    return gene.with_changes(planting_window=choice(rng, windows)) if windows else gene


def mutate(context: FarmContext, chromosome: Chromosome, probability: float,
           rng: np.random.Generator) -> Chromosome:
    """Mutate each gene independently with ``probability``."""
    return Chromosome([mutate_gene(context, g, rng) if rng.random() < probability else g
                       for g in chromosome.genes])
