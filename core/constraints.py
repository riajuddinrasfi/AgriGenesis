"""Hard constraints on a strategy and the repair operator that enforces them."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from config import FALLOW
from core.chromosome import Chromosome, Gene, fallow_gene
from simulation.farm_simulator import FarmContext, irrigation_demand_m3, simulate_farm
from simulation.weather_simulator import Scenario
from utils.normalization import clip
from utils.random_generator import choice

NEUTRAL = Scenario("normal", "Normal conditions")
TOL = 1e-6


@dataclass
class ConstraintReport:
    violations: list[dict] = field(default_factory=list)
    land_used_ha: dict[str, float] = field(default_factory=dict)
    total_cost: float = 0.0
    water_demand_m3: float = 0.0

    @property
    def feasible(self) -> bool:
        return not self.violations

    def add(self, kind: str, message: str, amount: float = 0.0) -> None:
        self.violations.append({"kind": kind, "message": message, "amount": amount})


def _gene_problems(context: FarmContext, gene: Gene) -> list[str]:
    problems = []
    if not (0.0 <= gene.water_level <= 1.0 and 0.0 <= gene.fertilizer_level <= 1.0):
        problems.append("management levels must be within [0, 1]")
    if gene.is_fallow:
        return problems
    if gene.crop_id not in context.options.get(gene.season, []):
        problems.append(f"{gene.crop_id} is not a feasible crop in {gene.season}")
    elif gene.planting_window not in context.windows_for(gene.crop_id, gene.season):
        problems.append(f"{gene.crop_id} planted in window {gene.planting_window} does not fit the season")
    return problems


def check_constraints(context: FarmContext, chromosome: Chromosome,
                      baseline: Scenario = NEUTRAL) -> ConstraintReport:
    """Check land, budget, water, crop-season and planting-duration constraints."""
    report = ConstraintReport()
    profile = context.profile
    slots = [(g.plot_id, g.season) for g in chromosome.genes]
    if sorted(slots) != sorted(context.slots) or len(set(slots)) != len(slots):
        report.add("structure", "Strategy must contain exactly one gene per plot and season")
        return report
    for gene in chromosome.genes:
        for problem in _gene_problems(context, gene):
            report.add("allocation", f"Plot {gene.plot_id}, {gene.season}: {problem}")

    result = simulate_farm(context, chromosome, baseline)
    report.land_used_ha = result.totals["land_used_ha"]
    for season, used in report.land_used_ha.items():
        if used > profile.total_area_ha + TOL:
            report.add("land", f"{season}: {used:.2f} ha allocated exceeds {profile.total_area_ha:.2f} ha",
                       used - profile.total_area_ha)
    report.total_cost = result.totals["total_cost"]
    if report.total_cost > profile.budget_usd + TOL:
        report.add("budget", f"Cost ${report.total_cost:,.0f} exceeds budget ${profile.budget_usd:,.0f}",
                   report.total_cost - profile.budget_usd)
    report.water_demand_m3 = sum(irrigation_demand_m3(context, chromosome, baseline).values())
    available = profile.available_water_m3 * baseline.water_availability_multiplier
    if report.water_demand_m3 > available + TOL:
        report.add("water", f"Irrigation {report.water_demand_m3:,.0f} m3 exceeds {available:,.0f} m3",
                   report.water_demand_m3 - available)
    return report


def _repair_gene(context: FarmContext, gene: Gene, rng: np.random.Generator) -> Gene:
    if gene.is_fallow:
        return fallow_gene(gene.plot_id, gene.season)
    crop_id = gene.crop_id
    options = context.options.get(gene.season, [])
    if crop_id not in options:
        crop_id = choice(rng, options) if options else FALLOW
    if crop_id == FALLOW:
        return fallow_gene(gene.plot_id, gene.season)
    windows = context.windows_for(crop_id, gene.season)
    window = gene.planting_window
    if window not in windows:
        earlier = [w for w in windows if w <= window]
        window = max(earlier) if earlier else windows[0]
    return Gene(gene.plot_id, gene.season, crop_id, round(clip(gene.water_level), 2),
                round(clip(gene.fertilizer_level), 2), window)


def repair(context: FarmContext, chromosome: Chromosome, rng: np.random.Generator,
           baseline: Scenario = NEUTRAL) -> Chromosome:
    """Return a feasible copy of ``chromosome``.

    1. one gene per slot, valid crop/season/window, levels clipped to [0, 1];
    2. water levels scaled down until irrigation fits the available water;
    3. least profitable plantings switched to fallow until costs fit the budget.
    """
    by_slot = {(g.plot_id, g.season): g for g in chromosome.genes}
    genes = [_repair_gene(context, by_slot.get(slot) or fallow_gene(*slot), rng) for slot in context.slots]
    repaired = Chromosome(genes)

    profile = context.profile
    available = profile.available_water_m3 * baseline.water_availability_multiplier
    demand = sum(irrigation_demand_m3(context, repaired, baseline).values())
    if demand > available + TOL:
        factor = available / demand
        repaired = Chromosome([g if g.is_fallow else g.with_changes(
            water_level=math.floor(g.water_level * factor * 100) / 100) for g in repaired.genes])

    for _ in range(len(repaired.genes)):
        result = simulate_farm(context, repaired, baseline)
        if result.totals["total_cost"] <= profile.budget_usd + TOL:
            break
        planted = [(r["profit"], i) for i, r in enumerate(result.gene_results) if r["crop_id"] != FALLOW]
        if not planted:
            break
        index = {(g.plot_id, g.season): i for i, g in enumerate(repaired.genes)}
        worst = result.gene_results[min(planted)[1]]
        slot = (worst["plot_id"], worst["season"])
        genes = list(repaired.genes)
        genes[index[slot]] = fallow_gene(*slot)
        repaired = Chromosome(genes)
    return repaired
