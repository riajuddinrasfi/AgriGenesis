"""Validation of farm input, optimisation weights and sanitisation of AI-parsed values."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from config import DEFAULT_WEIGHTS, SEASONS
from utils.helpers import split_list

NUMERIC_RULES: dict[str, tuple[float, float]] = {
    "total_area_ha": (0.1, 10_000.0),
    "n_plots": (1, 20),
    "soil_ph": (3.0, 10.0),
    "soil_health_index": (0.0, 100.0),
    "available_water_m3": (0.0, 10_000_000.0),
    "budget_usd": (1.0, 100_000_000.0),
}
RAINFALL_RANGE = (0.0, 5000.0)


class FarmValidationError(ValueError):
    """Raised with the full list of problems found in a farm input."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class FarmProfile:
    farm_name: str
    total_area_ha: float
    n_plots: int
    soil_type: str
    soil_ph: float
    soil_health_index: float
    available_water_m3: float
    budget_usd: float
    seasons: list[str]
    rainfall_mm: dict[str, float]
    preferred_crops: list[str] = field(default_factory=list)
    excluded_crops: list[str] = field(default_factory=list)

    @property
    def plot_area_ha(self) -> float:
        return self.total_area_ha / self.n_plots

    def to_dict(self) -> dict:
        data = asdict(self)
        data["plot_area_ha"] = self.plot_area_ha
        return data


def _number(value, name: str, errors: list[str]) -> float | None:
    """Parse a number; record an error for missing, non-numeric or NaN values."""
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{name} is required")
        return None
    try:
        number = float(str(value).replace(",", "")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        errors.append(f"{name} must be a number (got {value!r})")
        return None
    if math.isnan(number) or math.isinf(number):
        errors.append(f"{name} is required")
        return None
    return number


def validate_farm_input(data: dict, crop_ids: list[str], soil_types: list[str]) -> FarmProfile:
    """Validate raw farm input and return a normalised :class:`FarmProfile`.

    Every missing or invalid field is reported; nothing is silently defaulted.
    """
    errors: list[str] = []
    name = str(data.get("farm_name") or "").strip()
    if not name:
        errors.append("farm_name is required")

    numbers: dict[str, float] = {}
    for key, (low, high) in NUMERIC_RULES.items():
        value = _number(data.get(key), key, errors)
        if value is None:
            continue
        if not low <= value <= high:
            errors.append(f"{key} must be between {low:g} and {high:g} (got {value:g})")
        numbers[key] = value
    if "n_plots" in numbers and numbers["n_plots"] != int(numbers["n_plots"]):
        errors.append("n_plots must be a whole number")

    soil = str(data.get("soil_type") or "").strip()
    if soil not in soil_types:
        errors.append(f"soil_type must be one of {', '.join(soil_types)} (got {soil or 'nothing'})")

    seasons = split_list(data.get("seasons"))
    unknown = [s for s in seasons if s not in SEASONS]
    if not seasons:
        errors.append("At least one season must be selected")
    if unknown:
        errors.append(f"Unknown seasons: {', '.join(unknown)}")
    seasons = [s for s in SEASONS if s in seasons]

    raw_rain = data.get("rainfall_mm") or {}
    rainfall: dict[str, float] = {}
    for season in seasons:
        value = _number(raw_rain.get(season), f"rainfall_mm.{season}", errors)
        if value is None:
            continue
        if not RAINFALL_RANGE[0] <= value <= RAINFALL_RANGE[1]:
            errors.append(f"rainfall_mm.{season} must be between 0 and {RAINFALL_RANGE[1]:g}")
        rainfall[season] = value

    preferred = [c.upper() for c in split_list(data.get("preferred_crops"))]
    excluded = [c.upper() for c in split_list(data.get("excluded_crops"))]
    for label, items in (("preferred_crops", preferred), ("excluded_crops", excluded)):
        bad = [c for c in items if c not in crop_ids]
        if bad:
            errors.append(f"{label} contains unknown crops: {', '.join(bad)}")
    overlap = set(preferred) & set(excluded)
    if overlap:
        errors.append(f"Crops cannot be both preferred and excluded: {', '.join(sorted(overlap))}")

    if errors:
        raise FarmValidationError(errors)
    return FarmProfile(
        farm_name=name,
        total_area_ha=numbers["total_area_ha"],
        n_plots=int(numbers["n_plots"]),
        soil_type=soil,
        soil_ph=numbers["soil_ph"],
        soil_health_index=numbers["soil_health_index"],
        available_water_m3=numbers["available_water_m3"],
        budget_usd=numbers["budget_usd"],
        seasons=seasons,
        rainfall_mm=rainfall,
        preferred_crops=preferred,
        excluded_crops=excluded,
    )


def validate_weights(weights: dict[str, float]) -> dict[str, float]:
    """Check the five fitness weights and rescale them so they sum exactly to 1."""
    missing = [k for k in DEFAULT_WEIGHTS if k not in weights]
    if missing:
        raise ValueError(f"Missing fitness weights: {', '.join(missing)}")
    values = {}
    for key in DEFAULT_WEIGHTS:
        value = float(weights[key])
        if math.isnan(value) or value < 0:
            raise ValueError(f"Weight '{key}' must be a non-negative number")
        values[key] = value
    total = sum(values.values())
    if total <= 0:
        raise ValueError("At least one fitness weight must be greater than zero")
    return {k: v / total for k, v in values.items()}


ALLOWED_PARSED_FIELDS = {
    "farm_name": str, "total_area_ha": float, "n_plots": int, "soil_type": str, "soil_ph": float,
    "soil_health_index": float, "available_water_m3": float, "budget_usd": float,
    "seasons": list, "rainfall_mm": dict, "preferred_crops": list, "excluded_crops": list,
}


def sanitize_parsed_farm(raw: dict, crop_ids: list[str], soil_types: list[str]) -> tuple[dict, list[str]]:
    """Keep only known fields with plausible types from an AI/regex parse.

    Returns the cleaned dict and a list of notes about dropped values.
    """
    clean: dict = {}
    notes: list[str] = []
    if not isinstance(raw, dict):
        return clean, ["Parser did not return an object"]
    for key, value in raw.items():
        if key not in ALLOWED_PARSED_FIELDS or value is None:
            continue
        kind = ALLOWED_PARSED_FIELDS[key]
        try:
            if kind is float:
                number = float(value)
                low, high = NUMERIC_RULES.get(key, (-math.inf, math.inf))
                if math.isnan(number) or not low <= number <= high:
                    notes.append(f"Ignored out-of-range {key}={value}")
                    continue
                clean[key] = number
            elif kind is int:
                number = int(float(value))
                low, high = NUMERIC_RULES[key]
                if not low <= number <= high:
                    notes.append(f"Ignored out-of-range {key}={value}")
                    continue
                clean[key] = number
            elif kind is str:
                text = str(value).strip()[:80]
                if key == "soil_type":
                    text = text.lower().replace(" ", "_")
                    if text not in soil_types:
                        notes.append(f"Ignored unknown soil type '{value}'")
                        continue
                if text:
                    clean[key] = text
            elif key == "seasons":
                seasons = [s.lower() for s in split_list(value) if s.lower() in SEASONS]
                if seasons:
                    clean[key] = seasons
            elif key in ("preferred_crops", "excluded_crops"):
                crops = [c.upper() for c in split_list(value) if c.upper() in crop_ids]
                clean[key] = crops
            elif key == "rainfall_mm" and isinstance(value, dict):
                rain = {}
                for season, mm in value.items():
                    if season in SEASONS and mm is not None:
                        mm = float(mm)
                        if RAINFALL_RANGE[0] <= mm <= RAINFALL_RANGE[1]:
                            rain[season] = mm
                if rain:
                    clean[key] = rain
        except (TypeError, ValueError):
            notes.append(f"Ignored invalid {key}={value!r}")
    return clean, notes
