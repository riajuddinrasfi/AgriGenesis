"""Scaling and normalisation helpers."""
from __future__ import annotations

import numpy as np


def normalize_probabilities(weights) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    if (w < 0).any() or w.sum() <= 0:
        raise ValueError("Weights must be non-negative and sum to more than zero")
    return w / w.sum()


def min_max(values) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    span = v.max() - v.min() if v.size else 0
    return np.zeros_like(v) if span == 0 else (v - v.min()) / span


def clip01(values) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 0.0, 1.0)
