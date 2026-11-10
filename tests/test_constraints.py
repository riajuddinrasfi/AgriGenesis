import numpy as np

from core.constraints import check_constraints
from simulation.farm_simulator import resource_usage


def test_all_fallow_is_feasible(context, fallow_genes):
    report = check_constraints(context, fallow_genes)
    assert report.feasible and report.penalty == 0 and report.to_frame().empty


def test_budget_overrun_is_hard_violation(context, fallow_genes, wet_dry):
    context.farm["budget"] = 1.0
    genes = fallow_genes.copy()
    genes[0, wet_dry[0]] = context.crop_index("Aman Rice")
    report = check_constraints(context, genes)
    kinds = {v.kind for v in report.violations}
    assert "budget" in kinds and not report.feasible and report.penalty > 0


def test_labour_overrun_is_hard_violation(context, fallow_genes, wet_dry):
    context.farm["labor_days"] = 1.0
    genes = fallow_genes.copy()
    genes[:, wet_dry[0]] = context.crop_index("Jute")
    assert "labor" in {v.kind for v in check_constraints(context, genes).violations}


def test_out_of_season_crop_is_unsuitable(context, fallow_genes, wet_dry):
    genes = fallow_genes.copy()
    genes[0, wet_dry[0]] = context.crop_index("Wheat")  # dry-season crop in the wet season
    report = check_constraints(context, genes)
    assert [v.kind for v in report.violations] == ["unsuitable"]
    assert not report.feasible


def test_same_family_in_a_row_is_soft(context, fallow_genes, wet_dry):
    wet, dry = wet_dry
    assert dry == wet + 1
    genes = fallow_genes.copy()
    genes[0, wet] = context.crop_index("Aman Rice")
    genes[0, dry] = context.crop_index("Wheat")
    report = check_constraints(context, genes)
    soft = [v for v in report.violations if v.kind == "same_family"]
    assert len(soft) == 1 and not soft[0].hard and soft[0].plot == 0
    assert report.feasible


def test_resource_usage_has_one_row_per_season(context, fallow_genes):
    usage = resource_usage(context, fallow_genes)
    assert len(usage) == context.n_seasons
    assert np.allclose(usage["cost"], 0)
