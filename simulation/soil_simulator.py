"""Soil nitrogen dynamics and crop rotation effects."""
from __future__ import annotations

import numpy as np

FALLOW_NITROGEN_GAIN = 10.0
MINERALISATION_PER_OM_PCT = 1.0
LEGUME_FAMILY = "Fabaceae"


def nitrogen_factor(nitrogen: np.ndarray) -> np.ndarray:
    """Yield multiplier from the soil nitrogen index (50 = neutral)."""
    return np.clip(0.7 + 0.006 * nitrogen, 0.7, 1.1)


def update_nitrogen(
    nitrogen: np.ndarray, planted: np.ndarray, crop_effect: np.ndarray, organic_matter_pct: float
) -> np.ndarray:
    gain = np.where(planted, crop_effect, FALLOW_NITROGEN_GAIN)
    gain = gain + MINERALISATION_PER_OM_PCT * float(organic_matter_pct)
    return np.clip(nitrogen + gain, 0, 100)


def rotation_matrix(families, same_family_factor: float = 0.9, legume_bonus: float = 1.08) -> np.ndarray:
    """Yield multiplier for (previous crop, next crop); the last row/column is fallow."""
    families = np.asarray(families)
    n = len(families)
    matrix = np.ones((n + 1, n + 1))
    same = families[:, None] == families[None, :]
    after_legume = (families[:, None] == LEGUME_FAMILY) & (families[None, :] != LEGUME_FAMILY)
    matrix[:n, :n][same] = same_family_factor
    matrix[:n, :n][after_legume] = legume_bonus
    return matrix
