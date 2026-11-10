"""Water balance: effective rainfall, irrigation, adequacy and waterlogging."""
from __future__ import annotations

from config import MIN_WATER_FACTOR, WATERLOGGING_THRESHOLD
from utils.normalization import clip, safe_ratio


def effective_rainfall_mm(rainfall_mm: float, effective_fraction: float) -> float:
    """Share of rainfall the soil retains for the crop."""
    return max(0.0, rainfall_mm) * clip(effective_fraction)


def irrigation_need_mm(requirement_mm: float, effective_rain_mm: float) -> float:
    return max(0.0, requirement_mm - effective_rain_mm)


def irrigation_applied_mm(need_mm: float, water_level: float, supply_scale: float = 1.0) -> float:
    """Irrigation actually applied: the chosen share of the need, scaled by supply limits."""
    return need_mm * clip(water_level) * clip(supply_scale)


def water_factor(supply_mm: float, requirement_mm: float, drought_tolerance: float,
                 waterlogging_tolerance: float, drainage_factor: float) -> tuple[float, float, bool]:
    """Yield factor from water supply.

    Returns ``(factor, adequacy_ratio, waterlogged)``. Adequacy above 1 gives no extra yield
    (capped); above ``WATERLOGGING_THRESHOLD`` a penalty applies that grows with the excess,
    the crop's waterlogging sensitivity and poor soil drainage.
    """
    adequacy = safe_ratio(supply_mm, requirement_mm, default=1.0)
    if adequacy < 1.0:
        factor = 1.0 - (1.0 - adequacy) * (1.0 - 0.5 * clip(drought_tolerance))
    else:
        factor = 1.0
    waterlogged = adequacy > WATERLOGGING_THRESHOLD
    if waterlogged:
        excess = adequacy - WATERLOGGING_THRESHOLD
        factor -= excess * (1.0 - clip(waterlogging_tolerance)) * (1.0 - clip(drainage_factor))
    return clip(factor, MIN_WATER_FACTOR, 1.0), adequacy, waterlogged


def supply_scale(demand_m3: float, available_m3: float) -> float:
    """Share of irrigation demand that can be met from the available water."""
    if demand_m3 <= 1e-9:
        return 1.0
    return clip(available_m3 / demand_m3)
