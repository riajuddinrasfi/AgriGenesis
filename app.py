"""AgriGenesis: multi-agent, genetic-algorithm crop planning (Streamlit app).

Run with ``streamlit run app.py``.
"""
from __future__ import annotations

import streamlit as st

from agents.orchestrator import Orchestrator
from core.genetic_algorithm import GAParams
from dashboard import (
    evolution_lab, farm_setup, overview, research_report, scenario_lab, strategy_comparison,
)

st.set_page_config(page_title="AgriGenesis", page_icon="🌾", layout="wide")


@st.cache_resource
def get_orchestrator() -> Orchestrator:
    return Orchestrator()


orchestrator = get_orchestrator()
config = orchestrator.config
ga_defaults = GAParams.from_config(config)
farms = orchestrator.farm_agent.list_farms()

with st.sidebar:
    st.header("Farm")
    farm_id = st.selectbox("Farm profile", list(farms), format_func=lambda f: f"{farms[f]} ({f})")
    farm = orchestrator.farm_agent.get_farm(farm_id)
    all_scenarios = orchestrator.scenario_agent.names()
    scenario_names = st.multiselect("Scenarios to plan against", all_scenarios, default=all_scenarios)
    with st.expander("Resources and risk"):
        budget = st.number_input("Budget per season (USD)", 0.0, value=float(farm["budget"]), step=500.0)
        labor = st.number_input("Labour per season (days)", 0.0, value=float(farm["labor_days"]), step=25.0)
        irrigation = st.number_input("Irrigation per season (m³)", 0.0,
                                     value=float(farm["irrigation_m3"]), step=1000.0)
        risk_tolerance = st.slider("Risk tolerance", 0.0, 1.0, float(farm["risk_tolerance"]), 0.05)
        soil_weight = st.slider("Soil health weight", 0.0, 100.0,
                                float(config["fitness"]["soil_health_weight"]), 5.0)
    with st.expander("Genetic algorithm"):
        population = st.slider("Population size", 10, 200, ga_defaults.population_size, 10)
        generations = st.slider("Generations", 10, 300, ga_defaults.generations, 10)
        mutation = st.slider("Mutation rate", 0.0, 0.5, ga_defaults.mutation_rate, 0.01)
        crossover = st.slider("Crossover rate", 0.0, 1.0, ga_defaults.crossover_rate, 0.05)
        seed = st.number_input("Random seed", 0, 10_000, int(ga_defaults.seed or 0))
    run = st.button("Run optimisation", type="primary", width="stretch")

farm_overrides = {"budget": budget, "labor_days": labor, "irrigation_m3": irrigation,
                  "risk_tolerance": risk_tolerance}
params = GAParams.from_config(
    config, population_size=population, generations=generations, mutation_rate=mutation,
    crossover_rate=crossover, seed=int(seed), tournament_size=min(ga_defaults.tournament_size, population))
inputs_key = (farm_id, tuple(scenario_names), tuple(farm_overrides.values()), soil_weight,
              tuple(vars(params).values()))

st.title("🌾 AgriGenesis")
st.caption("Evolving resilient crop rotation plans with agents, farm simulation and a genetic algorithm.")

if not scenario_names:
    st.warning("Select at least one scenario in the sidebar.")
    st.stop()

if run or "report" not in st.session_state:
    bar = st.progress(0.0, text="Evolving crop plans…")

    def progress(generation: int, best: float) -> None:
        bar.progress(generation / params.generations,
                     text=f"Generation {generation}/{params.generations} · best fitness {best:,.0f}")

    st.session_state["report"] = orchestrator.plan(
        farm_id, params, scenario_names, farm_overrides, {"soil_health_weight": soil_weight}, progress)
    st.session_state["report_key"] = inputs_key
    st.session_state.pop("sweep", None)
    bar.empty()

report = st.session_state["report"]
if st.session_state.get("report_key") != inputs_key:
    st.info("Settings changed since the last run. Click **Run optimisation** to update the plan.")

tabs = st.tabs(["Overview", "Farm setup", "Scenario lab", "Evolution lab", "Strategy comparison",
                "Research report"])
with tabs[0]:
    overview.render(report)
with tabs[1]:
    farm_setup.render(orchestrator, report)
with tabs[2]:
    scenario_lab.render(orchestrator, report)
with tabs[3]:
    evolution_lab.render(orchestrator, report, params)
with tabs[4]:
    strategy_comparison.render(report)
with tabs[5]:
    research_report.render(orchestrator, report)
