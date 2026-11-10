"""Scenario Agent: loads built-in scenarios and builds validated custom ones."""
from __future__ import annotations

import re

from services.data_loader import Datasets
from services.gemini_service import GeminiService
from simulation.scenario_engine import BASELINE_ID, make_custom_scenario, scenarios_from_frame
from simulation.weather_simulator import SCENARIO_LIMITS, Scenario
from utils.normalization import clip

KEYWORD_RULES: list[tuple[str, dict]] = [
    (r"severe drought|extreme drought", {"rainfall_multiplier": 0.3, "yield_stress_factor": 0.85,
                                         "water_availability_multiplier": 0.5}),
    (r"drought|dry|low rain|no rain", {"rainfall_multiplier": 0.5, "yield_stress_factor": 0.92,
                                       "water_availability_multiplier": 0.7}),
    (r"flood|heavy rain|excess rain|cyclone", {"rainfall_multiplier": 1.7, "yield_stress_factor": 0.93}),
    (r"heat ?wave|heat stress", {"yield_stress_factor": 0.88}),
    (r"(cost|input|fertili[sz]er|fuel|labou?r).{0,20}(rise|increase|up|shock|spike)|inflation",
     {"input_cost_multiplier": 1.3}),
    (r"price.{0,20}(drop|fall|crash|down)|market.{0,10}(drop|crash)", {"market_price_multiplier": 0.75}),
    (r"price.{0,20}(rise|increase|boom|up)", {"market_price_multiplier": 1.2}),
]


class ScenarioAgent:
    def __init__(self, datasets: Datasets, gemini: GeminiService | None = None):
        self.builtin = scenarios_from_frame(datasets.scenarios)
        self.gemini = gemini or GeminiService()

    def available(self) -> dict[str, Scenario]:
        return dict(self.builtin)

    def select(self, scenario_ids: list[str] | None = None,
               custom: list[Scenario] | None = None) -> list[Scenario]:
        """Chosen scenarios with the normal baseline always first."""
        ids = scenario_ids if scenario_ids is not None else list(self.builtin)
        unknown = [s for s in ids if s not in self.builtin]
        if unknown:
            raise ValueError(f"Unknown scenarios: {', '.join(unknown)}")
        chosen = [self.builtin[BASELINE_ID]] + [self.builtin[s] for s in ids if s != BASELINE_ID]
        seen = {s.scenario_id for s in chosen}
        for scenario in custom or []:
            if scenario.scenario_id not in seen:
                chosen.append(scenario)
                seen.add(scenario.scenario_id)
        return chosen

    def custom_from_params(self, name: str, params: dict, description: str = "") -> Scenario:
        return make_custom_scenario(name, params, description)

    @staticmethod
    def _sanitize(raw: dict) -> dict:
        params = {}
        for key, (low, high) in SCENARIO_LIMITS.items():
            try:
                params[key] = round(clip(float(raw.get(key, 1.0)), low, high), 3)
            except (TypeError, ValueError):
                params[key] = 1.0
        return params

    def rule_based_interpretation(self, text: str) -> dict:
        t = text.lower()
        params = {k: 1.0 for k in SCENARIO_LIMITS}
        for pattern, values in KEYWORD_RULES:
            if re.search(pattern, t):
                for key, value in values.items():
                    if params[key] == 1.0:
                        params[key] = value
        if m := re.search(r"(\d+)\s*%", t):
            pct = int(m.group(1)) / 100
            if re.search(r"price.{0,25}(drop|fall|down)", t):
                params["market_price_multiplier"] = 1 - pct
            elif re.search(r"(cost|input).{0,25}(rise|increase|up)", t):
                params["input_cost_multiplier"] = 1 + pct
            elif re.search(r"rain.{0,25}(drop|fall|down|less)", t):
                params["rainfall_multiplier"] = 1 - pct
        return params

    def custom_from_text(self, text: str, use_gemini: bool = True) -> tuple[Scenario, str, list[str]]:
        """Interpret a described scenario. Returns ``(scenario, source, notes)``."""
        if not text or not text.strip():
            raise ValueError("Describe the scenario first")
        notes, source, raw = [], "rules", None
        if use_gemini and self.gemini.available:
            raw = self.gemini.interpret_scenario(text)
            if raw is None:
                notes.append("Gemini interpretation failed; used keyword rules instead")
            else:
                source = "gemini"
        if raw is None:
            raw = self.rule_based_interpretation(text)
        params = self._sanitize(raw)
        if all(v == 1.0 for v in params.values()):
            notes.append("No recognisable change was found; the scenario equals normal conditions")
        name = str(raw.get("scenario_name") or text.strip()[:40])
        description = str(raw.get("description") or text.strip())[:300]
        return make_custom_scenario(name, params, description), source, notes
