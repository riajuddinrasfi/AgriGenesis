"""Whole-farm simulation of a planting strategy.

A strategy is an integer matrix ``genes[plot, season]`` holding a crop index
into ``FarmContext.crops`` or ``FALLOW``. Simulations are vectorised over a
batch of scenarios so a strategy is scored against every scenario at once.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from simulation.crop_simulator import crop_yield, pest_factor, ph_factor, temperature_factor
from simulation.economic_simulator import production_cost, revenue
from simulation.scenario_engine import sample_scenarios, scenario_params
from simulation.soil_simulator import nitrogen_factor, update_nitrogen
from simulation.water_simulator import (
    allocate_irrigation, available_soil_water, flood_factor, water_stress_factor,
)
from simulation.weather_simulator import base_conditions, season_weather
from utils.random_generator import make_rng, mean_one_lognormal

FALLOW = -1
CROP_ARRAYS = (
    "water_mm", "yield_t_ha", "price_per_t", "cost_per_ha", "labor_days_ha", "ph_min", "ph_max",
    "temp_min", "temp_max", "nitrogen_effect", "drought_tolerance", "flood_tolerance",
    "pest_sensitivity",
)


@dataclass
class FarmContext:
    farm: dict
    crops: pd.DataFrame
    seasons: list[dict]
    scenarios: pd.DataFrame
    rotation: np.ndarray
    allowed: list[list[int]]
    config: dict = field(default_factory=dict)

    def __post_init__(self):
        self.crops = self.crops.reset_index(drop=True)
        self.arrays = {col: self.crops[col].to_numpy(dtype=float) for col in CROP_ARRAYS}
        self.arrays["ph_factor"] = ph_factor(
            float(self.farm["soil_ph"]), self.arrays["ph_min"], self.arrays["ph_max"])

    @property
    def n_plots(self) -> int:
        return int(self.farm["num_plots"])

    @property
    def n_seasons(self) -> int:
        return len(self.seasons)

    @property
    def n_crops(self) -> int:
        return len(self.crops)

    @property
    def plot_area(self) -> float:
        return float(self.farm["plot_area_ha"])

    @property
    def fallow_index(self) -> int:
        """Row/column of ``rotation`` that represents a fallow season."""
        return self.n_crops

    @property
    def irrigation_cost(self) -> float:
        return float(self.config.get("economics", {}).get("irrigation_cost_per_m3", 0.05))

    def crop_name(self, idx: int) -> str:
        return "Fallow" if idx == FALLOW else str(self.crops.at[int(idx), "crop"])

    def crop_index(self, name: str) -> int:
        if name == "Fallow":
            return FALLOW
        matches = np.flatnonzero(self.crops["crop"].to_numpy() == name)
        if not len(matches):
            raise KeyError(f"Unknown crop: {name}")
        return int(matches[0])

    def season_conditions(self, season: int) -> tuple[float, float]:
        return base_conditions(self.farm, self.seasons[season]["type"])


@dataclass
class SimulationResult:
    """Per-scenario, per-season totals; arrays are ``(n_scenarios, n_seasons)``."""

    revenue: np.ndarray
    cost: np.ndarray
    water_m3: np.ndarray
    labor_days: np.ndarray
    final_nitrogen: np.ndarray
    details: pd.DataFrame | None = None

    @property
    def profit(self) -> np.ndarray:
        return self.revenue - self.cost

    @property
    def total_profit(self) -> np.ndarray:
        return self.profit.sum(axis=1)


def simulate(context: FarmContext, genes, scenarios=None, noise=None, detailed=False) -> SimulationResult:
    """Simulate ``genes`` under each scenario (neutral conditions if ``scenarios`` is None).

    ``noise`` multiplies yields and must broadcast to ``(n_scenarios, n_plots, n_seasons)``.
    ``detailed`` adds a per-plot table for the first scenario.
    """
    genes = np.asarray(genes, dtype=int)
    p = scenario_params(scenarios)
    n_scen = len(p["rainfall_factor"])
    n_plots, n_seasons = genes.shape
    area, a, farm = context.plot_area, context.arrays, context.farm
    stored = available_soil_water(farm.get("water_holding_mm", 0))
    nitrogen = np.full((n_scen, n_plots), float(farm["soil_nitrogen"]))
    prev = np.full(n_plots, context.fallow_index)
    revenue_s, cost_s, water_s, labor_s = (np.zeros((n_scen, n_seasons)) for _ in range(4))
    rows = []

    for s in range(n_seasons):
        g = genes[:, s]
        planted = g != FALLOW
        idx = np.where(planted, g, 0)
        mask = planted[None, :].astype(float)
        temp, rain = season_weather(farm, context.seasons[s]["type"], p)

        need = a["water_mm"][idx][None, :]
        _, satisfaction, irrigation = allocate_irrigation(
            need, rain + stored, mask, area, float(farm["irrigation_m3"]))
        nxt = np.where(planted, g, context.fallow_index)
        yield_t = crop_yield(
            a["yield_t_ha"][idx], area, a["ph_factor"][idx], context.rotation[prev, nxt],
            water_stress_factor(satisfaction, a["drought_tolerance"][idx]),
            flood_factor(p["rainfall_factor"], a["flood_tolerance"][idx]),
            temperature_factor(temp, a["temp_min"][idx], a["temp_max"][idx]),
            pest_factor(p["pest_pressure"], a["pest_sensitivity"][idx]),
            nitrogen_factor(nitrogen), p["yield_shock"], mask,
        )
        if noise is not None:
            yield_t = yield_t * np.broadcast_to(noise, (n_scen, n_plots, n_seasons))[:, :, s]
        rev = revenue(yield_t, a["price_per_t"][idx], p["price_factor"])
        cst = production_cost(a["cost_per_ha"][idx], area, p["cost_factor"], irrigation,
                              context.irrigation_cost, mask)
        lab = a["labor_days_ha"][idx] * area * planted

        revenue_s[:, s], cost_s[:, s] = rev.sum(axis=1), cst.sum(axis=1)
        water_s[:, s], labor_s[:, s] = irrigation.sum(axis=1), lab.sum()
        if detailed:
            rows += [{
                "plot": f"Plot {i + 1}", "season": context.seasons[s]["name"],
                "crop": context.crop_name(g[i]), "yield_t": yield_t[0, i], "revenue": rev[0, i],
                "cost": cst[0, i], "profit": rev[0, i] - cst[0, i], "irrigation_m3": irrigation[0, i],
                "labor_days": lab[i], "soil_nitrogen_before": nitrogen[0, i],
            } for i in range(n_plots)]

        nitrogen = update_nitrogen(nitrogen, planted[None, :], a["nitrogen_effect"][idx][None, :],
                                   farm.get("organic_matter_pct", 0))
        prev = nxt

    return SimulationResult(revenue_s, cost_s, water_s, labor_s, nitrogen.mean(axis=1),
                            pd.DataFrame(rows) if detailed else None)


def scenario_breakdown(context: FarmContext, genes) -> pd.DataFrame:
    result = simulate(context, genes, context.scenarios)
    return pd.DataFrame({
        "scenario": context.scenarios["scenario"].to_numpy(),
        "probability": context.scenarios["probability"].to_numpy(),
        "revenue": result.revenue.sum(axis=1),
        "cost": result.cost.sum(axis=1),
        "profit": result.total_profit,
        "irrigation_m3": result.water_m3.sum(axis=1),
    })


def resource_usage(context: FarmContext, genes) -> pd.DataFrame:
    """Budget, labour and irrigation use per season under neutral conditions."""
    result = simulate(context, genes)
    farm = context.farm
    return pd.DataFrame({
        "season": [s["name"] for s in context.seasons],
        "cost": result.cost[0], "budget": float(farm["budget"]),
        "labor_days": result.labor_days[0], "labor_capacity": float(farm["labor_days"]),
        "irrigation_m3": result.water_m3[0], "irrigation_capacity": float(farm["irrigation_m3"]),
    })


def monte_carlo(context: FarmContext, genes, n_runs: int = 500, seed: int | None = 0,
                noise_sd: float | None = None) -> pd.DataFrame:
    """Sample scenarios by probability and add mean-one log-normal yield noise."""
    rng = make_rng(seed)
    if noise_sd is None:
        noise_sd = float(context.config.get("simulation", {}).get("yield_noise_sd", 0.08))
    sampled = sample_scenarios(context.scenarios, n_runs, rng)
    genes = np.asarray(genes)
    noise = mean_one_lognormal(rng, noise_sd, (n_runs, *genes.shape))
    result = simulate(context, genes, sampled, noise=noise)
    return pd.DataFrame({"scenario": sampled["scenario"], "profit": result.total_profit})
