"""Irrigation allocation and water-related yield effects."""
from __future__ import annotations

import numpy as np

STORED_MOISTURE_SHARE = 0.3
FLOOD_THRESHOLD = 1.2


def available_soil_water(water_holding_mm: float) -> float:
    """Share of the soil's water-holding capacity a crop can draw on each season."""
    return STORED_MOISTURE_SHARE * float(water_holding_mm)


def allocate_irrigation(
    need_mm: np.ndarray, natural_mm: np.ndarray, mask: np.ndarray, area_ha: float, capacity_m3: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Share the season's irrigation capacity pro rata across plots in deficit.

    Returns ``(supplied_mm, satisfaction, irrigation_m3)``, each ``(n_scenarios, n_plots)``.
    1 mm over 1 ha is 10 m³.
    """
    deficit = np.clip(need_mm - natural_mm, 0, None) * mask
    demand = deficit.sum(axis=1, keepdims=True) * area_ha * 10.0
    ratio = np.where(demand > capacity_m3, capacity_m3 / np.maximum(demand, 1e-9), 1.0)
    supplied = deficit * ratio
    satisfaction = np.clip((np.minimum(natural_mm, need_mm) + supplied) / need_mm, 0, 1)
    return supplied, satisfaction, supplied * area_ha * 10.0


def water_stress_factor(satisfaction: np.ndarray, drought_tolerance: np.ndarray) -> np.ndarray:
    return 1 - (1 - satisfaction) * (1 - drought_tolerance)


def flood_factor(rainfall_factor: np.ndarray, flood_tolerance: np.ndarray) -> np.ndarray:
    excess = np.clip(rainfall_factor - FLOOD_THRESHOLD, 0, None)
    return np.clip(1 - excess * (1 - flood_tolerance), 0.3, 1)
