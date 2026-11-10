"""Full user journey through the Streamlit dashboard with Streamlit's AppTest (Gemini off and faked on)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from services.gemini_service import GeminiService
from utils.helpers import money

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PAGES = ["Overview", "Farm Setup", "Scenario Lab", "Evolution Lab", "Strategy Comparison", "Research Report"]


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def _by_label(widgets, label: str):
    return next(w for w in widgets if w.label == label)


def _ok(at: AppTest) -> None:
    assert not at.exception, [e.value for e in at.exception]


def _goto(at: AppTest, page: str) -> None:
    at.radio(key="page").set_value(page).run(timeout=120)
    _ok(at)


def _start(monkeypatch, key: str = "") -> AppTest:
    monkeypatch.setenv("GEMINI_API_KEY", key)
    st.cache_resource.clear()  # the orchestrator (and its Gemini settings) is cached per process
    at = AppTest.from_file(str(APP_PATH), default_timeout=120).run()
    _ok(at)
    return at


def _validate_and_evolve(at: AppTest, population: int = 12, generations: int = 4) -> dict:
    _goto(at, "Farm Setup")
    _button(at, "Load sample").click().run()
    _by_label(at.slider, "Profit").set_value(0.5)
    _button(at, "Validate farm").click().run()
    _ok(at)
    assert at.session_state.farm_profile is not None
    assert any("Farm validated" in s.value for s in at.success)
    _goto(at, "Evolution Lab")
    _by_label(at.number_input, "Population size").set_value(population)
    _by_label(at.number_input, "Generations").set_value(generations)
    _button(at, "Evolve My Farm").click().run()
    _ok(at)
    return at.session_state.result


@pytest.fixture(autouse=True)
def _clear_cache():
    yield
    st.cache_resource.clear()


def test_full_user_journey_without_gemini(monkeypatch):
    at = _start(monkeypatch)
    for page in PAGES:  # every page renders before any optimisation
        _goto(at, page)

    # Natural-language input is parsed by the rule-based parser and applied to the form.
    _goto(at, "Farm Setup")
    at.text_area[0].set_value("Farm named River Bend has 3 hectares in 3 plots of clay loam, pH 6.8, "
                              "20000 m3 of water and a budget of $9,000 for the winter season.").run()
    _button(at, "Parse description").click().run()
    _ok(at)
    assert at.session_state.nl_parse.values["farm_name"] == "River Bend"
    _button(at, "Apply parsed values to the form").click().run()
    assert at.session_state.farm_input["n_plots"] == 3

    # Scenario selection, including a custom scenario described in words.
    _goto(at, "Scenario Lab")
    at.multiselect[0].set_value(["drought", "market_price_drop"]).run()
    _by_label(at.text_input, "Describe the scenario").set_value("fertilizer costs rise 40%").run()
    _button(at, "Interpret and add").click().run()
    _ok(at)
    assert len(at.session_state.custom_scenarios) == 1

    result = _validate_and_evolve(at)
    history = result["fitness_history"]
    assert len(history) == 4 and history[-1]["best_fitness"] >= history[0]["best_fitness"]
    assert result["optimization"]["weights"]["profit"] > 0.35  # the 0.5 priority was used (then normalised)
    assert set(result["scenarios"]) >= {"normal", "drought", "market_price_drop"} and len(result["scenarios"]) == 4
    assert at.session_state.result_inputs is not None and not any("changed since" in w.value for w in at.warning)

    # Live numbers come from the result, not hardcoded samples.
    profit = money(result["best_strategy"]["metrics"]["net_profit"])
    assert _by_label(at.metric, "Best net profit").value == profit
    _goto(at, "Overview")
    assert _by_label(at.metric, "Net profit").value == profit

    # Changing pages never re-runs the optimiser.
    runtime, evaluations = result["optimization"]["runtime_s"], result["optimization"]["evaluations"]
    for page in PAGES + PAGES[::-1]:
        _goto(at, page)
    again = at.session_state.result
    assert again["optimization"]["runtime_s"] == runtime and again["optimization"]["evaluations"] == evaluations

    _goto(at, "Strategy Comparison")
    assert len(at.dataframe) >= 2
    at.selectbox[0].set_value(at.selectbox[0].options[-1]).run()
    _ok(at)

    _goto(at, "Scenario Lab")
    _button(at, "Evaluate best strategy under these scenarios").click().run()
    _ok(at)
    assert len(at.session_state.scenario_eval["table"]) == 4

    _goto(at, "Research Report")
    assert result["research_report"]["source"] == "deterministic"
    assert not [b for b in at.button if "Gemini explanation" in b.label]
    assert any("GEMINI_API_KEY" in c.value for c in at.caption)

    # Changing an input marks the stored result as stale instead of silently re-running.
    _goto(at, "Scenario Lab")
    at.multiselect[0].set_value(["drought"]).run()
    _goto(at, "Evolution Lab")
    assert any("changed since this run" in w.value for w in at.warning)
    assert at.session_state.result["optimization"]["runtime_s"] == runtime


class FakeModels:
    def __init__(self):
        self.calls = 0

    def generate_content(self, *, model, contents, config):
        self.calls += 1
        return SimpleNamespace(text=f"### Summary\nExplanation {self.calls} of the simulated plan (synthetic data).")


def test_journey_with_gemini_explanation(monkeypatch):
    fake = FakeModels()
    monkeypatch.setattr(GeminiService, "_get_client", lambda self: SimpleNamespace(models=fake))
    at = _start(monkeypatch, key="AIzaSyFAKEKEYFORTESTS000000000000000000")
    assert any("Gemini connected" in m.value for m in at.markdown)

    result = _validate_and_evolve(at, population=10, generations=3)
    assert result["research_report"]["source"] == "gemini" and fake.calls == 1  # never called by the GA
    _goto(at, "Research Report")
    assert any("Explanation 1" in m.value for m in at.markdown)
    _button(at, "Regenerate Gemini explanation").click().run()
    _ok(at)
    assert fake.calls == 2 and at.session_state.result["research_report"]["text"].endswith("(synthetic data).")
    assert any("Explanation 2" in m.value for m in at.markdown)
