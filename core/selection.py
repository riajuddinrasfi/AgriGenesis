"""Parent selection operators."""
from __future__ import annotations

import numpy as np


def tournament(scores: np.ndarray, size: int, rng: np.random.Generator) -> int:
    """Index of the fittest of ``size`` randomly drawn individuals."""
    picks = rng.choice(len(scores), size=size, replace=False)
    return int(picks[np.argmax(scores[picks])])


def roulette(scores: np.ndarray, rng: np.random.Generator) -> int:
    """Fitness-proportional pick; scores are shifted so the worst has a small positive weight."""
    shifted = scores - scores.min()
    weights = shifted + max(shifted.max() * 1e-3, 1e-9)
    return int(rng.choice(len(scores), p=weights / weights.sum()))


def elite_indices(scores: np.ndarray, count: int) -> np.ndarray:
    return np.argsort(scores)[::-1][:count]
