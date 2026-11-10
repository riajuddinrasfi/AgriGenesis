import numpy as np
import pandas as pd
import pytest

from simulation.farm_simulator import monte_carlo, scenario_breakdown, simulate
from simulation.scenario_engine import scenario_params, select_scenarios
from simulation.soil_simulator import FALLOW_NITROGEN_GAIN, rotation_matrix, update_nitrogen
from simulation.water_simulator import allocate_irrigation


def plan(context, wet_crop, dry_crop):
    genes = np.empty((context.n_plots, context.n_seasons), dtype=int)
    for s, season in enumerate(context.seasons):
        genes[:, s] = context.crop_index(wet_crop if season["type"] == "wet" else dry_crop)
    return genes


def test_fallow_has_no_revenue_or_cost(context, fallow_genes):
    result = simulate(context, fallow_genes, context.scenarios)
    assert np.allclose(result.revenue, 0) and np.allclose(result.cost, 0)
    assert np.allclose(result.water_m3, 0) and np.allclose(result.labor_days, 0)


def test_fallow_rebuilds_nitrogen(context, fallow_genes):
    start = float(context.farm["soil_nitrogen"])
    gain = FALLOW_NITROGEN_GAIN + float(context.farm["organic_matter_pct"])
    expected = min(100.0, start + gain * context.n_seasons)
    assert simulate(context, fallow_genes).final_nitrogen[0] == pytest.approx(expected)


def test_update_nitrogen_is_clipped():
    n = update_nitrogen(np.array([95.0, 5.0]), np.array([True, True]), np.array([30.0, -50.0]), 0)
    assert list(n) == [100.0, 0.0]


def test_rotation_matrix():
    m = rotation_matrix(["Poaceae", "Fabaceae", "Poaceae"], same_family_factor=0.9, legume_bonus=1.1)
    assert m[0, 2] == 0.9 and m[1, 0] == 1.1 and m[1, 1] == 0.9 and m[0, 1] == 1.0
    assert m.shape == (4, 4) and (m[-1] == 1).all() and (m[:, -1] == 1).all()


def test_irrigation_shared_pro_rata():
    need = np.array([[500.0, 500.0]])
    _, sat, m3 = allocate_irrigation(need, np.array([[0.0]]), np.ones((1, 2)), 1.0, 5000.0)
    assert m3.sum() == pytest.approx(5000) and np.allclose(sat, 0.5)


def test_prices_scale_revenue(context):
    genes = plan(context, "Jute", "Lentil")
    base = simulate(context, genes).revenue.sum()
    boom = simulate(context, genes, {**scenario_params_row(), "price_factor": 1.5}).revenue.sum()
    assert boom == pytest.approx(1.5 * base)


def scenario_params_row():
    return {"scenario": "x", "rainfall_factor": 1.0, "temp_shift": 0.0, "price_factor": 1.0,
            "cost_factor": 1.0, "pest_pressure": 0.0, "yield_shock": 1.0}


def test_drought_and_pests_hurt_profit(context):
    genes = plan(context, "Aman Rice", "Potato")
    normal = simulate(context, genes, scenario_params_row()).total_profit[0]
    for change in ({"rainfall_factor": 0.4, "temp_shift": 3.0}, {"pest_pressure": 0.8}):
        assert simulate(context, genes, {**scenario_params_row(), **change}).total_profit[0] < normal


def test_no_irrigation_capacity_means_no_irrigation(context):
    context.farm["irrigation_m3"] = 0
    assert np.allclose(simulate(context, plan(context, "Aman Rice", "Boro Rice")).water_m3, 0)


def test_scenario_breakdown_and_selection(context):
    genes = plan(context, "Jute", "Potato")
    table = scenario_breakdown(context, genes)
    assert len(table) == len(context.scenarios)
    assert np.allclose(table["profit"], table["revenue"] - table["cost"])
    chosen = select_scenarios(context.scenarios, ["Drought", "Normal Year"])
    assert set(chosen["scenario"]) == {"Drought", "Normal Year"}
    assert chosen["probability"].sum() == pytest.approx(1)
    with pytest.raises(ValueError):
        select_scenarios(context.scenarios, ["Nope"])
    assert scenario_params(pd.DataFrame([scenario_params_row()]))["price_factor"].shape == (1, 1)


def test_monte_carlo_is_reproducible(context):
    genes = plan(context, "Jute", "Potato")
    a = monte_carlo(context, genes, n_runs=200, seed=7)
    b = monte_carlo(context, genes, n_runs=200, seed=7)
    assert len(a) == 200 and a.equals(b)
    assert set(a["scenario"]) <= set(context.scenarios["scenario"])


def test_detailed_output(context):
    details = simulate(context, plan(context, "Jute", "Potato"), detailed=True).details
    assert len(details) == context.n_plots * context.n_seasons
    assert np.allclose(details["profit"], details["revenue"] - details["cost"])
