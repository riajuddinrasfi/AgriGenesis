"""Whole-farm simulation of one strategy under one scenario.

A demonstration model on synthetic data: transparent formulas, not a scientifically validated crop model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config import DATA_DIR, FALLOW, FALLOW_SOIL_EFFECT, SEASONS, SIMULATOR_DISCLAIMER
from core.chromosome import Chromosome, Gene
from services.data_loader import Datasets, load_datasets, load_sample_farm
from services.validation_service import FarmProfile, validate_farm_input
from simulation import soil_simulator as soil_sim
from simulation.crop_simulator import irrigation_need_mm, simulate_crop
from simulation.water_simulator import supply_scale
from simulation.weather_simulator import Scenario, valid_windows
from utils.calculations import mm_to_m3

COST_KEYS = ("seed_cost", "fertilizer_cost", "labor_cost", "irrigation_cost")


@dataclass
class FarmContext:
    """Everything the simulator needs about one farm: profile, crop data, soil and options."""

    profile: FarmProfile
    crops: dict[str, dict]
    soil: dict
    options: dict[str, list[str]] = field(default_factory=dict)

    @property
    def seasons(self) -> list[str]:
        return self.profile.seasons

    @property
    def plot_ids(self) -> list[int]:
        return list(range(1, self.profile.n_plots + 1))

    @property
    def slots(self) -> list[tuple[int, str]]:
        return [(p, s) for p in self.plot_ids for s in self.seasons]

    def crop(self, crop_id: str) -> dict:
        return self.crops[crop_id]

    def windows_for(self, crop_id: str, season: str) -> list[int]:
        if crop_id == FALLOW:
            return [0]
        return valid_windows(self.crops[crop_id]["growth_duration_days"], season)

    def crop_name(self, crop_id: str) -> str:
        return "Fallow" if crop_id == FALLOW else self.crops[crop_id]["crop_name"]


def basic_options(profile: FarmProfile, crops: dict[str, dict]) -> dict[str, list[str]]:
    """Crops that pass season, soil, pH and duration checks (no preferences applied)."""
    options = {}
    for season in profile.seasons:
        options[season] = [
            cid for cid, c in crops.items()
            if season in c["allowed_seasons"] and profile.soil_type in c["suitable_soils"]
            and soil_sim.ph_factor(profile.soil_ph, c["min_ph"], c["max_ph"]) > 0
            and valid_windows(c["growth_duration_days"], season)
            and cid not in profile.excluded_crops
        ]
    return options


def build_context(profile: FarmProfile, datasets: Datasets,
                  options: dict[str, list[str]] | None = None) -> FarmContext:
    crops = {r["crop_id"]: r for r in datasets.crops.to_dict("records")}
    soil = datasets.soils.set_index("soil_type").loc[profile.soil_type].to_dict()
    soil["soil_type"] = profile.soil_type
    return FarmContext(profile, crops, soil, options or basic_options(profile, crops))


def sample_context(datasets: Datasets | None = None) -> FarmContext:
    """Context for ``data/sample_farm.json``, loaded and validated through ``services.data_loader``."""
    datasets = datasets or load_datasets(DATA_DIR)
    farm = {k: v for k, v in load_sample_farm(DATA_DIR).items() if k not in ("data_note", "weights")}
    profile = validate_farm_input(farm, datasets.crop_ids, datasets.soil_types)
    return build_context(profile, datasets)


@dataclass
class SimulationResult:
    """Per-gene rows and farm totals (USD, tonnes, m3, soil-health points) for one scenario."""

    scenario_id: str
    gene_results: list[dict]
    totals: dict
    note: str = SIMULATOR_DISCLAIMER


def index_genes(context: FarmContext, chromosome: Chromosome) -> dict[tuple[int, str], Gene]:
    """Map (plot, season) to gene, rejecting strategies that do not cover the farm exactly once."""
    slots, genes = set(context.slots), {}
    for g in chromosome.genes:
        key = (g.plot_id, g.season)
        if key not in slots:
            raise ValueError(f"Gene for plot {g.plot_id}, season {g.season!r} is outside this farm")
        if key in genes:
            raise ValueError(f"Strategy has two genes for plot {g.plot_id}, season {g.season!r}")
        if not g.is_fallow and g.crop_id not in context.crops:
            raise ValueError(f"Unknown crop_id {g.crop_id!r} for plot {g.plot_id}, season {g.season!r}")
        for name in ("water_level", "fertilizer_level"):
            if not 0.0 <= getattr(g, name) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1 (got {getattr(g, name)})")
        genes[key] = g
    missing = [k for k in context.slots if k not in genes]
    if missing:
        raise ValueError(f"Strategy has no gene for plot-season slots {missing}")
    return genes


def _fallow_result(gene: Gene) -> dict:
    zero = {k: 0.0 for k in ("rainfall_mm", "effective_rainfall_mm", "irrigation_mm", "water_use_m3",
                             "water_adequacy", "water_factor", "soil_factor", "weather_factor",
                             "nutrient_factor", "fertilizer_kg", "yield_t", "potential_yield_t",
                             "revenue", *COST_KEYS, "total_cost", "profit")}
    return {**zero, "waterlogged": False, "soil_health_delta": FALLOW_SOIL_EFFECT}


def irrigation_demand_m3(context: FarmContext, chromosome: Chromosome,
                         scenario: Scenario) -> dict[tuple[int, str], float]:
    """Planned irrigation volume per (plot, season) before any supply limit is applied."""
    area = context.profile.plot_area_ha
    return {
        (g.plot_id, g.season): 0.0 if g.is_fallow else mm_to_m3(
            irrigation_need_mm(context.crop(g.crop_id), context.soil,
                               context.profile.rainfall_mm[g.season], scenario) * g.water_level, area)
        for g in chromosome.genes
    }


def simulate_farm(context: FarmContext, chromosome: Chromosome, scenario: Scenario) -> SimulationResult:
    """Simulate every gene; soil health carries over season to season on each plot."""
    profile, area = context.profile, context.profile.plot_area_ha
    genes = index_genes(context, chromosome)

    demand = sum(irrigation_demand_m3(context, chromosome, scenario).values())
    available = profile.available_water_m3 * scenario.water_availability_multiplier
    scale = supply_scale(demand, available)

    rows, final_health = [], []
    for plot in context.plot_ids:
        health, previous_family = profile.soil_health_index, None
        for season in context.seasons:
            gene = genes[(plot, season)]
            if gene.is_fallow:
                result, family = _fallow_result(gene), None
            else:
                crop = context.crop(gene.crop_id)
                family = crop["crop_family"]
                result = simulate_crop(crop, gene, area, context.soil, profile.soil_ph,
                                       profile.rainfall_mm[season], scenario, health,
                                       family == previous_family, scale)
            start = health
            health = soil_sim.update_soil_health(health, result["soil_health_delta"])
            rows.append({**gene.to_dict(), "crop_name": context.crop_name(gene.crop_id),
                         "season_name": SEASONS[season]["name"], "area_ha": 0.0 if gene.is_fallow else area,
                         "soil_health_start": start, "soil_health_end": health, **result})
            previous_family = family
        final_health.append(health)

    totals = {k: sum(r[k] for r in rows) for k in ("yield_t", "revenue", *COST_KEYS, "total_cost",
                                                   "profit", "water_use_m3", "fertilizer_kg")}
    totals["total_yield_t"] = totals.pop("yield_t")
    totals["net_profit"] = totals.pop("profit")
    slots = max(1, len(rows))
    totals["yield_achievement"] = sum(
        r["yield_t"] / r["potential_yield_t"] for r in rows if r["potential_yield_t"] > 0) / slots
    totals["water_available_m3"] = available
    totals["irrigation_supply_scale"] = scale
    totals["final_soil_health"] = sum(final_health) / len(final_health)
    totals["soil_health_change"] = totals["final_soil_health"] - profile.soil_health_index
    totals["waterlogged_genes"] = sum(1 for r in rows if r["waterlogged"])
    totals["land_used_ha"] = {s: sum(r["area_ha"] for r in rows if r["season"] == s) for s in context.seasons}
    return SimulationResult(scenario.scenario_id, rows, totals)
