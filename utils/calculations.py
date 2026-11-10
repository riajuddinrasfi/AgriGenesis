"""Statistical helpers for profit distributions."""
from __future__ import annotations

import numpy as np

from utils.normalization import normalize_probabilities


def weighted_mean_std(values, weights) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    w = normalize_probabilities(weights)
    mean = float(w @ values)
    return mean, float(np.sqrt(w @ (values - mean) ** 2))


def risk_metrics(profits, tail: float = 0.05) -> dict:
    """Mean, tail percentiles, expected shortfall (CVaR) and loss probability."""
    profits = np.asarray(profits, dtype=float)
    if profits.size == 0:
        raise ValueError("profits must not be empty")
    cutoff = float(np.percentile(profits, tail * 100))
    return {
        "mean": float(profits.mean()),
        "std": float(profits.std()),
        "p5": cutoff,
        "p95": float(np.percentile(profits, 100 - tail * 100)),
        "cvar5": float(profits[profits <= cutoff].mean()),
        "loss_probability": float((profits < 0).mean()),
    }


def gross_margin(yield_t_ha: float, price_per_t: float, cost_per_ha: float) -> float:
    return yield_t_ha * price_per_t - cost_per_ha
