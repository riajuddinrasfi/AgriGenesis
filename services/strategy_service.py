"""Baseline strategies, benchmarks, GA parameter studies and saved strategies."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from config import STRATEGY_DIR
from core.chromosome import Chromosome
from core.fitness import evaluate
from core.genetic_algorithm import GAParams, GAResult, GeneticAlgorithm
from simulation.farm_simulator import FALLOW, FarmContext
from utils.helpers import save_json, slugify, timestamp


def random_genes(context: FarmContext, rng: np.random.Generator) -> np.ndarray:
    return Chromosome.random(context, rng).genes


def expected_margin_per_ha(context: FarmContext, season: int) -> pd.Series:
    """Gross margin per hectare of each allowed crop under normal conditions."""
    a = context.arrays
    temp, rain = context.season_conditions(season)
    margins = {}
    for crop in context.allowed[season]:
        if crop == FALLOW:
            continue
        deficit = max(0.0, a["water_mm"][crop] - rain)
        temp_gap = max(0.0, a["temp_min"][crop] - temp) + max(0.0, temp - a["temp_max"][crop])
        yield_factor = a["ph_factor"][crop] * max(0.3, 1 - 0.08 * temp_gap)
        revenue = a["yield_t_ha"][crop] * yield_factor * a["price_per_t"][crop]
        cost = a["cost_per_ha"][crop] + deficit * 10.0 * context.irrigation_cost
        margins[crop] = revenue - cost
    return pd.Series(margins, dtype=float).sort_values(ascending=False)


def greedy_genes(context: FarmContext) -> np.ndarray:
    """Fill plots with the highest-margin crop that fits remaining budget, labour and water,
    avoiding the same crop family twice in a row on a plot."""
    a = context.arrays
    area = context.plot_area
    families = context.crops["family"].to_numpy()
    genes = np.full((context.n_plots, context.n_seasons), FALLOW, dtype=int)
    for s in range(context.n_seasons):
        _, rain = context.season_conditions(s)
        ranking = expected_margin_per_ha(context, s)
        budget = float(context.farm["budget"])
        labor = float(context.farm["labor_days"])
        water = float(context.farm["irrigation_m3"])
        for plot in range(context.n_plots):
            prev = genes[plot, s - 1] if s > 0 else FALLOW
            for crop, margin in ranking.items():
                if margin <= 0:
                    break
                if prev != FALLOW and families[crop] == families[prev]:
                    continue
                water_need = max(0.0, a["water_mm"][crop] - rain) * area * 10.0
                cost = a["cost_per_ha"][crop] * area + water_need * context.irrigation_cost
                lab = a["labor_days_ha"][crop] * area
                if cost <= budget and lab <= labor and water_need <= water:
                    genes[plot, s] = crop
                    budget -= cost
                    labor -= lab
                    water -= water_need
                    break
    return genes


def monoculture_genes(context: FarmContext) -> np.ndarray:
    """Every plot gets the single highest-margin crop of each season."""
    genes = np.full((context.n_plots, context.n_seasons), FALLOW, dtype=int)
    for s in range(context.n_seasons):
        ranking = expected_margin_per_ha(context, s)
        if len(ranking) and ranking.iloc[0] > 0:
            genes[:, s] = int(ranking.index[0])
    return genes


def traditional_genes(context: FarmContext) -> np.ndarray:
    """The configured traditional rotation (e.g. rice in wet, wheat in dry season)."""
    rotation = context.config.get("rotation", {}).get("traditional", {})
    genes = np.full((context.n_plots, context.n_seasons), FALLOW, dtype=int)
    for s, season in enumerate(context.seasons):
        name = rotation.get(season["type"])
        try:
            crop = context.crop_index(name) if name else FALLOW
        except KeyError:
            crop = FALLOW
        if crop not in context.allowed[s]:
            ranking = expected_margin_per_ha(context, s)
            crop = int(ranking.index[0]) if len(ranking) else FALLOW
        genes[:, s] = crop
    return genes


def baseline_strategies(context: FarmContext) -> dict[str, np.ndarray]:
    return {
        "Traditional rotation": traditional_genes(context),
        "Max-margin monoculture": monoculture_genes(context),
        "Greedy heuristic": greedy_genes(context),
    }


def genes_to_frame(context: FarmContext, genes: np.ndarray) -> pd.DataFrame:
    return Chromosome(genes).to_frame(context)


def compare_with_baselines(context: FarmContext, ga_result: GAResult, n_random: int = 50) -> pd.DataFrame:
    rows = [{"strategy": "Genetic algorithm", **ga_result.best.as_dict()}]
    for name, genes in baseline_strategies(context).items():
        rows.append({"strategy": name, **evaluate(context, genes).as_dict()})
    rng = np.random.default_rng(0)
    randoms = pd.DataFrame([evaluate(context, random_genes(context, rng)).as_dict() for _ in range(n_random)])
    rows.append({"strategy": f"Random (mean of {n_random})", **randoms.mean().to_dict(),
                 "feasible": bool(randoms["feasible"].mean() >= 0.5)})
    return pd.DataFrame(rows)


def seed_study(context: FarmContext, params: GAParams, seeds: list[int]) -> pd.DataFrame:
    rows = []
    baselines = list(baseline_strategies(context).values())
    for seed in seeds:
        result = GeneticAlgorithm(context, replace(params, seed=seed), seed_strategies=baselines).run()
        rows.append({"seed": seed, "generations_run": result.generations_run,
                     "evaluations": result.evaluations, **result.best.as_dict()})
    return pd.DataFrame(rows)


def parameter_sweep(
    context: FarmContext, params: GAParams, name: str, values: list, seeds: list[int] = (0, 1, 2)
) -> pd.DataFrame:
    """Best fitness for each value of one GA parameter, averaged over ``seeds``."""
    rows = []
    for value in values:
        study = seed_study(context, replace(params, **{name: value}), list(seeds))
        rows.append({
            "parameter": name,
            "value": value,
            "mean_fitness": study["fitness"].mean(),
            "std_fitness": study["fitness"].std(ddof=0),
            "mean_expected_profit": study["expected_profit"].mean(),
            "mean_evaluations": study["evaluations"].mean(),
        })
    return pd.DataFrame(rows)


def strategy_record(context: FarmContext, genes: np.ndarray, fitness: dict, label: str = "") -> dict:
    return {
        "label": label,
        "farm_id": context.farm["farm_id"],
        "farm": context.farm["name"],
        "seasons": [s["name"] for s in context.seasons],
        "plan": Chromosome(genes).to_frame(context).to_dict(orient="index"),
        "fitness": fitness,
        "scenarios": context.scenarios["scenario"].tolist(),
    }


def save_strategy(record: dict, directory: str | Path = STRATEGY_DIR) -> Path:
    name = f"{slugify(record['farm_id'])}-{slugify(record.get('label') or 'strategy')}-{timestamp()}.json"
    return save_json(record, Path(directory) / name)
