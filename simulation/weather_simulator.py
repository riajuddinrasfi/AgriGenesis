"""Season weather under a batch of scenarios."""
from __future__ import annotations

import numpy as np


def base_conditions(farm: dict, season_type: str) -> tuple[float, float]:
    """Normal-year average temperature (C) and rainfall (mm) for a season type."""
    return float(farm[f"avg_temp_{season_type}"]), float(farm[f"rainfall_{season_type}_mm"])


def season_weather(farm: dict, season_type: str, params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Temperature and rainfall per scenario, shaped ``(n_scenarios, 1)``."""
    temp, rain = base_conditions(farm, season_type)
    return temp + params["temp_shift"], rain * params["rainfall_factor"]
