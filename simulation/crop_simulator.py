"""Yield model for one crop on one plot in one season.

yield_t = area_ha * base_yield * water_factor * soil_factor * weather_factor * nutrient_factor
"""
from __future__ import annotations

from core.chromosome import Gene
from simulation import soil_simulator as soil_sim
from simulation import water_simulator as water_sim
from simulation.economic_simulator import cost_breakdown, revenue
from simulation.weather_simulator import Scenario, seasonal_rainfall_mm, weather_factor
from utils.calculations import mm_to_m3


def irrigation_need_mm(crop: dict, soil: dict, base_rainfall_mm: float, scenario: Scenario) -> float:
    """Irrigation (mm) needed to meet the crop requirement after effective rainfall."""
    rain = seasonal_rainfall_mm(base_rainfall_mm, scenario)
    effective = water_sim.effective_rainfall_mm(rain, soil["effective_rainfall_fraction"])
    return water_sim.irrigation_need_mm(crop["water_requirement_mm"], effective)


def simulate_crop(crop: dict, gene: Gene, area_ha: float, soil: dict, soil_ph: float,
                  base_rainfall_mm: float, scenario: Scenario, soil_health: float,
                  repeats_family: bool, water_supply_scale: float = 1.0) -> dict:
    """Simulate one planted gene and return every intermediate factor for transparency."""
    rain = seasonal_rainfall_mm(base_rainfall_mm, scenario)
    effective = water_sim.effective_rainfall_mm(rain, soil["effective_rainfall_fraction"])
    need = water_sim.irrigation_need_mm(crop["water_requirement_mm"], effective)
    irrigation_mm = water_sim.irrigation_applied_mm(need, gene.water_level, water_supply_scale)
    w_factor, adequacy, waterlogged = water_sim.water_factor(
        effective + irrigation_mm, crop["water_requirement_mm"], crop["drought_tolerance"],
        crop["waterlogging_tolerance"], soil["drainage_factor"])

    ph_fac = soil_sim.ph_factor(soil_ph, crop["min_ph"], crop["max_ph"])
    s_factor = soil_sim.soil_factor(soil["fertility_factor"], soil_health, ph_fac)
    fert_kg_ha = soil_sim.fertilizer_applied_kg_per_ha(
        crop["fertilizer_requirement_kg_per_ha"], gene.fertilizer_level)
    ratio = soil_sim.fertilizer_ratio(fert_kg_ha, crop["fertilizer_requirement_kg_per_ha"])
    n_factor = soil_sim.nutrient_factor(ratio)
    wx_factor = weather_factor(scenario, gene.planting_window)

    yield_t = area_ha * crop["base_yield_t_per_ha"] * w_factor * s_factor * wx_factor * n_factor
    irrigation_m3 = mm_to_m3(irrigation_mm, area_ha)
    costs = cost_breakdown(crop, area_ha, fert_kg_ha * area_ha, irrigation_m3,
                           scenario.input_cost_multiplier)
    income = revenue(yield_t, crop["selling_price_usd_per_t"], scenario.market_price_multiplier)
    delta = soil_sim.soil_health_delta(crop["soil_health_effect"], ratio, repeats_family)
    return {
        "rainfall_mm": rain,
        "effective_rainfall_mm": effective,
        "irrigation_mm": irrigation_mm,
        "water_use_m3": irrigation_m3,
        "water_adequacy": adequacy,
        "waterlogged": waterlogged,
        "water_factor": w_factor,
        "soil_factor": s_factor,
        "weather_factor": wx_factor,
        "nutrient_factor": n_factor,
        "fertilizer_kg": fert_kg_ha * area_ha,
        "yield_t": yield_t,
        "potential_yield_t": area_ha * crop["base_yield_t_per_ha"],
        "revenue": income,
        **costs,
        "profit": income - costs["total_cost"],
        "soil_health_delta": delta,
    }
