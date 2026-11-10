"""Soil suitability, nutrient response and soil-health change."""
from __future__ import annotations

from config import MARGINAL_PH_FACTOR, MAX_FERTILIZER_RATIO, PH_MARGIN, SAME_FAMILY_SOIL_PENALTY
from utils.normalization import clip, safe_ratio


def ph_factor(soil_ph: float, min_ph: float, max_ph: float) -> float:
    """1.0 inside the crop pH range, reduced when marginal, 0 when far outside."""
    gap = max(min_ph - soil_ph, 0.0, soil_ph - max_ph)
    if gap == 0:
        return 1.0
    return MARGINAL_PH_FACTOR if gap <= PH_MARGIN else 0.0


def soil_factor(fertility_factor: float, soil_health_index: float, ph_fac: float) -> float:
    """Yield factor from soil type fertility, current soil health (0-100) and pH."""
    return fertility_factor * (0.6 + 0.4 * clip(soil_health_index / 100.0)) * ph_fac


def fertilizer_applied_kg_per_ha(requirement_kg_per_ha: float, fertilizer_level: float) -> float:
    return requirement_kg_per_ha * MAX_FERTILIZER_RATIO * clip(fertilizer_level)


def fertilizer_ratio(applied_kg_per_ha: float, requirement_kg_per_ha: float) -> float:
    return safe_ratio(applied_kg_per_ha, requirement_kg_per_ha, default=1.0)


def nutrient_factor(ratio: float) -> float:
    """Yield response to fertilizer: 0.55 with none, 1.0 at the requirement, capped above it."""
    return 0.55 + 0.45 * clip(ratio)


def soil_health_delta(crop_effect: float, ratio: float, repeats_family: bool) -> float:
    """Change in soil-health points for one season.

    Crop effect (e.g. legumes positive), minus nutrient mining when under-fertilised,
    minus damage from excess fertilizer, minus a penalty for repeating a crop family.
    """
    mining = 2.0 * clip((0.6 - ratio) / 0.6)
    excess = 4.0 * max(0.0, ratio - 1.0)
    rotation = SAME_FAMILY_SOIL_PENALTY if repeats_family else 0.0
    return crop_effect - mining - excess - rotation


def update_soil_health(current: float, delta: float) -> float:
    return clip(current + delta, 0.0, 100.0)
