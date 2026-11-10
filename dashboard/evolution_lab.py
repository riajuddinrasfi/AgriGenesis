"""Evolution lab: GA convergence, population diversity and parameter experiments."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.genetic_algorithm import GAParams
from dashboard import STRETCH, TEMPLATE

SWEEPABLE = {
    "mutation_rate": "0.02, 0.05, 0.1, 0.2",
    "crossover_rate": "0.5, 0.7, 0.85, 1.0",
    "population_size": "20, 40, 60",
    "tournament_size": "2, 3, 5",
    "elitism": "0, 2, 5",
}
INTEGER_PARAMS = {"population_size", "tournament_size", "elitism"}


def convergence_chart(history: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for col, name, dash in (("best_fitness", "Best", "solid"), ("mean_fitness", "Population mean", "dash")):
        fig.add_trace(go.Scatter(x=history["generation"], y=history[col], name=name,
                                 mode="lines", line={"dash": dash}))
    fig.update_layout(template=TEMPLATE, title="Fitness by generation", xaxis_title="Generation",
                      yaxis_title="Fitness", hovermode="x unified")
    return fig


def diversity_chart(history: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for col, name in (("diversity", "Unique plans"), ("feasible_share", "Feasible plans")):
        fig.add_trace(go.Scatter(x=history["generation"], y=history[col], name=name, mode="lines"))
    fig.update_layout(template=TEMPLATE, title="Population health", xaxis_title="Generation",
                      yaxis_tickformat=".0%", yaxis_range=[0, 1.05], hovermode="x unified")
    return fig


def sweep_chart(sweep: pd.DataFrame) -> go.Figure:
    name = sweep["parameter"].iloc[0]
    fig = go.Figure(go.Scatter(x=sweep["value"].astype(str), y=sweep["mean_fitness"], mode="lines+markers",
                               error_y={"type": "data", "array": sweep["std_fitness"]}))
    fig.update_layout(template=TEMPLATE, title=f"Sensitivity to {name}", xaxis_title=name,
                      yaxis_title="Mean best fitness")
    return fig


def render(orchestrator, report, params: GAParams) -> None:
    result = report.ga_result
    cols = st.columns(4)
    cols[0].metric("Generations run", result.generations_run)
    cols[1].metric("Unique plans evaluated", f"{result.evaluations:,}")
    cols[2].metric("Population", result.params.population_size)
    cols[3].metric("Best fitness", f"{result.best.fitness:,.0f}")
    left, right = st.columns(2)
    left.plotly_chart(convergence_chart(result.history), **STRETCH)
    right.plotly_chart(diversity_chart(result.history), **STRETCH)
    st.caption("Fitness = expected profit − risk aversion × profit σ + soil-health value − constraint penalties.")

    st.subheader("Parameter experiment")
    st.write("Measure how one GA setting affects plan quality, averaged over several random seeds.")
    c1, c2, c3 = st.columns([1, 2, 1])
    name = c1.selectbox("Parameter", list(SWEEPABLE))
    raw = c2.text_input("Values (comma separated)", SWEEPABLE[name], key=f"values_{name}")
    n_seeds = c3.number_input("Seeds per value", 1, 10, 3)
    if st.button("Run experiment"):
        cast = int if name in INTEGER_PARAMS else float
        try:
            values = [cast(v.strip()) for v in raw.split(",") if v.strip()]
            sweep_params = GAParams.from_config(
                orchestrator.config, **{**vars(params), "generations": min(params.generations, 40),
                                        "patience": None})
            with st.spinner("Running experiment…"):
                st.session_state["sweep"] = orchestrator.evolution_agent.sweep(
                    report.context, sweep_params, name, values, seeds=list(range(int(n_seeds))))
        except ValueError as exc:
            st.error(f"Invalid experiment settings: {exc}")
    sweep = st.session_state.get("sweep")
    if sweep is not None:
        st.plotly_chart(sweep_chart(sweep), **STRETCH)
        st.dataframe(sweep.round(2), hide_index=True, **STRETCH)
