"""Farm Input Agent: turns form input or natural-language text into a validated FarmProfile."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import SEASONS
from services.data_loader import Datasets
from services.gemini_service import GeminiService
from services.validation_service import (FarmProfile, FarmValidationError, sanitize_parsed_farm,
                                        validate_farm_input)
from utils.calculations import acres_to_ha

REQUIRED_FIELDS = ["farm_name", "total_area_ha", "n_plots", "soil_type", "soil_ph", "soil_health_index",
                   "available_water_m3", "budget_usd", "seasons", "rainfall_mm"]


@dataclass
class ParseResult:
    values: dict
    missing: list[str]
    notes: list[str] = field(default_factory=list)
    source: str = "rules"
    profile: FarmProfile | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.profile is not None

    def to_json(self) -> dict:
        """Structured farm profile JSON (the validated profile when complete, else the partial values)."""
        return {"source": self.source, "complete": self.complete,
                "farm_profile": self.profile.to_dict() if self.profile else self.values,
                "missing_fields": self.missing, "errors": self.errors, "notes": self.notes}


def _num(text: str) -> float:
    return float(text.replace(",", ""))


class FarmInputAgent:
    def __init__(self, datasets: Datasets, gemini: GeminiService | None = None):
        self.datasets = datasets
        self.gemini = gemini or GeminiService()

    def from_form(self, data: dict) -> FarmProfile:
        """Validate structured input; raises ``FarmValidationError`` listing every problem."""
        return validate_farm_input(data, self.datasets.crop_ids, self.datasets.soil_types)

    def rule_based_parse(self, text: str) -> dict:
        """Deterministic keyword/regex parser used when Gemini is unavailable."""
        t = text.lower()
        out: dict = {}
        if m := re.search(r"(\d[\d,]*\.?\d*)\s*(ha|hectares?)\b", t):
            out["total_area_ha"] = _num(m.group(1))
        elif m := re.search(r"(\d[\d,]*\.?\d*)\s*acres?\b", t):
            out["total_area_ha"] = round(acres_to_ha(_num(m.group(1))), 3)
        if m := re.search(r"(\d+)\s*(plots?|fields?|parcels?)\b", t):
            out["n_plots"] = int(m.group(1))
        if m := re.search(r"\bph\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?)", t):
            out["soil_ph"] = float(m.group(1))
        if m := re.search(r"soil health\D{0,20}(\d+(?:\.\d+)?)", t):
            out["soil_health_index"] = float(m.group(1))
        if m := re.search(r"(\d[\d,]*\.?\d*)\s*(m3|m³|cubic met(?:er|re)s?)", t):
            out["available_water_m3"] = _num(m.group(1))
        if m := re.search(r"budget\D{0,25}\$?\s*(\d[\d,]*\.?\d*)\s*(k\b)?", t) or \
                re.search(r"\$\s*(\d[\d,]*\.?\d*)\s*(k\b)?", t):
            out["budget_usd"] = _num(m.group(1)) * (1000 if m.group(2) else 1)
        for soil in sorted(self.datasets.soil_types, key=len, reverse=True):
            if soil.replace("_", " ") in t or soil in t:
                out["soil_type"] = soil
                break
        seasons = [s for s in SEASONS if s in t or SEASONS[s]["name"].split("(")[1].rstrip(")").lower() in t]
        if seasons:
            out["seasons"] = seasons
        rain = {}
        for season in SEASONS:
            if m := re.search(rf"{season}\D{{0,30}}(\d[\d,]*)\s*mm", t):
                rain[season] = _num(m.group(1))
        if rain:
            out["rainfall_mm"] = rain
        names = {r["crop_name"].lower(): r["crop_id"] for r in self.datasets.crops.to_dict("records")}
        excluded = [cid for name, cid in names.items()
                    if re.search(rf"\b(no|avoid|without|exclude|not)\s+(?:\w+\s+){{0,2}}{name}", t)]
        preferred = [cid for name, cid in names.items()
                     if re.search(rf"\b{name}\b", t) and cid not in excluded]
        if preferred:
            out["preferred_crops"] = preferred
        if excluded:
            out["excluded_crops"] = excluded
        if m := re.search(r"(?i:farm (?:is )?called|farm named|named|name is)\s+([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)", text):
            out["farm_name"] = m.group(1).strip()
        return out

    def from_text(self, text: str, use_gemini: bool = True) -> ParseResult:
        """Parse free text. Values are sanitised; missing fields are reported, never invented."""
        if not text or not text.strip():
            return ParseResult({}, list(REQUIRED_FIELDS), ["No text provided"], "none")
        raw, source, notes = None, "rules", []
        if use_gemini and self.gemini.available:
            raw = self.gemini.parse_farm_description(text, self.datasets.crop_ids, self.datasets.soil_types)
            if raw is None:
                notes.append("Gemini parsing failed; used the rule-based parser instead")
            else:
                source = "gemini"
        if raw is None:
            raw = self.rule_based_parse(text)
        values, sanitize_notes = sanitize_parsed_farm(raw, self.datasets.crop_ids, self.datasets.soil_types)
        missing = [f for f in REQUIRED_FIELDS if f not in values]
        if "rainfall_mm" in values and "seasons" in values:
            missing += [f"rainfall_mm.{s}" for s in values["seasons"] if s not in values["rainfall_mm"]]
        result = ParseResult(values, missing, notes + sanitize_notes, source)
        if not missing:
            try:
                result.profile = self.from_form(values)
            except FarmValidationError as exc:
                result.errors = exc.errors
        return result
