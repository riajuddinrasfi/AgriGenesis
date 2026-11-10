"""Turns GA output into serialisable strategy records and saves them to outputs/."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import PLANTING_WINDOWS, STRATEGY_DIR
from core.chromosome import Chromosome
from core.fitness import FitnessResult
from simulation.farm_simulator import FarmContext
from utils.helpers import timestamp, write_json

WINDOW_NAMES = {w["id"]: w["name"] for w in PLANTING_WINDOWS}


def plan_records(context: FarmContext, chromosome: Chromosome) -> list[dict]:
    """Readable gene table: one row per plot-season."""
    return [{
        "plot": g.plot_id, "season": g.season, "crop_id": g.crop_id, "crop": context.crop_name(g.crop_id),
        "water_level": g.water_level, "fertilizer_level": g.fertilizer_level,
        "planting_window": WINDOW_NAMES[g.planting_window] if not g.is_fallow else "-",
    } for g in chromosome.genes]


def allocation_summary(context: FarmContext, chromosome: Chromosome) -> dict[str, dict[str, int]]:
    """Season -> crop name -> number of plots."""
    summary: dict[str, dict[str, int]] = {}
    for g in chromosome.genes:
        season = summary.setdefault(g.season, {})
        name = context.crop_name(g.crop_id)
        season[name] = season.get(name, 0) + 1
    return summary


def strategy_record(context: FarmContext, rank: int, chromosome: Chromosome, fitness: FitnessResult) -> dict:
    return {
        "rank": rank,
        "fitness": fitness.fitness,
        "feasible": fitness.feasible,
        "components": fitness.components,
        "contributions": fitness.contributions,
        "metrics": fitness.metrics,
        "scenario_profits": fitness.scenario_profits,
        "violations": fitness.violations,
        "genes": chromosome.to_records(),
        "plan": plan_records(context, chromosome),
        "allocation": allocation_summary(context, chromosome),
    }


def ranked_records(context: FarmContext, ranked: list[tuple[Chromosome, FitnessResult]]) -> list[dict]:
    return [strategy_record(context, i + 1, c, f) for i, (c, f) in enumerate(ranked)]


def comparison_frame(strategies: list[dict]) -> pd.DataFrame:
    rows = []
    for s in strategies:
        m = s["metrics"]
        rows.append({
            "strategy": f"#{s['rank']}", "fitness": s["fitness"], "net_profit": m["net_profit"],
            "total_yield_t": m["total_yield_t"], "water_use_m3": m["water_use_m3"],
            "final_soil_health": m["final_soil_health"], "resilience": s["components"]["resilience"],
            "feasible": s["feasible"],
        })
    return pd.DataFrame(rows)


def save_result(result: dict, directory: Path = STRATEGY_DIR) -> Path:
    """Write the full orchestrator result as JSON and return the path."""
    return write_json(directory / f"agrigenesis_result_{timestamp()}.json", result)
