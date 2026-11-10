"""Safe normalisation helpers used by the fitness function."""
from __future__ import annotations

import math


def clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp ``value`` into ``[low, high]``; NaN becomes ``low``."""
    if value is None or math.isnan(value):
        return low
    return max(low, min(high, value))


def min_max(value: float, low: float, high: float) -> float:
    """Scale ``value`` from ``[low, high]`` to ``[0, 1]``; returns 0 when ``high <= low``."""
    span = high - low
    if span <= 1e-12:
        return 0.0
    return clip((value - low) / span)


def safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    """``numerator / denominator`` or ``default`` when the denominator is ~0."""
    if abs(denominator) <= 1e-12:
        return default
    return numerator / denominator


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Return non-negative weights rescaled to sum to 1 (raises if all are zero)."""
    cleaned = {k: max(0.0, float(v)) for k, v in weights.items()}
    total = sum(cleaned.values())
    if total <= 1e-12:
        raise ValueError("At least one fitness weight must be greater than zero")
    return {k: v / total for k, v in cleaned.items()}
