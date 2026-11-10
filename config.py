"""Project paths and environment settings (reads ``.env`` if present)."""
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
SAMPLE_FARM_FILE = DATA_DIR / "sample_farm.json"

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    data_dir: Path = DATA_DIR
    output_dir: Path = OUTPUT_DIR

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", cls.gemini_model).strip() or cls.gemini_model,
            data_dir=Path(os.getenv("AGRIGENESIS_DATA_DIR", DATA_DIR)),
            output_dir=Path(os.getenv("AGRIGENESIS_OUTPUT_DIR", OUTPUT_DIR)),
        )


def get_settings() -> Settings:
    return Settings.from_env()
