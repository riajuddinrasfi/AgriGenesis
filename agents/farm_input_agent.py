"""Loads and validates the farm being planned (CSV profiles or the sample farm)."""
from __future__ import annotations

import pandas as pd

from services.data_loader import DataLoader
from services.validation_service import validate_farm


class FarmInputAgent:
    def __init__(self, loader: DataLoader):
        self.config = loader.load_sample_farm()
        farms = loader.load_farms()
        sample = self.config.get("farm")
        if sample and sample["farm_id"] not in set(farms["farm_id"]):
            farms = pd.concat([pd.DataFrame([sample]), farms], ignore_index=True)
        self.farms = farms

    def list_farms(self) -> dict[str, str]:
        return dict(zip(self.farms["farm_id"], self.farms["name"]))

    def get_farm(self, farm_id: str) -> dict:
        match = self.farms[self.farms["farm_id"] == farm_id]
        if match.empty:
            raise KeyError(f"Unknown farm_id: {farm_id}")
        return {k: v.item() if hasattr(v, "item") else v for k, v in match.iloc[0].to_dict().items()}

    def prepare(self, farm_id: str, overrides: dict | None = None) -> tuple[dict, list[str]]:
        """The farm with user overrides applied, plus any data warnings."""
        farm = {**self.get_farm(farm_id), **(overrides or {})}
        return farm, validate_farm(farm)

    @staticmethod
    def summarize(farm: dict) -> dict:
        return {
            "Farm": farm["name"],
            "Region": farm["region"],
            "Plots": int(farm["num_plots"]),
            "Total area (ha)": round(farm["num_plots"] * farm["plot_area_ha"], 2),
            "Soil": f"{farm['soil_type']}, pH {farm['soil_ph']}, N index {farm['soil_nitrogen']}, "
                    f"OM {farm['organic_matter_pct']}%",
            "Budget / season": f"${farm['budget']:,.0f}",
            "Labour / season": f"{farm['labor_days']:,.0f} days",
            "Irrigation / season": f"{farm['irrigation_m3']:,.0f} m³",
            "Risk tolerance": farm["risk_tolerance"],
        }
