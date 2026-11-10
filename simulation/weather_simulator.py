"""Scenario (weather + market) definitions and weather-related yield factors."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from config import PLANTING_WINDOWS, SCENARIO_LIMITS, SEASONS

# Allowed ranges for every scenario parameter (also used to sanitise AI output).


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    scenario_name: str
    rainfall_multiplier: float = 1.0
    yield_stress_factor: float = 1.0
    input_cost_multiplier: float = 1.0
    market_price_multiplier: float = 1.0
    water_availability_multiplier: float = 1.0
    description: str = ""
    custom: bool = False

    def __post_init__(self):
        for name, (low, high) in SCENARIO_LIMITS.items():
            value = float(getattr(self, name))
            if not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high} (got {value})")

    @classmethod
    def from_row(cls, row: dict) -> "Scenario":
        return cls(
            scenario_id=str(row["scenario_id"]),
            scenario_name=str(row["scenario_name"]),
            **{name: float(row[name]) for name in SCENARIO_LIMITS},
            description=str(row.get("description", "") or ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def seasonal_rainfall_mm(base_rainfall_mm: float, scenario: Scenario) -> float:
    return max(0.0, base_rainfall_mm) * scenario.rainfall_multiplier


def planting_window(window_id: int) -> dict:
    for window in PLANTING_WINDOWS:
        if window["id"] == window_id:
            return window
    raise ValueError(f"Unknown planting window {window_id}")


def window_fits(window_id: int, growth_days: float, season_id: str) -> bool:
    """True when a crop planted in this window matures before the season ends."""
    return planting_window(window_id)["offset_days"] + growth_days <= SEASONS[season_id]["duration_days"]


def valid_windows(growth_days: float, season_id: str) -> list[int]:
    return [w["id"] for w in PLANTING_WINDOWS if window_fits(w["id"], growth_days, season_id)]


def weather_factor(scenario: Scenario, window_id: int) -> float:
    """Scenario heat/stress factor times the planting-window timing factor."""
    return scenario.yield_stress_factor * planting_window(window_id)["timing_factor"]
