"""Revenue and production cost."""
from __future__ import annotations

import numpy as np


def revenue(yield_t: np.ndarray, price_per_t: np.ndarray, price_factor: np.ndarray) -> np.ndarray:
    return yield_t * price_per_t * price_factor


def production_cost(
    cost_per_ha: np.ndarray,
    area_ha: float,
    cost_factor: np.ndarray,
    irrigation_m3: np.ndarray,
    irrigation_cost_per_m3: float,
    mask: np.ndarray,
) -> np.ndarray:
    return (cost_per_ha * area_ha * cost_factor + irrigation_m3 * irrigation_cost_per_m3) * mask
