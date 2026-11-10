"""Unit tests for each simulation module, plus the sample strategy under all five scenarios."""
from __future__ import annotations

import pytest

from config import MIN_WATER_FACTOR, SIMULATOR_DISCLAIMER
from core.chromosome import Chromosome, Gene
from simulation import soil_simulator as soil
from simulation import water_simulator as water
from simulation.crop_simulator import simulate_crop
from simulation.economic_simulator import cost_breakdown, revenue
from simulation.farm_simulator import sample_context, simulate_farm
from simulation.scenario_engine import (make_custom_scenario, profit_retention, run_scenarios,
                                        scenario_table)
from simulation.weather_simulator import Scenario, seasonal_rainfall_mm, valid_windows, weather_factor

BUILT_IN = ["normal", "drought", "excess_rainfall", "input_price_shock", "market_price_drop"]
CROP = {"seed_cost_usd_per_ha": 50, "labor_cost_usd_per_ha": 200, "fertilizer_cost_usd_per_kg": 1.0,
        "irrigation_cost_usd_per_m3": 0.1}


def sample_strategy(context) -> Chromosome:
    """First feasible crop per slot, 80% water and fertilizer, earliest valid window."""
    genes = []
    for plot, season in context.slots:
        crop = context.options[season][(plot - 1) % len(context.options[season])]
        genes.append(Gene(plot, season, crop, 0.8, 0.8, context.windows_for(crop, season)[0]))
    return Chromosome(genes)


# --- water ---------------------------------------------------------------------------------
def test_water_balance():
    assert water.effective_rainfall_mm(200, 0.5) == 100
    assert water.effective_rainfall_mm(-50, 0.5) == 0
    assert water.irrigation_need_mm(500, 100) == 400 and water.irrigation_need_mm(100, 500) == 0
    assert water.irrigation_applied_mm(400, 0.5, 0.5) == 100
    assert water.supply_scale(1000, 500) == 0.5 and water.supply_scale(0, 0) == 1.0


def test_water_factor_shape():
    full, adequacy, logged = water.water_factor(100, 100, 0.5, 0.5, 0.5)
    assert (full, adequacy, logged) == (1.0, 1.0, False)
    dry_sensitive, *_ = water.water_factor(50, 100, 0.0, 0.5, 0.5)
    dry_tolerant, *_ = water.water_factor(50, 100, 1.0, 0.5, 0.5)
    assert dry_sensitive == pytest.approx(0.5) and dry_tolerant == pytest.approx(0.75)
    assert water.water_factor(0, 100, 0.0, 0.5, 0.5)[0] == MIN_WATER_FACTOR
    tolerant_flood, *_ = water.water_factor(300, 100, 0.5, 1.0, 0.0)
    assert tolerant_flood == 1.0


# --- soil ----------------------------------------------------------------------------------
def test_soil_factors():
    assert soil.ph_factor(6.5, 6.0, 7.0) == 1.0
    assert soil.ph_factor(5.7, 6.0, 7.0) == pytest.approx(0.85)
    assert soil.ph_factor(4.0, 6.0, 7.0) == 0.0
    assert soil.soil_factor(1.0, 100, 1.0) == pytest.approx(1.0)
    assert soil.soil_factor(1.0, 0, 1.0) == pytest.approx(0.6)
    assert soil.fertilizer_applied_kg_per_ha(100, 0.8) == pytest.approx(100)
    assert soil.nutrient_factor(0) == pytest.approx(0.55) and soil.nutrient_factor(2) == 1.0


def test_soil_health_impact_uses_dataset_effect():
    assert soil.soil_health_delta(2.0, 1.0, False) == pytest.approx(2.0)
    assert soil.soil_health_delta(2.0, 1.0, True) < 2.0
    assert soil.soil_health_delta(0.0, 0.0, False) == pytest.approx(-2.0)
    assert soil.soil_health_delta(0.0, 1.5, False) == pytest.approx(-2.0)
    assert soil.update_soil_health(99, 5) == 100 and soil.update_soil_health(1, -5) == 0


# --- weather -------------------------------------------------------------------------------
def test_weather_and_windows():
    drought = Scenario("d", "Drought", rainfall_multiplier=0.5, yield_stress_factor=0.9)
    assert seasonal_rainfall_mm(400, drought) == 200
    assert weather_factor(drought, 1) == pytest.approx(0.9)
    assert valid_windows(200, "summer") == []
    with pytest.raises(ValueError, match="rainfall_multiplier"):
        Scenario("x", "Bad", rainfall_multiplier=10)


# --- economics -----------------------------------------------------------------------------
def test_costs_and_revenue():
    costs = cost_breakdown(CROP, 2.0, 100, 1000, 1.5)
    assert costs["seed_cost"] == 150 and costs["labor_cost"] == 600
    assert costs["fertilizer_cost"] == 150 and costs["irrigation_cost"] == pytest.approx(150)
    assert costs["total_cost"] == pytest.approx(1050)
    assert revenue(4, 300, 0.8) == pytest.approx(960)


@pytest.mark.parametrize("call", [
    lambda: cost_breakdown(CROP, -1, 0, 0),
    lambda: cost_breakdown(CROP, 1, -5, 0),
    lambda: cost_breakdown(CROP, 1, 0, 0, 0),
    lambda: revenue(-1, 300),
    lambda: revenue(1, float("nan")),
])
def test_economics_reject_invalid_inputs(call):
    with pytest.raises(ValueError):
        call()


# --- crop ----------------------------------------------------------------------------------
def test_crop_yield_formula(context, scenarios):
    crop_id = context.options["monsoon"][0]
    crop = context.crop(crop_id)
    gene = Gene(1, "monsoon", crop_id, 0.8, 0.8, context.windows_for(crop_id, "monsoon")[0])
    r = simulate_crop(crop, gene, 1.0, context.soil, 6.5, 1100, scenarios["normal"], 65, False)
    expected = crop["base_yield_t_per_ha"] * r["water_factor"] * r["soil_factor"] * r["weather_factor"] \
        * r["nutrient_factor"]
    assert r["yield_t"] == pytest.approx(expected)
    assert r["profit"] == pytest.approx(r["revenue"] - r["total_cost"])
    assert r["soil_health_delta"] == pytest.approx(crop["soil_health_effect"])
    with pytest.raises(ValueError, match="area_ha"):
        simulate_crop(crop, gene, 0, context.soil, 6.5, 1100, scenarios["normal"], 65, False)
    with pytest.raises(ValueError, match="soil_health"):
        simulate_crop(crop, gene, 1, context.soil, 6.5, 1100, scenarios["normal"], 140, False)


# --- farm ----------------------------------------------------------------------------------
def test_farm_rejects_incomplete_or_invalid_strategies(context, scenarios):
    plan = sample_strategy(context)
    with pytest.raises(ValueError, match="no gene"):
        simulate_farm(context, Chromosome(plan.genes[1:]), scenarios["normal"])
    with pytest.raises(ValueError, match="two genes"):
        simulate_farm(context, Chromosome([*plan.genes, plan.genes[0]]), scenarios["normal"])
    with pytest.raises(ValueError, match="Unknown crop_id"):
        simulate_farm(context, Chromosome([plan.genes[0].with_changes(crop_id="BANANA"), *plan.genes[1:]]),
                      scenarios["normal"])


def test_irrigation_is_limited_by_available_water(context, scenarios):
    plan = sample_strategy(context)
    plan = Chromosome([g.with_changes(water_level=1.0) for g in plan.genes])
    t = simulate_farm(context, plan, scenarios["drought"]).totals
    assert t["water_use_m3"] <= t["water_available_m3"] + 1e-6


def test_sample_context_loads_through_data_loader():
    context = sample_context()
    assert context.profile.farm_name == "Green Valley Farm" and len(context.slots) == 12


# --- scenarios: the sample strategy under all five ----------------------------------------
def test_sample_strategy_under_all_five_scenarios(scenarios):
    context = sample_context()
    results = run_scenarios(context, sample_strategy(context), [scenarios[s] for s in BUILT_IN])
    table = scenario_table(results, scenarios).set_index("scenario_id")
    assert list(table.index) == BUILT_IN
    for result in results.values():
        t = result.totals
        assert t["net_profit"] == pytest.approx(t["revenue"] - t["total_cost"])
        assert t["total_yield_t"] > 0 and 0 <= t["final_soil_health"] <= 100
        assert result.note == SIMULATOR_DISCLAIMER and len(result.gene_results) == 12
    normal = table.loc["normal"]
    assert table.loc["drought", "total_yield_t"] < normal["total_yield_t"]
    assert table.loc["excess_rainfall", "waterlogged_plots"] >= normal["waterlogged_plots"]
    assert table.loc["input_price_shock", "total_cost"] > normal["total_cost"]
    assert table.loc["market_price_drop", "revenue"] < normal["revenue"]
    assert set(profit_retention(results)) == set(BUILT_IN[1:])


def test_custom_scenario_defaults_are_neutral(context, scenarios):
    neutral = make_custom_scenario("Same as normal", {})
    plan = sample_strategy(context)
    assert simulate_farm(context, plan, neutral).totals["net_profit"] == pytest.approx(
        simulate_farm(context, plan, scenarios["normal"]).totals["net_profit"])
