"""Load the CSV/JSON inputs in ``data/`` into analysis-ready tables."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import DATA_DIR
from services.validation_service import (
    DataValidationError,
    validate_columns,
    validate_crops,
    validate_scenarios,
    validate_unique,
)

COST_COLUMNS = ["seed_per_ha", "fertilizer_per_ha", "pesticide_per_ha", "machinery_per_ha"]


class DataLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def _read(self, dataset: str) -> pd.DataFrame:
        path = self.data_dir / f"{dataset}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing data file: {path}")
        return validate_columns(pd.read_csv(path), dataset)

    def load_table(self, dataset: str) -> pd.DataFrame:
        return self._read(dataset)

    def load_crops(self) -> pd.DataFrame:
        """Crops joined with their requirements and input costs (``cost_per_ha`` = sum)."""
        crops = self._read("crops")
        validate_unique(crops, "crop", "crops")
        requirements = self._read("crop_requirements")
        costs = self._read("input_costs")
        merged = crops.merge(requirements, on="crop", how="left").merge(costs, on="crop", how="left")
        merged["cost_per_ha"] = merged[COST_COLUMNS].sum(axis=1, min_count=len(COST_COLUMNS))
        return validate_crops(merged).reset_index(drop=True)

    def load_farms(self) -> pd.DataFrame:
        """Farms joined with their soil profile."""
        farms = self._read("farms")
        validate_unique(farms, "farm_id", "farms")
        soils = self._read("soil_profiles")
        merged = farms.merge(soils, on="soil_profile_id", how="left")
        unknown = merged.loc[merged["soil_ph"].isna(), "farm_id"].tolist()
        if unknown:
            raise DataValidationError(f"Farms reference unknown soil profiles: {unknown}")
        return merged.reset_index(drop=True)

    def load_scenarios(self) -> pd.DataFrame:
        df = validate_scenarios(self._read("weather_scenarios"))
        df["probability"] = df["probability"] / df["probability"].sum()
        return df.reset_index(drop=True)

    def load_sample_farm(self) -> dict:
        path = self.data_dir / "sample_farm.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing config file: {path}")
        with path.open(encoding="utf-8") as fh:
            sample = json.load(fh)
        if not sample.get("seasons"):
            raise DataValidationError("sample_farm.json must define at least one season")
        return sample
