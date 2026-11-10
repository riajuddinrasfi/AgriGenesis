"""Agronomy Agent: deterministic crop feasibility checks against the supplied datasets."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config import MAX_FERTILIZER_RATIO, SEASONS
from services.data_loader import Datasets
from services.validation_service import FarmProfile
from simulation import soil_simulator as soil_sim
from simulation.crop_simulator import irrigation_need_mm
from simulation.economic_simulator import cost_breakdown
from simulation.weather_simulator import Scenario, valid_windows
from utils.calculations import mm_to_m3

NORMAL = Scenario("normal", "Normal conditions")


@dataclass
class AgronomyReport:
    feasible_options: dict[str, list[str]]
    table: pd.DataFrame
    messages: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(m["level"] == "error" for m in self.messages)


class AgronomyAgent:
    def __init__(self, datasets: Datasets):
        self.crops = {r["crop_id"]: r for r in datasets.crops.to_dict("records")}
        self.soils = datasets.soils.set_index("soil_type")

    def _check(self, profile: FarmProfile, crop: dict, season: str, soil: dict) -> dict:
        area = profile.plot_area_ha
        reasons = []
        season_ok = season in crop["allowed_seasons"]
        if not season_ok:
            reasons.append(f"not grown in {season}")
        soil_ok = profile.soil_type in crop["suitable_soils"]
        if not soil_ok:
            reasons.append(f"unsuited to {profile.soil_type} soil")
        ph = soil_sim.ph_factor(profile.soil_ph, crop["min_ph"], crop["max_ph"])
        if ph == 0:
            reasons.append(f"pH {profile.soil_ph} outside {crop['min_ph']}-{crop['max_ph']}")
        windows = valid_windows(crop["growth_duration_days"], season)
        if not windows:
            reasons.append(f"{crop['growth_duration_days']} days does not fit the "
                           f"{SEASONS[season]['duration_days']}-day season")
        need_mm = irrigation_need_mm(crop, soil, profile.rainfall_mm[season], NORMAL)
        water_m3 = mm_to_m3(need_mm, area)
        fert_kg = crop["fertilizer_requirement_kg_per_ha"] * area
        full_cost = cost_breakdown(crop, area, fert_kg, water_m3)["total_cost"]
        min_cost = cost_breakdown(crop, area, 0.0, 0.0)["total_cost"]
        if min_cost > profile.budget_usd:
            reasons.append(f"minimum cost ${min_cost:,.0f} per plot exceeds budget")
        excluded = crop["crop_id"] in profile.excluded_crops
        if excluded:
            reasons.append("excluded by user")
        return {
            "crop_id": crop["crop_id"], "crop_name": crop["crop_name"], "season": season,
            "season_ok": season_ok, "soil_ok": soil_ok,
            "ph_status": {1.0: "ok", 0.0: "unsuitable"}.get(ph, "marginal"),
            "valid_windows": len(windows), "irrigation_need_m3_per_plot": round(water_m3, 1),
            "fertilizer_need_kg_per_plot": round(fert_kg, 1),
            "full_input_cost_per_plot": round(full_cost, 2),
            "water_fits": water_m3 <= profile.available_water_m3,
            "preferred": crop["crop_id"] in profile.preferred_crops,
            "feasible": not reasons, "notes": "; ".join(reasons) or "feasible",
        }

    def assess(self, profile: FarmProfile) -> AgronomyReport:
        """Return feasible crops per season, a full check table and validation messages."""
        soil = self.soils.loc[profile.soil_type].to_dict()
        rows = [self._check(profile, crop, season, soil)
                for season in profile.seasons for crop in self.crops.values()]
        table = pd.DataFrame(rows)
        messages, options = [], {}
        for season in profile.seasons:
            ok = table[(table["season"] == season) & table["feasible"]]
            feasible = ok["crop_id"].tolist()
            if profile.preferred_crops:
                preferred = [c for c in feasible if c in profile.preferred_crops]
                if preferred:
                    feasible = preferred
                else:
                    messages.append({"level": "warning", "message":
                                     f"No preferred crop is feasible in {season}; using all feasible crops"})
            options[season] = feasible
            if not feasible:
                messages.append({"level": "warning", "message": f"No feasible crop in {season}; plots stay fallow"})
            thirsty = ok[~ok["water_fits"]]["crop_name"].tolist()
            if thirsty:
                messages.append({"level": "info", "message": f"{season}: full irrigation of {', '.join(thirsty)} "
                                 "on one plot exceeds total water; the optimiser will irrigate partially"})
        if not any(options.values()):
            messages.append({"level": "error", "message": "No crop is feasible in any season for this farm"})
        if MAX_FERTILIZER_RATIO and profile.budget_usd < table["full_input_cost_per_plot"].min():
            messages.append({"level": "warning", "message": "Budget is below the cost of fully managing one plot"})
        return AgronomyReport(options, table, messages)
