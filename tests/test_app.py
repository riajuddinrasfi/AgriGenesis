"""End-to-end smoke test of the Streamlit dashboard using Streamlit's AppTest (no Gemini key needed)."""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

PAGES = ["Overview", "Farm Setup", "Scenario Lab", "Evolution Lab", "Strategy Comparison", "Research Report"]


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def _goto(at: AppTest, page: str) -> None:
    at.radio(key="page").set_value(page).run(timeout=120)
    assert not at.exception, [e.value for e in at.exception]


def test_full_dashboard_flow(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    at = AppTest.from_file(str(APP_PATH), default_timeout=120).run()
    assert not at.exception
    for page in PAGES:
        _goto(at, page)

    _goto(at, "Farm Setup")
    _button(at, "Validate farm").click().run()
    assert not at.exception
    assert at.session_state.farm_profile is not None
    assert any("Farm validated" in s.value for s in at.success)

    _goto(at, "Evolution Lab")
    next(n for n in at.number_input if n.label == "Population size").set_value(12)
    next(n for n in at.number_input if n.label == "Generations").set_value(4)
    _button(at, "Run evolution").click().run()
    assert not at.exception, [e.value for e in at.exception]
    result = at.session_state.result
    assert result is not None and len(result["fitness_history"]) == 4

    for page in PAGES:
        _goto(at, page)
    _goto(at, "Scenario Lab")
    _button(at, "Evaluate best strategy under these scenarios").click().run()
    assert not at.exception
    assert at.session_state.scenario_eval is not None
