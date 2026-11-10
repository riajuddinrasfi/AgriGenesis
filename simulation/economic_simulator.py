"""Costs and revenue for one plot-season."""
from __future__ import annotations


def cost_breakdown(crop: dict, area_ha: float, fertilizer_kg: float, irrigation_m3: float,
                   input_cost_multiplier: float = 1.0) -> dict[str, float]:
    """Seed, fertilizer, labour and irrigation cost in USD (scenario multiplier applied)."""
    seed = crop["seed_cost_usd_per_ha"] * area_ha
    labor = crop["labor_cost_usd_per_ha"] * area_ha
    fertilizer = crop["fertilizer_cost_usd_per_kg"] * fertilizer_kg
    irrigation = crop["irrigation_cost_usd_per_m3"] * irrigation_m3
    costs = {"seed_cost": seed, "fertilizer_cost": fertilizer, "labor_cost": labor,
             "irrigation_cost": irrigation}
    costs = {k: v * input_cost_multiplier for k, v in costs.items()}
    costs["total_cost"] = sum(costs.values())
    return costs


def revenue(yield_t: float, selling_price_usd_per_t: float, market_price_multiplier: float = 1.0) -> float:
    return yield_t * selling_price_usd_per_t * market_price_multiplier
