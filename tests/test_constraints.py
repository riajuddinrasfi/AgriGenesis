"""Farm-input validation, agronomy (crop compatibility) and constraint repair."""
from __future__ import annotations

import dataclasses

import pytest

from agents.agronomy_agent import AgronomyAgent
from config import FALLOW
from core.chromosome import Chromosome, Gene
from core.constraints import check_constraints, repair
from core.population import random_chromosome
from services.validation_service import FarmValidationError, validate_farm_input, validate_weights
from simulation.farm_simulator import build_context


def _validate(datasets, data):
    return validate_farm_input(data, datasets.crop_ids, datasets.soils["soil_type"].tolist())


def test_sample_farm_validates(profile):
    assert profile.total_area_ha == 4.0 and profile.n_plots == 4
    assert profile.plot_area_ha == pytest.approx(1.0)


@pytest.mark.parametrize("field,value", [("total_area_ha", -1), ("budget_usd", "abc"), ("n_plots", 0),
                                         ("soil_ph", 15), ("soil_type", "moon_dust"), ("seasons", [])])
def test_invalid_values_rejected(datasets, sample_input, field, value):
    with pytest.raises(FarmValidationError):
        _validate(datasets, {**sample_input, field: value})


def test_missing_numbers_are_not_silently_defaulted(datasets, sample_input):
    data = {k: v for k, v in sample_input.items() if k not in ("available_water_m3", "budget_usd")}
    with pytest.raises(FarmValidationError) as err:
        _validate(datasets, data)
    text = " ".join(err.value.errors)
    assert "available_water_m3" in text and "budget_usd" in text


def test_weights_normalised_and_validated():
    weights = validate_weights({"profit": 2, "yield": 1, "water": 1, "soil": 0, "resilience": 0})
    assert sum(weights.values()) == pytest.approx(1.0) and weights["profit"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        validate_weights({"profit": 1})


def test_crop_season_compatibility(datasets, profile):
    report = AgronomyAgent(datasets).assess(profile)
    assert report.ok
    assert "WHEAT" in report.feasible_options["winter"]
    assert "WHEAT" not in report.feasible_options["monsoon"]
    assert "RICE" not in report.feasible_options["winter"]


def test_excluded_crops_are_removed(datasets, sample_input):
    profile = _validate(datasets, {**sample_input, "excluded_crops": ["RICE"]})
    options = AgronomyAgent(datasets).assess(profile).feasible_options
    assert all("RICE" not in crops for crops in options.values())


def test_random_chromosomes_have_one_gene_per_plot_season(context, rng):
    chrom = random_chromosome(context, rng)
    assert [(g.plot_id, g.season) for g in chrom.genes] == context.slots


def test_repair_fixes_invalid_crop_and_levels(context, rng):
    chrom = repair(context, random_chromosome(context, rng), rng)
    genes = list(chrom.genes)
    winter = next(i for i, g in enumerate(genes) if g.season == "winter")
    genes[winter] = dataclasses.replace(genes[winter], crop_id="RICE", water_level=1.7, fertilizer_level=-0.5)
    broken = Chromosome(genes)
    assert not check_constraints(context, broken).feasible
    fixed = repair(context, broken, rng)
    assert check_constraints(context, fixed).feasible
    gene = fixed.genes[winter]
    assert gene.crop_id in context.options["winter"] + [FALLOW]
    assert 0.0 <= gene.water_level <= 1.0 and 0.0 <= gene.fertilizer_level <= 1.0


def test_repair_enforces_budget_and_water(datasets, sample_input, rng):
    tight = _validate(datasets, {**sample_input, "budget_usd": 1500, "available_water_m3": 2000})
    context = build_context(tight, datasets, AgronomyAgent(datasets).assess(tight).feasible_options)
    for _ in range(10):
        chrom = Chromosome([Gene(p, s, context.options[s][0], 1.0, 1.0, context.windows_for(context.options[s][0], s)[0])
                            for p, s in context.slots])
        fixed = repair(context, chrom, rng)
        report = check_constraints(context, fixed)
        assert report.feasible, report.violations
        assert report.total_cost <= 1500 + 1e-6
        assert report.water_demand_m3 <= 2000 + 1e-6
