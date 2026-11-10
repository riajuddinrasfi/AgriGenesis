"""Loads the synthetic CSV/JSON datasets (cached) and checks their schema."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from config import DATA_DIR
from utils.helpers import split_list

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "crops.csv": ["crop_id", "crop_name", "crop_family", "base_yield_t_per_ha",
                  "selling_price_usd_per_t", "growth_duration_days"],
    "crop_requirements.csv": ["crop_id", "allowed_seasons", "suitable_soils", "min_ph", "max_ph",
                              "water_requirement_mm", "fertilizer_requirement_kg_per_ha",
                              "drought_tolerance", "waterlogging_tolerance", "soil_health_effect"],
    "input_costs.csv": ["crop_id", "seed_cost_usd_per_ha", "labor_cost_usd_per_ha",
                        "fertilizer_cost_usd_per_kg", "irrigation_cost_usd_per_m3"],
    "soil_profiles.csv": ["soil_type", "soil_name", "fertility_factor",
                          "effective_rainfall_fraction", "drainage_factor"],
    "farms.csv": ["farm_id", "farm_name", "total_area_ha", "n_plots", "soil_type", "soil_ph",
                  "soil_health_index", "available_water_m3", "budget_usd", "seasons",
                  "rainfall_monsoon_mm", "rainfall_winter_mm", "rainfall_summer_mm"],
    "weather_scenarios.csv": ["scenario_id", "scenario_name", "rainfall_multiplier",
                              "yield_stress_factor", "input_cost_multiplier",
                              "market_price_multiplier", "water_availability_multiplier"],
}


class DataError(ValueError):
    """Raised when a dataset is missing or malformed."""


@dataclass(frozen=True)
class Datasets:
    crops: pd.DataFrame      # crops + requirements + input costs, one row per crop
    soils: pd.DataFrame
    farms: pd.DataFrame
    scenarios: pd.DataFrame

    @property
    def crop_ids(self) -> list[str]:
        return self.crops["crop_id"].tolist()

    @property
    def soil_types(self) -> list[str]:
        return self.soils["soil_type"].tolist()


@lru_cache(maxsize=None)
def _read_csv(data_dir: str, name: str) -> pd.DataFrame:
    path = Path(data_dir) / name
    if not path.exists():
        raise DataError(f"Dataset not found: {path}")
    frame = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS.get(name, []) if c not in frame.columns]
    if missing:
        raise DataError(f"{name} is missing columns: {', '.join(missing)}")
    if frame.empty:
        raise DataError(f"{name} has no rows")
    return frame


def read_csv(name: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Cached CSV read; returns a copy so callers cannot mutate the cache."""
    return _read_csv(str(data_dir), name).copy()


def load_crops(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    crops = read_csv("crops.csv", data_dir)
    reqs = read_csv("crop_requirements.csv", data_dir)
    costs = read_csv("input_costs.csv", data_dir)
    for name, frame in (("crop_requirements.csv", reqs), ("input_costs.csv", costs)):
        unknown = set(frame["crop_id"]) ^ set(crops["crop_id"])
        if unknown:
            raise DataError(f"{name} crop_ids do not match crops.csv: {sorted(unknown)}")
    merged = crops.merge(reqs, on="crop_id").merge(costs, on="crop_id")
    merged["allowed_seasons"] = merged["allowed_seasons"].map(split_list)
    merged["suitable_soils"] = merged["suitable_soils"].map(split_list)
    return merged


def load_soil_profiles(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return read_csv("soil_profiles.csv", data_dir)


def load_farms(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return read_csv("farms.csv", data_dir)


def load_scenarios(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return read_csv("weather_scenarios.csv", data_dir)


def load_sample_farm(data_dir: Path = DATA_DIR) -> dict:
    path = Path(data_dir) / "sample_farm.json"
    if not path.exists():
        raise DataError(f"Dataset not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_datasets(data_dir: Path = DATA_DIR) -> Datasets:
    """Load every dataset and cross-check the references between them."""
    datasets = Datasets(
        crops=load_crops(data_dir),
        soils=load_soil_profiles(data_dir),
        farms=load_farms(data_dir),
        scenarios=load_scenarios(data_dir),
    )
    soil_types = set(datasets.soil_types)
    for _, crop in datasets.crops.iterrows():
        bad = set(crop["suitable_soils"]) - soil_types
        if bad:
            raise DataError(f"{crop['crop_id']} references unknown soil types {sorted(bad)}")
    bad_farms = set(datasets.farms["soil_type"]) - soil_types
    if bad_farms:
        raise DataError(f"farms.csv references unknown soil types {sorted(bad_farms)}")
    if "normal" not in set(datasets.scenarios["scenario_id"]):
        raise DataError("weather_scenarios.csv must contain a 'normal' scenario")
    return datasets


def farm_row_to_input(row: pd.Series | dict) -> dict:
    """Convert a ``farms.csv`` row into the farm-input dictionary used by the app."""
    row = dict(row)
    seasons = split_list(row.get("seasons"))
    return {
        "farm_name": row.get("farm_name"),
        "total_area_ha": row.get("total_area_ha"),
        "n_plots": row.get("n_plots"),
        "soil_type": row.get("soil_type"),
        "soil_ph": row.get("soil_ph"),
        "soil_health_index": row.get("soil_health_index"),
        "available_water_m3": row.get("available_water_m3"),
        "budget_usd": row.get("budget_usd"),
        "seasons": seasons,
        "rainfall_mm": {s: row.get(f"rainfall_{s}_mm") for s in ("monsoon", "winter", "summer")},
        "preferred_crops": split_list(row.get("preferred_crops")),
        "excluded_crops": split_list(row.get("excluded_crops")),
    }
