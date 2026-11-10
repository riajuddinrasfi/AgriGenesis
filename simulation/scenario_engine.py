"""Weather and market scenarios: selection, parameter arrays and sampling."""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils.normalization import normalize_probabilities

SCENARIO_FIELDS = (
    "rainfall_factor", "temp_shift", "price_factor", "cost_factor", "pest_pressure", "yield_shock",
)
NEUTRAL_SCENARIO = {
    "scenario": "Neutral", "rainfall_factor": 1.0, "temp_shift": 0.0, "price_factor": 1.0,
    "cost_factor": 1.0, "pest_pressure": 0.0, "yield_shock": 1.0,
}


def select_scenarios(scenarios: pd.DataFrame, names: list[str] | None = None) -> pd.DataFrame:
    """Chosen scenarios with probabilities renormalised to sum to 1."""
    df = scenarios if not names else scenarios[scenarios["scenario"].isin(names)]
    if df.empty:
        raise ValueError("Select at least one scenario")
    df = df.copy().reset_index(drop=True)
    df["probability"] = normalize_probabilities(df["probability"])
    return df


def scenario_params(scenarios: pd.DataFrame | list[dict] | dict | None) -> dict[str, np.ndarray]:
    """Scenario fields as arrays shaped ``(n_scenarios, 1)`` for broadcasting over plots."""
    if scenarios is None:
        scenarios = NEUTRAL_SCENARIO
    if isinstance(scenarios, dict):
        scenarios = [scenarios]
    df = pd.DataFrame(scenarios)
    return {f: df[f].to_numpy(dtype=float)[:, None] for f in SCENARIO_FIELDS}


def sample_scenarios(scenarios: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    picks = rng.choice(len(scenarios), size=n, p=normalize_probabilities(scenarios["probability"]))
    return scenarios.iloc[picks].reset_index(drop=True)
