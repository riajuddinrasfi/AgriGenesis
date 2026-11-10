import numpy as np
import pytest

from core.constraints import check_constraints
from core.fitness import evaluate, risk_aversion
from simulation.farm_simulator import simulate
from utils.calculations import risk_metrics, weighted_mean_std


def test_weighted_mean_std():
    mean, std = weighted_mean_std([0, 10], [1, 1])
    assert mean == pytest.approx(5) and std == pytest.approx(5)
    with pytest.raises(ValueError):
        weighted_mean_std([1, 2], [0, 0])


def test_risk_metrics():
    m = risk_metrics(np.array([-10.0, 0, 10, 20, 30]))
    assert m["mean"] == pytest.approx(10) and m["loss_probability"] == pytest.approx(0.2)
    assert m["cvar5"] <= m["p5"] <= m["mean"]


def test_risk_aversion_follows_tolerance(context):
    context.farm["risk_tolerance"] = 1.0
    assert risk_aversion(context) == 0
    context.farm["risk_tolerance"] = 0.0
    assert risk_aversion(context) > 0


def test_fitness_components_add_up(context, wet_dry):
    genes = np.full((context.n_plots, context.n_seasons), context.crop_index("Mung Bean"))
    genes[:, wet_dry[1]::2] = context.crop_index("Lentil")
    fit = evaluate(context, genes)
    probs = context.scenarios["probability"].to_numpy()
    profits = simulate(context, genes, context.scenarios).total_profit
    assert fit.expected_profit == pytest.approx(probs @ profits / probs.sum())
    assert fit.worst_case_profit == pytest.approx(profits.min())
    assert fit.penalty == pytest.approx(check_constraints(context, genes).penalty)
    expected = fit.expected_profit - risk_aversion(context) * fit.profit_std + fit.soil_health - fit.penalty
    assert fit.fitness == pytest.approx(expected)


def test_legumes_score_better_soil_health_than_cereals(context, wet_dry):
    wet, dry = wet_dry
    legumes = np.full((context.n_plots, context.n_seasons), context.crop_index("Mung Bean"))
    legumes[:, dry::2] = context.crop_index("Lentil")
    cereals = np.full((context.n_plots, context.n_seasons), context.crop_index("Aman Rice"))
    cereals[:, dry::2] = context.crop_index("Wheat")
    assert evaluate(context, legumes).soil_health > 0 > evaluate(context, cereals).soil_health


def test_penalties_lower_fitness(context, fallow_genes, wet_dry):
    genes = fallow_genes.copy()
    genes[0, wet_dry[0]] = context.crop_index("Wheat")
    assert evaluate(context, genes).fitness < evaluate(context, fallow_genes).fitness
