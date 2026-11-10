"""Prompt 4: Gemini service and agents, with Gemini enabled (fake client) and disabled."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import errors

from agents.agronomy_agent import AgronomyAgent
from agents.farm_input_agent import FarmInputAgent
from agents.orchestrator import Orchestrator
from agents.scenario_agent import ScenarioAgent
from agents.simulation_agent import SimulationAgent
from config import GAConfig, GeminiSettings
from services.gemini_service import FARM_SCHEMA, SCENARIO_SCHEMA, GeminiService, redact_secrets, validate_json
from services.validation_service import FarmValidationError

ROOT = Path(__file__).resolve().parents[1]
KEY = "AIzaSyTESTKEY0000000000000000000000000"
NO_KEY = GeminiSettings("", "gemini-2.5-flash")
SMALL_GA = GAConfig(population_size=12, generations=3)
FARM_TEXT = ("Farm named Green Valley Farm has 4 hectares in 4 plots of loam soil, pH 6.5, soil health 65, "
             "30000 m3 of water and a budget of $12,000. Monsoon rain 1100 mm, winter rain 80 mm, "
             "summer rain 250 mm.")


class RecordingModels:
    """Stands in for ``client.models``; replies in order and records each request."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        reply = self.replies.pop(0) if self.replies else "Explanation without numbers."
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(text=reply)


def enabled(*replies):
    models = RecordingModels(replies)
    return GeminiService(GeminiSettings(KEY, "gemini-2.5-flash"), SimpleNamespace(models=models)), models


# --- Gemini service ---------------------------------------------------------------------------

def test_settings_and_service_never_show_the_key():
    settings = GeminiSettings(KEY, "gemini-2.5-flash")
    service = GeminiService(settings)
    for text in (repr(settings), repr(service), json.dumps(service.status())):
        assert KEY not in text
    assert service.available and service.status()["model"] == "gemini-2.5-flash"


def test_env_variables_are_read(monkeypatch):
    from config import get_gemini_settings
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    settings = get_gemini_settings()
    assert settings.api_key == KEY and settings.model == "gemini-test-model" and settings.configured
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.delenv("GEMINI_MODEL")
    assert not get_gemini_settings().configured and get_gemini_settings().model == "gemini-2.5-flash"


def test_real_sdk_client_is_built_lazily_without_network():
    from google import genai
    service = GeminiService(GeminiSettings(KEY, "gemini-2.5-flash"))
    assert service._client is None
    assert isinstance(service._get_client(), genai.Client)


def test_request_uses_current_sdk_config_and_schema():
    service, models = enabled('{"scenario_name": "Dry", "rainfall_multiplier": 0.5}')
    assert service.interpret_scenario("dry year") == {"scenario_name": "Dry", "rainfall_multiplier": 0.5}
    call = models.calls[0]
    assert call["model"] == "gemini-2.5-flash" and "dry year" in call["contents"]
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema == SCENARIO_SCHEMA


def test_validate_json_drops_wrong_types_and_unknown_fields():
    clean, problems = validate_json({"total_area_ha": "lots", "n_plots": 4, "seasons": ["winter", 3],
                                     "hack": 1, "rainfall_mm": {"winter": "wet", "summer": 200}}, FARM_SCHEMA)
    assert clean == {"n_plots": 4, "seasons": ["winter"], "rainfall_mm": {"summer": 200}}
    assert any("total_area_ha" in p for p in problems) and any("hack" in p for p in problems)
    assert validate_json({"rainfall_multiplier": 0.5}, SCENARIO_SCHEMA)[0] is None  # missing scenario_name


@pytest.mark.parametrize("reply", ["not json at all", "[1, 2, 3]", '{"total_area_ha": "big"}'])
def test_invalid_json_returns_none(reply):
    service, _ = enabled(reply)
    assert service.parse_farm_description("x", ["RICE"], ["loam"]) is None
    assert service.last_error


@pytest.mark.parametrize("error, phrase", [
    (errors.ClientError(401, {"error": {"code": 401, "message": f"API key {KEY} not valid",
                                        "status": "UNAUTHENTICATED"}}), "invalid API key"),
    (errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
     "quota"),
    (errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}}), "server error"),
    (ConnectionError(f"timeout with key={KEY}"), "ConnectionError"),
])
def test_api_errors_fall_back_with_redacted_message(error, phrase):
    service, _ = enabled(error)
    assert service.generate_text("hi") is None
    assert phrase in service.last_error and KEY not in service.last_error


def test_redact_secrets_masks_key_shaped_strings():
    assert redact_secrets("k=AQ.Ab8RN6abcdefghijklmnopqrstuvwxyz end") == "k=*** end"
    assert redact_secrets("mine-secret leaked", "mine-secret") == "*** leaked"


# --- Farm input agent -------------------------------------------------------------------------

def test_farm_text_without_gemini_gives_validated_profile(datasets):
    parsed = FarmInputAgent(datasets, GeminiService(NO_KEY)).from_text(FARM_TEXT)
    assert parsed.source == "rules" and parsed.complete, (parsed.missing, parsed.errors)
    out = parsed.to_json()
    assert out["farm_profile"]["total_area_ha"] == 4.0 and out["farm_profile"]["plot_area_ha"] == 1.0
    assert out["farm_profile"]["rainfall_mm"] == {"monsoon": 1100, "winter": 80, "summer": 250}
    json.dumps(out)  # serialisable


def test_farm_text_with_gemini_uses_ai_values_and_validates(datasets, sample_input):
    service, models = enabled(json.dumps(sample_input))
    parsed = FarmInputAgent(datasets, service).from_text("my farm ...")
    assert parsed.source == "gemini" and parsed.complete and len(models.calls) == 1
    assert parsed.profile.budget_usd == 12000 and parsed.profile.seasons == ["monsoon", "winter", "summer"]


def test_gemini_out_of_range_values_are_rejected_not_trusted(datasets, sample_input):
    bad = dict(sample_input, soil_ph=42, soil_type="moon_dust")
    parsed = FarmInputAgent(datasets, enabled(json.dumps(bad))[0]).from_text("my farm ...")
    assert not parsed.complete and {"soil_ph", "soil_type"} <= set(parsed.missing)
    assert any("soil_ph" in n for n in parsed.notes)


def test_gemini_failure_falls_back_to_rules(datasets):
    service, _ = enabled(RuntimeError("offline"))
    parsed = FarmInputAgent(datasets, service).from_text(FARM_TEXT)
    assert parsed.source == "rules" and parsed.complete and any("rule-based" in n for n in parsed.notes)


def test_structured_form_input_is_validated(datasets, sample_input):
    parsed = FarmInputAgent(datasets, enabled(json.dumps(dict(sample_input, seasons=["winter"])))[0]) \
        .from_text("x")
    assert parsed.profile is not None  # extra rainfall seasons are fine
    with pytest.raises(FarmValidationError):
        FarmInputAgent(datasets, GeminiService(NO_KEY)).from_form(dict(sample_input, n_plots=0))


# --- Agronomy, scenario and simulation agents ---------------------------------------------------

def test_agronomy_returns_feasible_options_and_messages(datasets, profile):
    report = AgronomyAgent(datasets).assess(profile)
    assert report.ok and set(report.feasible_options) == set(profile.seasons)
    assert all(report.feasible_options[s] for s in profile.seasons)
    infeasible = report.table[~report.table["feasible"]]
    assert not infeasible.empty and (infeasible["notes"] != "feasible").all()
    strict = AgronomyAgent(datasets).assess(type(profile)(**{**profile.__dict__, "soil_ph": 3.0}))
    assert not strict.ok and any(m["level"] == "error" for m in strict.messages)


def test_scenario_agent_loads_five_scenarios_and_custom_text(datasets):
    gemini_off = ScenarioAgent(datasets, GeminiService(NO_KEY))
    assert list(gemini_off.available()) == ["normal", "drought", "excess_rainfall", "input_price_shock",
                                            "market_price_drop"]
    rules, source, _ = gemini_off.custom_from_text("fertilizer costs rise 40%")
    assert source == "rules" and rules.input_cost_multiplier == pytest.approx(1.4)
    service, _ = enabled('{"scenario_name": "Locust swarm", "yield_stress_factor": 0.6, "description": "Pests"}')
    ai, source, _ = ScenarioAgent(datasets, service).custom_from_text("locusts arrive")
    assert source == "gemini" and ai.yield_stress_factor == 0.6 and ai.custom
    assert [s.scenario_id for s in gemini_off.select(["drought"], [ai])][:2] == ["normal", "drought"]


def test_simulation_agent_returns_structured_metrics(context, scenarios):
    from core.population import random_chromosome
    import numpy as np
    chromosome = random_chromosome(context, np.random.default_rng(1))
    out = SimulationAgent().evaluate_scenarios(context, chromosome, list(scenarios.values()))
    assert set(out["results"]) == set(scenarios) and 0.0 <= out["resilience"] <= 1.0
    totals = out["results"]["normal"].totals
    for key in ("total_yield_t", "revenue", "total_cost", "net_profit", "water_use_m3", "final_soil_health"):
        assert isinstance(totals[key], float)
    assert len(out["table"]) == 5


# --- Orchestrator --------------------------------------------------------------------------------

RESULT_KEYS = {"farm_profile", "validation_results", "scenarios", "best_strategy", "ranked_strategies",
               "best_fitness", "fitness_history", "simulation_metrics", "scenario_results", "research_report",
               "assumptions"}


def test_orchestrator_without_gemini(sample_input):
    result = Orchestrator(gemini=GeminiService(NO_KEY)).run(sample_input, ga_config=SMALL_GA)
    assert RESULT_KEYS <= set(result)
    assert result["research_report"]["source"] == "deterministic"
    assert result["ai_status"]["available"] is False
    assert result["best_fitness"] == result["best_strategy"]["fitness"]
    assert len(result["fitness_history"]) == SMALL_GA.generations


def test_orchestrator_with_gemini_text_input(sample_input):
    service, models = enabled(json.dumps(sample_input), "## Summary\nA balanced plan on synthetic data.")
    result = Orchestrator(gemini=service).run("Describe my farm ...", ga_config=SMALL_GA)
    assert RESULT_KEYS <= set(result) and result["farm_profile"]["farm_name"] == "Green Valley Farm"
    assert result["research_report"]["source"] == "gemini"
    assert result["research_report"]["deterministic_text"]  # rule-based numbers are always kept
    assert len(models.calls) == 2  # one parse + one explanation; none during optimisation
    facts = json.loads(models.calls[1]["contents"].split("FACTS (JSON):\n", 1)[1])
    assert facts["best_metrics"]["net_profit"] == pytest.approx(result["best_strategy"]["metrics"]["net_profit"])


def test_orchestrator_rejects_incomplete_text():
    with pytest.raises(FarmValidationError, match="Missing"):
        Orchestrator(gemini=GeminiService(NO_KEY)).run("a small farm", ga_config=SMALL_GA)


def test_ga_and_simulation_match_with_and_without_gemini(sample_input):
    off = Orchestrator(gemini=GeminiService(NO_KEY)).run(sample_input, ga_config=SMALL_GA)
    on = Orchestrator(gemini=enabled()[0]).run(sample_input, ga_config=SMALL_GA)
    assert off["best_strategy"]["genes"] == on["best_strategy"]["genes"]
    assert off["fitness_history"] == on["fitness_history"]


MODULES = ["config", "services.data_loader", "services.validation_service", "services.gemini_service",
           "services.strategy_service", "services.report_service", "agents.farm_input_agent",
           "agents.agronomy_agent", "agents.scenario_agent", "agents.simulation_agent", "agents.evolution_agent",
           "agents.research_agent", "agents.orchestrator", "core.genetic_algorithm", "simulation.farm_simulator"]


def test_no_circular_imports():
    """Import each module first in a fresh interpreter, so any import cycle would fail."""
    script = "import importlib, sys\nfor m in sys.argv[1:]:\n    importlib.import_module(m)\n"
    for module in MODULES:
        run = subprocess.run([sys.executable, "-c", script, module], cwd=ROOT, capture_output=True,
                             text=True, env={"PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")})
        assert run.returncode == 0, f"{module}: {run.stderr[-500:]}"
