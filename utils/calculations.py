"""Unit conversions and small numeric helpers."""
from __future__ import annotations

from config import M3_PER_MM_HA

ACRE_TO_HA = 0.404686


def mm_to_m3(depth_mm: float, area_ha: float) -> float:
    """Volume of ``depth_mm`` of water over ``area_ha`` hectares, in cubic metres."""
    return max(0.0, depth_mm) * max(0.0, area_ha) * M3_PER_MM_HA


def acres_to_ha(acres: float) -> float:
    return acres * ACRE_TO_HA


def round_to(value: float, step: float = 0.05) -> float:
    """Round ``value`` to the nearest multiple of ``step``."""
    return round(round(value / step) * step, 4)
