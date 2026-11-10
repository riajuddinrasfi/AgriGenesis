"""Schema and range checks for input data and farm profiles."""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = {
    "crops": {"crop", "family", "season_type", "growth_days", "yield_t_ha", "price_per_t",
              "nitrogen_effect"},
    "crop_requirements": {"crop", "water_mm", "ph_min", "ph_max", "temp_min", "temp_max",
                          "labor_days_ha", "drought_tolerance", "flood_tolerance",
                          "pest_sensitivity"},
    "input_costs": {"crop", "seed_per_ha", "fertilizer_per_ha", "pesticide_per_ha",
                    "machinery_per_ha"},
    "farms": {"farm_id", "name", "region", "soil_profile_id", "num_plots", "plot_area_ha",
              "avg_temp_wet", "avg_temp_dry", "rainfall_wet_mm", "rainfall_dry_mm",
              "irrigation_m3", "budget", "labor_days", "risk_tolerance"},
    "soil_profiles": {"soil_profile_id", "soil_type", "soil_ph", "soil_nitrogen",
                      "organic_matter_pct", "water_holding_mm"},
    "weather_scenarios": {"scenario", "description", "probability", "rainfall_factor",
                          "temp_shift", "price_factor", "cost_factor", "pest_pressure",
                          "yield_shock"},
}
FARM_FIELDS = (REQUIRED_COLUMNS["farms"] - {"soil_profile_id"}) | (
    REQUIRED_COLUMNS["soil_profiles"] - {"soil_profile_id"})
SEASON_TYPES = {"wet", "dry", "any"}


class DataValidationError(ValueError):
    pass


def validate_columns(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS[dataset] - set(df.columns)
    if missing:
        raise DataValidationError(f"{dataset} is missing columns: {sorted(missing)}")
    return df


def validate_unique(df: pd.DataFrame, column: str, dataset: str) -> None:
    dupes = df.loc[df[column].duplicated(), column].tolist()
    if dupes:
        raise DataValidationError(f"{dataset} has duplicate {column} values: {dupes}")


def validate_crops(crops: pd.DataFrame) -> pd.DataFrame:
    bad = ~crops["season_type"].isin(SEASON_TYPES)
    if bad.any():
        raise DataValidationError(f"Invalid season_type for: {crops.loc[bad, 'crop'].tolist()}")
    if crops.isna().any().any():
        missing = crops.loc[crops.isna().any(axis=1), "crop"].tolist()
        raise DataValidationError(f"Crops missing requirement or cost data: {missing}")
    for low, high in (("ph_min", "ph_max"), ("temp_min", "temp_max")):
        bad = crops[low] > crops[high]
        if bad.any():
            raise DataValidationError(f"{low} > {high} for: {crops.loc[bad, 'crop'].tolist()}")
    for col in ("drought_tolerance", "flood_tolerance", "pest_sensitivity"):
        if not crops[col].between(0, 1).all():
            raise DataValidationError(f"{col} must be between 0 and 1")
    return crops


def validate_scenarios(scenarios: pd.DataFrame) -> pd.DataFrame:
    if (scenarios["probability"] < 0).any() or scenarios["probability"].sum() <= 0:
        raise DataValidationError("Scenario probabilities must be non-negative and sum to > 0")
    return scenarios


def validate_farm(farm: dict) -> list[str]:
    """Problems that make a farm profile unusable or suspicious."""
    missing = FARM_FIELDS - set(farm)
    if missing:
        return [f"Farm profile is missing fields: {sorted(missing)}"]
    warnings = []
    if farm["num_plots"] < 1 or farm["plot_area_ha"] <= 0:
        warnings.append("Farm must have at least one plot with positive area.")
    if not 3.5 <= farm["soil_ph"] <= 9.5:
        warnings.append(f"Soil pH {farm['soil_ph']} looks unrealistic.")
    if not 0 <= farm["soil_nitrogen"] <= 100:
        warnings.append("Soil nitrogen index should be between 0 and 100.")
    if not 0 <= farm["risk_tolerance"] <= 1:
        warnings.append("risk_tolerance should be between 0 and 1.")
    for key in ("budget", "labor_days", "irrigation_m3"):
        if farm[key] <= 0:
            warnings.append(f"{key} is zero or negative; most crops will be infeasible.")
    return warnings
