"""Central configuration: paths, seasons, GA defaults, fitness weights and Gemini settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
STRATEGY_DIR = OUTPUT_DIR / "strategies"
REPORT_DIR = OUTPUT_DIR / "reports"
CHART_DIR = OUTPUT_DIR / "charts"

load_dotenv(BASE_DIR / ".env")

FALLOW = "FALLOW"

SYNTHETIC_DATA_NOTICE = (
    "All crop, soil, cost, price and weather figures are synthetic sample data created for "
    "this demo. They are not verified agricultural research or real market prices."
)

# Season id -> display name and length of the planting season in days.
SEASONS: dict[str, dict] = {
    "monsoon": {"name": "Monsoon (Kharif)", "duration_days": 150},
    "winter": {"name": "Winter (Rabi)", "duration_days": 140},
    "summer": {"name": "Summer (Zaid)", "duration_days": 110},
}

# Planting windows: days after season start, and a timing factor applied to yield.
PLANTING_WINDOWS: list[dict] = [
    {"id": 0, "name": "Early", "offset_days": 0, "timing_factor": 0.96},
    {"id": 1, "name": "On-time", "offset_days": 15, "timing_factor": 1.00},
    {"id": 2, "name": "Late", "offset_days": 30, "timing_factor": 0.88},
]

DEFAULT_WEIGHTS: dict[str, float] = {
    "profit": 0.35,
    "yield": 0.20,
    "water": 0.15,
    "soil": 0.15,
    "resilience": 0.15,
}

# Simulation constants (transparent, synthetic assumptions).
MAX_FERTILIZER_RATIO = 1.25      # fertilizer_level 1.0 applies 125% of the crop requirement
WATERLOGGING_THRESHOLD = 1.10    # water supply above 110% of requirement starts waterlogging
MIN_WATER_FACTOR = 0.30
PH_MARGIN = 0.5                  # pH within this distance outside the range is "marginal"
MARGINAL_PH_FACTOR = 0.85
SAME_FAMILY_SOIL_PENALTY = 1.5   # soil health points lost when a family follows itself
FALLOW_SOIL_EFFECT = 1.0
M3_PER_MM_HA = 10.0              # 1 mm of water over 1 ha = 10 m3


@dataclass(frozen=True)
class GAConfig:
    population_size: int = 50
    generations: int = 20
    seed: int = 42
    tournament_size: int = 3
    crossover_probability: float = 0.80
    mutation_probability: float = 0.10
    elitism: int = 2
    top_k: int = 5

    def validate(self) -> None:
        if self.population_size < 4:
            raise ValueError("population_size must be at least 4")
        if self.generations < 1:
            raise ValueError("generations must be at least 1")
        if not 0.0 <= self.crossover_probability <= 1.0:
            raise ValueError("crossover_probability must be in [0, 1]")
        if not 0.0 <= self.mutation_probability <= 1.0:
            raise ValueError("mutation_probability must be in [0, 1]")
        if not 2 <= self.tournament_size <= self.population_size:
            raise ValueError("tournament_size must be between 2 and population_size")
        if not 0 <= self.elitism < self.population_size:
            raise ValueError("elitism must be between 0 and population_size - 1")


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key) and not self.api_key.startswith("your-")


def get_gemini_settings() -> GeminiSettings:
    """Read Gemini settings from the environment (``.env`` is loaded on import)."""
    return GeminiSettings(
        api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.5-flash",
    )
