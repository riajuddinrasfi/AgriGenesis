"""Loads the synthetic CSV/JSON datasets (cached) and validates their schema and values."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from config import DATA_DIR, SCENARIO_LIMITS, SEASONS
from utils.helpers import split_list

NOTE = ["data_note"]
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "crops.csv": ["crop_id", "crop_name", "crop_family", "base_yield_t_per_ha",
                  "selling_price_usd_per_t", "growth_duration_days", *NOTE],
    "crop_requirements.csv": ["crop_id", "allowed_seasons", "suitable_soils", "min_ph", "max_ph",
                              "water_requirement_mm", "fertilizer_requirement_kg_per_ha",
                              "drought_tolerance", "waterlogging_tolerance", "soil_health_effect", *NOTE],
    "input_costs.csv": ["crop_id", "seed_cost_usd_per_ha", "labor_cost_usd_per_ha",
                        "fertilizer_cost_usd_per_kg", "irrigation_cost_usd_per_m3", *NOTE],
    "soil_profiles.csv": ["soil_type", "soil_name", "fertility_factor",
                          "effective_rainfall_fraction", "drainage_factor", *NOTE],
    "farms.csv": ["farm_id", "farm_name", "total_area_ha", "n_plots", "soil_type", "soil_ph",
                  "soil_health_index", "available_water_m3", "budget_usd", "seasons",
                  "rainfall_monsoon_mm", "rainfall_winter_mm", "rainfall_summer_mm", *NOTE],
    "weather_scenarios.csv": ["scenario_id", "scenario_name", *SCENARIO_LIMITS, *NOTE],
}

ID_COLUMNS = {"crops.csv": "crop_id", "crop_requirements.csv": "crop_id", "input_costs.csv": "crop_id",
              "soil_profiles.csv": "soil_type", "farms.csv": "farm_id", "weather_scenarios.csv": "scenario_id"}

# column -> (minimum, maximum, minimum_is_exclusive); None means unbounded.
VALUE_RULES: dict[str, dict[str, tuple[float | None, float | None, bool]]] = {
    "crops.csv": {"base_yield_t_per_ha": (0, None, True), "selling_price_usd_per_t": (0, None, True),
                  "growth_duration_days": (0, 365, True)},
    "crop_requirements.csv": {"min_ph": (0, 14, False), "max_ph": (0, 14, False),
                              "water_requirement_mm": (0, None, False),
                              "fertilizer_requirement_kg_per_ha": (0, None, False),
                              "drought_tolerance": (0, 1, False), "waterlogging_tolerance": (0, 1, False),
                              "soil_health_effect": (-10, 10, False)},
    "input_costs.csv": {"seed_cost_usd_per_ha": (0, None, False), "labor_cost_usd_per_ha": (0, None, False),
                        "fertilizer_cost_usd_per_kg": (0, None, False),
                        "irrigation_cost_usd_per_m3": (0, None, False)},
    "soil_profiles.csv": {"fertility_factor": (0, 2, True), "effective_rainfall_fraction": (0, 1, False),
                          "drainage_factor": (0, 1, False)},
    "farms.csv": {"total_area_ha": (0, None, True), "n_plots": (1, None, False), "soil_ph": (0, 14, False),
                  "soil_health_index": (0, 100, False), "available_water_m3": (0, None, False),
                  "budget_usd": (0, None, False), "rainfall_monsoon_mm": (0, None, False),
                  "rainfall_winter_mm": (0, None, False), "rainfall_summer_mm": (0, None, False)},
    "weather_scenarios.csv": {k: (low, high, False) for k, (low, high) in SCENARIO_LIMITS.items()},
}
INTEGER_COLUMNS = {"crops.csv": ["growth_duration_days"], "farms.csv": ["n_plots"]}
SAMPLE_FARM_KEYS = ["farm_name", "total_area_ha", "n_plots", "soil_type", "soil_ph", "soil_health_index",
                    "available_water_m3", "budget_usd", "seasons", "rainfall_mm", "data_note"]


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


def _check_range(name: str, frame: pd.DataFrame, column: str, rule: tuple) -> list[str]:
    low, high, exclusive = rule
    values = pd.to_numeric(frame[column], errors="coerce")
    errors = []
    for i in frame.index[values.isna()]:
        errors.append(f"{name} row {i + 2}: '{column}' must be a number (got {frame.at[i, column]!r})")
    if column in INTEGER_COLUMNS.get(name, []):
        for i in frame.index[values.notna() & (values % 1 != 0)]:
            errors.append(f"{name} row {i + 2}: '{column}' must be a whole number (got {values[i]})")
    bad = values.notna() & (((values <= low) if exclusive else (values < low)) if low is not None else False)
    if high is not None:
        bad |= values > high
    for i in frame.index[bad]:
        bound = f"{'>' if exclusive else '>='} {low}" + (f" and <= {high}" if high is not None else "")
        errors.append(f"{name} row {i + 2}: '{column}' must be {bound} (got {values[i]})")
    return errors


def validate_frame(name: str, frame: pd.DataFrame) -> None:
    """Check required columns, IDs, numeric ranges, seasons and the synthetic-data label."""
    missing = [c for c in REQUIRED_COLUMNS.get(name, []) if c not in frame.columns]
    if missing:
        raise DataError(f"{name} is missing columns: {', '.join(missing)}")
    if frame.empty:
        raise DataError(f"{name} has no rows")
    errors: list[str] = []
    if id_col := ID_COLUMNS.get(name):
        if frame[id_col].isna().any() or (frame[id_col].astype(str).str.strip() == "").any():
            errors.append(f"{name}: '{id_col}' has empty values")
        dupes = sorted(frame.loc[frame[id_col].duplicated(), id_col].astype(str))
        if dupes:
            errors.append(f"{name}: duplicate {id_col} values {dupes}")
    for column, rule in VALUE_RULES.get(name, {}).items():
        errors += _check_range(name, frame, column, rule)
    for column in ("allowed_seasons", "seasons"):
        if column in frame.columns:
            for i, value in frame[column].items():
                seasons = split_list(value)
                unknown = [s for s in seasons if s not in SEASONS]
                if not seasons or unknown:
                    errors.append(f"{name} row {i + 2}: '{column}' must list seasons from {list(SEASONS)} "
                                  f"(got {value!r})")
    if name == "crop_requirements.csv" and not errors:
        for i in frame.index[frame["min_ph"] >= frame["max_ph"]]:
            errors.append(f"{name} row {i + 2}: min_ph must be below max_ph")
    if "data_note" in frame.columns and not frame["data_note"].astype(str).str.contains("synthetic", case=False).all():
        errors.append(f"{name}: every row's data_note must mark the data as synthetic")
    if errors:
        raise DataError(f"{name} has invalid values:\n- " + "\n- ".join(errors))


@lru_cache(maxsize=None)
def _read_csv(data_dir: str, name: str) -> pd.DataFrame:
    path = Path(data_dir) / name
    if not path.exists():
        raise DataError(f"Dataset not found: {path}")
    try:
        frame = pd.read_csv(path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataError(f"Could not read {name}: {exc}") from exc
    validate_frame(name, frame)
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
    """Read ``sample_farm.json`` and check it has every field the farm form needs."""
    path = Path(data_dir) / "sample_farm.json"
    if not path.exists():
        raise DataError(f"Dataset not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"sample_farm.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DataError("sample_farm.json must contain a JSON object")
    missing = [k for k in SAMPLE_FARM_KEYS if k not in data]
    if missing:
        raise DataError(f"sample_farm.json is missing fields: {', '.join(missing)}")
    if "synthetic" not in str(data["data_note"]).lower():
        raise DataError("sample_farm.json data_note must mark the data as synthetic")
    return data


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
