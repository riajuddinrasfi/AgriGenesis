"""Dataset loading and the deterministic simulation engine."""
from __future__ import annotations

import pytest

from config import FALLOW, SYNTHETIC_DATA_NOTICE
from core.chromosome import Chromosome, Gene, fallow_gene
from services.data_loader import load_sample_farm
from simulation.farm_simulator import simulate_farm
from simulation.scenario_engine import make_custom_scenario, resilience_score, run_scenarios
from simulation.water_simulator import water_factor


def _plan(context, water=0.8, fert=0.8):
    genes = []
    for plot, season in context.slots:
        crop = context.options[season][0]
        genes.append(Gene(plot, season, crop, water, fert, context.windows_for(crop, season)[0]))
    return Chromosome(genes)


def test_datasets_load(datasets):
    assert len(datasets.crops) >= 8
    assert {"normal", "drought", "excess_rainfall", "input_price_shock", "market_price_drop"} <= set(
        datasets.scenarios["scenario_id"])
    assert {"base_yield_t_per_ha", "selling_price_usd_per_t", "seed_cost_usd_per_ha"} <= set(datasets.crops.columns)
    assert len(datasets.farms) == 3 and "loam" in set(datasets.soils["soil_type"])
    assert load_sample_farm()["farm_name"]


def test_synthetic_data_is_labelled(datasets):
    assert "synthetic" in SYNTHETIC_DATA_NOTICE.lower()
    assert datasets.crops["data_note"].str.contains("synthetic", case=False).all()


def test_simulation_is_deterministic_and_consistent(context, scenarios):
    plan = _plan(context)
    a = simulate_farm(context, plan, scenarios["normal"])
    b = simulate_farm(context, plan, scenarios["normal"])
    assert a.totals == b.totals
    t = a.totals
    assert t["net_profit"] == pytest.approx(t["revenue"] - t["total_cost"])
    assert t["total_yield_t"] > 0 and len(a.gene_results) == len(context.slots)


def test_fallow_plan_costs_nothing(context, scenarios):
    plan = Chromosome([fallow_gene(p, s) for p, s in context.slots])
    t = simulate_farm(context, plan, scenarios["normal"]).totals
    assert t["total_cost"] == 0 and t["revenue"] == 0 and all(g.crop_id == FALLOW for g in plan.genes)


def test_more_fertilizer_raises_yield_until_saturation(context, scenarios):
    low = simulate_farm(context, _plan(context, fert=0.0), scenarios["normal"]).totals["total_yield_t"]
    high = simulate_farm(context, _plan(context, fert=0.9), scenarios["normal"]).totals["total_yield_t"]
    assert high > low


def test_waterlogging_penalty():
    adequate, _, logged_ok = water_factor(100, 100, 0.5, 0.5, 0.5)
    flooded, _, logged = water_factor(200, 100, 0.5, 0.5, 0.5)
    assert not logged_ok and logged and flooded < adequate


@pytest.mark.parametrize("scenario_id,metric", [("drought", "total_yield_t"), ("input_price_shock", "total_cost"),
                                                 ("market_price_drop", "revenue")])
def test_adverse_scenarios_move_metrics(context, scenarios, scenario_id, metric):
    plan = _plan(context)
    normal = simulate_farm(context, plan, scenarios["normal"]).totals
    adverse = simulate_farm(context, plan, scenarios[scenario_id]).totals
    if metric == "total_cost":
        assert adverse[metric] > normal[metric]
    else:
        assert adverse[metric] < normal[metric]
    assert adverse["net_profit"] < normal["net_profit"]


def test_scenarios_and_resilience(context, scenarios):
    custom = make_custom_scenario("Harsh", {"yield_stress_factor": 0.5, "market_price_multiplier": 0.5})
    results = run_scenarios(context, _plan(context), [*scenarios.values(), custom])
    assert set(results) == set(scenarios) | {custom.scenario_id}
    assert 0.0 <= resilience_score(results) <= 1.0
    assert results[custom.scenario_id].totals["net_profit"] < results["normal"].totals["net_profit"]
