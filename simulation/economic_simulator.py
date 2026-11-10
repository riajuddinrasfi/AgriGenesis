"""Costs and revenue for one plot-season."""
from __future__ import annotations

from utils.calculations import require_range


def cost_breakdown(crop: dict, area_ha: float, fertilizer_kg: float, irrigation_m3: float,
                   input_cost_multiplier: float = 1.0) -> dict[str, float]:
    """Seed, fertilizer, labour and irrigation cost in USD (scenario multiplier applied).

    cost = (seed_usd_per_ha * area + labor_usd_per_ha * area + fert_usd_per_kg * fert_kg
            + irrigation_usd_per_m3 * irrigation_m3) * input_cost_multiplier
    """
    require_range("area_ha", area_ha)
    require_range("fertilizer_kg", fertilizer_kg)
    require_range("irrigation_m3", irrigation_m3)
    require_range("input_cost_multiplier", input_cost_multiplier, exclusive_low=True)
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
    """revenue = yield_t * price_usd_per_t * market_price_multiplier."""
    require_range("yield_t", yield_t)
    require_range("selling_price_usd_per_t", selling_price_usd_per_t)
    require_range("market_price_multiplier", market_price_multiplier)
    return yield_t * selling_price_usd_per_t * market_price_multiplier
