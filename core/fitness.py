"""Weighted, normalised single-objective fitness evaluated with real scenario simulations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from config import DEFAULT_WEIGHTS, MAX_FERTILIZER_RATIO
from core.chromosome import Chromosome, Gene
from core.constraints import check_constraints
from services.validation_service import validate_weights
from simulation.crop_simulator import simulate_crop
from simulation.farm_simulator import FarmContext, SimulationResult
from simulation.scenario_engine import BASELINE_ID, resilience_score, run_scenarios
from simulation.weather_simulator import Scenario
from utils.normalization import clip, min_max, safe_ratio

INFEASIBLE_PENALTY = 0.5


@dataclass
class FitnessResult:
    fitness: float
    components: dict[str, float]      # normalised 0-1 scores
    contributions: dict[str, float]   # weight * score
    metrics: dict[str, float]         # raw metrics behind the scores (baseline scenario)
    scenario_profits: dict[str, float]
    feasible: bool
    violations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def reference_max_profit(context: FarmContext, baseline: Scenario) -> float:
    """Upper reference for profit: best single-crop profit on every slot, ignoring limits."""
    total = 0.0
    profile = context.profile
    for plot, season in context.slots:
        best = 0.0
        for crop_id in context.options.get(season, []):
            crop = context.crop(crop_id)
            for window in context.windows_for(crop_id, season):
                gene = Gene(plot, season, crop_id, 1.0, 1.0 / MAX_FERTILIZER_RATIO, window)
                result = simulate_crop(crop, gene, profile.plot_area_ha, context.soil, profile.soil_ph,
                                       profile.rainfall_mm[season], baseline,
                                       profile.soil_health_index, False)
                best = max(best, result["profit"])
        total += best
    return total


class FitnessEvaluator:
    """Scores strategies; calls the simulator for every scenario and caches by chromosome."""

    def __init__(self, context: FarmContext, scenarios: list[Scenario],
                 weights: dict[str, float] | None = None):
        self.context = context
        self.weights = validate_weights(weights or DEFAULT_WEIGHTS)
        ids = [s.scenario_id for s in scenarios]
        if BASELINE_ID not in ids:
            raise ValueError("Scenarios must include the 'normal' baseline")
        self.scenarios = scenarios
        self.baseline = scenarios[ids.index(BASELINE_ID)]
        self.profit_ceiling = max(reference_max_profit(context, self.baseline), 1.0)
        self.profit_floor = -context.profile.budget_usd
        self.cache: dict[tuple, FitnessResult] = {}
        self.chromosomes: dict[tuple, Chromosome] = {}

    @property
    def evaluations(self) -> int:
        return len(self.cache)

    def score(self, results: dict[str, SimulationResult]) -> tuple[dict[str, float], dict[str, float]]:
        base = results[BASELINE_ID].totals
        available = base["water_available_m3"]
        used = base["water_use_m3"]
        water_score = 1.0 - safe_ratio(used, available, default=0.0 if used > 0 else 0.0)
        components = {
            "profit": min_max(base["net_profit"], self.profit_floor, self.profit_ceiling),
            "yield": clip(base["yield_achievement"]),
            "water": clip(water_score) if available > 0 else (1.0 if used == 0 else 0.0),
            "soil": clip(base["final_soil_health"] / 100.0),
            "resilience": clip(resilience_score(results)),
        }
        metrics = {
            "net_profit": base["net_profit"], "revenue": base["revenue"], "total_cost": base["total_cost"],
            "total_yield_t": base["total_yield_t"], "yield_achievement": base["yield_achievement"],
            "water_use_m3": used, "water_available_m3": available,
            "final_soil_health": base["final_soil_health"], "soil_health_change": base["soil_health_change"],
            "profit_ceiling": self.profit_ceiling, "profit_floor": self.profit_floor,
        }
        return components, metrics

    def evaluate(self, chromosome: Chromosome) -> FitnessResult:
        key = chromosome.key
        if key in self.cache:
            return self.cache[key]
        results = run_scenarios(self.context, chromosome, self.scenarios)
        components, metrics = self.score(results)
        contributions = {k: self.weights[k] * components[k] for k in self.weights}
        fitness = sum(contributions.values())
        report = check_constraints(self.context, chromosome, self.baseline)
        if not report.feasible:
            fitness -= INFEASIBLE_PENALTY
        result = FitnessResult(
            fitness=fitness, components=components, contributions=contributions, metrics=metrics,
            scenario_profits={sid: r.totals["net_profit"] for sid, r in results.items()},
            feasible=report.feasible, violations=report.violations,
        )
        self.cache[key] = result
        self.chromosomes[key] = chromosome
        return result

    def ranked(self, top_k: int = 5) -> list[tuple[Chromosome, FitnessResult]]:
        """Best distinct strategies evaluated so far, feasible ones first."""
        order = sorted(self.cache, key=lambda k: (self.cache[k].feasible, self.cache[k].fitness), reverse=True)
        return [(self.chromosomes[k], self.cache[k]) for k in order[:top_k]]
