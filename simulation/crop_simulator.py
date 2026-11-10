"""Crop yield response to soil pH, temperature and pests."""
from __future__ import annotations

import numpy as np

MIN_FACTOR = 0.3


def ph_factor(soil_ph: float, ph_min: np.ndarray, ph_max: np.ndarray) -> np.ndarray:
    gap = np.clip(ph_min - soil_ph, 0, None) + np.clip(soil_ph - ph_max, 0, None)
    return np.clip(1.0 - 0.4 * gap, MIN_FACTOR, 1.0)


def temperature_factor(temp: np.ndarray, temp_min: np.ndarray, temp_max: np.ndarray) -> np.ndarray:
    gap = np.clip(temp_min - temp, 0, None) + np.clip(temp - temp_max, 0, None)
    return np.clip(1 - 0.08 * gap, MIN_FACTOR, 1)


def pest_factor(pest_pressure: np.ndarray, sensitivity: np.ndarray) -> np.ndarray:
    return 1 - 0.6 * pest_pressure * sensitivity


def crop_yield(base_yield_t_ha: np.ndarray, area_ha: float, *factors: np.ndarray) -> np.ndarray:
    """Tonnes harvested per plot: base yield × area × every yield factor."""
    result = base_yield_t_ha * area_ha
    for factor in factors:
        result = result * factor
    return result
