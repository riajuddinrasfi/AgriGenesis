"""Gemini service fallbacks, JSON parsing and agent fallbacks (no network calls)."""
from __future__ import annotations

from types import SimpleNamespace

from agents.farm_input_agent import FarmInputAgent
from agents.research_agent import ResearchAgent, unverified_numbers
from agents.scenario_agent import ScenarioAgent
from config import GeminiSettings
from services.gemini_service import GeminiService, extract_json

NO_KEY = GeminiSettings(api_key="", model="gemini-2.5-flash")


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text, self.error = text, error

    def generate_content(self, **kwargs):
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def _service(text=None, error=None, key="secret-key-123"):
    return GeminiService(GeminiSettings(key, "gemini-2.5-flash"), SimpleNamespace(models=FakeModels(text, error)))


def test_no_key_returns_none():
    service = GeminiService(NO_KEY)
    assert not service.available
    assert service.generate_text("hi") is None and service.explain_strategy({}) is None
    assert "not configured" in service.last_error


def test_placeholder_key_is_not_configured():
    assert not GeminiSettings("your-gemini-api-key-here", "m").configured


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('noise {"a": 3} trailing') == {"a": 3}
    assert extract_json("not json") is None and extract_json(None) is None


def test_errors_fall_back_and_redact_key():
    service = _service(error=RuntimeError("bad key secret-key-123"))
    assert service.generate_text("hi") is None
    assert "secret-key-123" not in service.last_error and "***" in service.last_error


def test_fake_client_json():
    assert _service(text='{"soil_type": "clay"}').generate_json("x") == {"soil_type": "clay"}


def test_farm_input_rule_fallback(datasets):
    parsed = FarmInputAgent(datasets, GeminiService(NO_KEY)).from_text(
        "Farm named Hill Top has 2.5 hectares in 2 plots of sandy loam, pH 6.2, "
        "10000 m3 of water and a budget of $5,000 for the winter season.")
    assert parsed.source == "rules"
    v = parsed.values
    assert v["total_area_ha"] == 2.5 and v["n_plots"] == 2 and v["soil_type"] == "sandy_loam"
    assert v["available_water_m3"] == 10000 and v["budget_usd"] == 5000 and v["seasons"] == ["winter"]


def test_scenario_rule_fallback(datasets):
    scenario, source, _ = ScenarioAgent(datasets, GeminiService(NO_KEY)).custom_from_text("severe drought")
    assert source == "rules" and scenario.rainfall_multiplier < 1.0 and scenario.custom


def test_gemini_scenario_values_are_clamped(datasets):
    service = _service(text='{"scenario_name": "Wild", "rainfall_multiplier": 99, "market_price_multiplier": 0.8}')
    scenario, source, _ = ScenarioAgent(datasets, service).custom_from_text("wild weather")
    assert source == "gemini" and scenario.rainfall_multiplier == 3.0 and scenario.market_price_multiplier == 0.8


FACTS = {
    "farm": {"farm_name": "Test"},
    "weights": {"profit": 0.5, "yield": 0.5, "water": 0.0, "soil": 0.0, "resilience": 0.0},
    "best_fitness": 0.7,
    "fitness_components": {"profit": 0.8, "yield": 0.6, "water": 0.5, "soil": 0.5, "resilience": 0.7},
    "best_metrics": {"net_profit": 6896.32, "revenue": 11141.0, "total_cost": 4245.0, "water_use_m3": 11122.0,
                     "water_available_m3": 30000.0, "final_soil_health": 66.7, "soil_health_change": 1.7},
    "allocation": {"Winter": {"Lentil": 4}},
    "scenario_profits": {"Drought": 5278.6},
}


def test_research_agent_fallback_uses_real_numbers():
    report = ResearchAgent(GeminiService(NO_KEY)).explain(FACTS)
    assert report["source"] == "deterministic" and "$6,896" in report["text"]


def test_research_agent_flags_invented_numbers():
    assert unverified_numbers("Profit was $6,896 and yield rose 4321 t", FACTS) == ["4321"]
    report = ResearchAgent(_service(text="Profit hits $99,999.")).explain(FACTS)
    assert report["source"] == "gemini" and any("99,999" in w for w in report["warnings"])
