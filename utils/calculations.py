"""Unit conversions and small numeric helpers."""
from __future__ import annotations

from config import M3_PER_MM_HA

ACRE_TO_HA = 0.404686


def mm_to_m3(depth_mm: float, area_ha: float) -> float:
    """Volume of ``depth_mm`` of water over ``area_ha`` hectares, in cubic metres."""
    return max(0.0, depth_mm) * max(0.0, area_ha) * M3_PER_MM_HA


def require_range(name: str, value: float, low: float | None = 0.0, high: float | None = None,
                  exclusive_low: bool = False) -> float:
    """Return ``value`` as a float, or raise ``ValueError`` naming the input if it is out of range."""
    number = float(value)
    if number != number:
        raise ValueError(f"{name} must be a number (got NaN)")
    too_low = low is not None and (number <= low if exclusive_low else number < low)
    if too_low or (high is not None and number > high):
        bound = f"{'>' if exclusive_low else '>='} {low}" if low is not None else ""
        bound += (" and " if bound and high is not None else "") + (f"<= {high}" if high is not None else "")
        raise ValueError(f"{name} must be {bound} (got {number})")
    return number


def acres_to_ha(acres: float) -> float:
    return acres * ACRE_TO_HA


def round_to(value: float, step: float = 0.05) -> float:
    """Round ``value`` to the nearest multiple of ``step``."""
    return round(round(value / step) * step, 4)
