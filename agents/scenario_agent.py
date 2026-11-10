"""Selects the weather and market scenarios a plan is stress-tested against."""
from __future__ import annotations

import pandas as pd

from services.data_loader import DataLoader
from simulation.scenario_engine import select_scenarios


class ScenarioAgent:
    def __init__(self, loader: DataLoader):
        self.scenarios = loader.load_scenarios()

    def names(self) -> list[str]:
        return self.scenarios["scenario"].tolist()

    def select(self, names: list[str] | None = None) -> pd.DataFrame:
        return select_scenarios(self.scenarios, names)

    def custom(self, name: str = "Custom", **factors) -> pd.DataFrame:
        """A single user-defined scenario, e.g. ``custom(rainfall_factor=0.6, price_factor=0.9)``."""
        row = {"scenario": name, "description": "User-defined scenario", "probability": 1.0,
               "rainfall_factor": 1.0, "temp_shift": 0.0, "price_factor": 1.0, "cost_factor": 1.0,
               "pest_pressure": 0.0, "yield_shock": 1.0, **factors}
        return pd.DataFrame([row])
