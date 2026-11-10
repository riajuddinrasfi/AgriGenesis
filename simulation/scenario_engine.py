"""Runs a strategy through several scenarios and measures how robust it is."""
from __future__ import annotations

import pandas as pd

from core.chromosome import Chromosome
from simulation.farm_simulator import FarmContext, SimulationResult, simulate_farm
from simulation.weather_simulator import SCENARIO_LIMITS, Scenario
from utils.normalization import clip

BASELINE_ID = "normal"


def scenarios_from_frame(frame: pd.DataFrame) -> dict[str, Scenario]:
    return {str(r["scenario_id"]): Scenario.from_row(r) for r in frame.to_dict("records")}


def make_custom_scenario(name: str, params: dict, description: str = "") -> Scenario:
    """Build a validated user-defined scenario; missing parameters stay at 1.0 (neutral)."""
    clean_name = str(name).strip()[:60] or "Custom scenario"
    slug = "custom_" + "".join(ch if ch.isalnum() else "_" for ch in clean_name.lower()).strip("_")
    values = {k: float(params.get(k, 1.0)) for k in SCENARIO_LIMITS}
    return Scenario(scenario_id=slug, scenario_name=clean_name, description=description[:300],
                    custom=True, **values)


def run_scenarios(context: FarmContext, chromosome: Chromosome,
                  scenarios: list[Scenario]) -> dict[str, SimulationResult]:
    return {s.scenario_id: simulate_farm(context, chromosome, s) for s in scenarios}


def profit_retention(results: dict[str, SimulationResult], baseline_id: str = BASELINE_ID) -> dict[str, float]:
    """Adverse-scenario profit as a share of baseline profit, clipped to [0, 1]."""
    baseline = results[baseline_id].totals["net_profit"]
    retention = {}
    for sid, result in results.items():
        if sid == baseline_id:
            continue
        retention[sid] = clip(result.totals["net_profit"] / baseline) if baseline > 0 else 0.0
    return retention


def resilience_score(results: dict[str, SimulationResult], baseline_id: str = BASELINE_ID) -> float:
    """Mean profit retention across adverse scenarios (1.0 if none were simulated)."""
    retention = profit_retention(results, baseline_id)
    if not retention:
        return 1.0
    return sum(retention.values()) / len(retention)


def scenario_table(results: dict[str, SimulationResult], scenarios: dict[str, Scenario]) -> pd.DataFrame:
    rows = []
    for sid, result in results.items():
        t = result.totals
        rows.append({
            "scenario_id": sid,
            "scenario": scenarios[sid].scenario_name if sid in scenarios else sid,
            "net_profit": t["net_profit"], "revenue": t["revenue"], "total_cost": t["total_cost"],
            "total_yield_t": t["total_yield_t"], "water_use_m3": t["water_use_m3"],
            "final_soil_health": t["final_soil_health"], "waterlogged_plots": t["waterlogged_genes"],
            "irrigation_supply_share": t["irrigation_supply_scale"],
        })
    return pd.DataFrame(rows)
