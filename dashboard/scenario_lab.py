"""Scenario lab: profit under each scenario, Monte Carlo risk and custom what-if scenarios."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import PALETTE, STRETCH, TEMPLATE
from utils.helpers import format_money


def scenario_profit_chart(scenarios: pd.DataFrame) -> go.Figure:
    df = scenarios.sort_values("profit")
    fig = px.bar(df, x="profit", y="scenario", orientation="h", color="profit",
                 color_continuous_scale="RdYlGn", text_auto=",.0f",
                 hover_data={"probability": ":.0%", "revenue": ":,.0f", "cost": ":,.0f"})
    fig.update_layout(template=TEMPLATE, title="Total profit by scenario",
                      xaxis_title="Profit (USD)", yaxis_title="", coloraxis_showscale=False)
    return fig


def monte_carlo_chart(mc: pd.DataFrame) -> go.Figure:
    fig = px.histogram(mc, x="profit", color="scenario", nbins=40, barmode="stack",
                       color_discrete_sequence=PALETTE)
    fig.add_vline(x=mc["profit"].mean(), line_dash="dash", annotation_text="mean")
    fig.update_layout(template=TEMPLATE, title="Monte Carlo profit distribution",
                      xaxis_title="Total profit (USD)", yaxis_title="Runs")
    return fig


def render(orchestrator, report) -> None:
    risk = report.risk
    cols = st.columns(4)
    cols[0].metric("Monte Carlo mean", format_money(risk["mean"]))
    cols[1].metric("5th percentile", format_money(risk["p5"]))
    cols[2].metric("Expected shortfall (5%)", format_money(risk["cvar5"]))
    cols[3].metric("Probability of loss", f"{risk['loss_probability']:.1%}")
    left, right = st.columns(2)
    left.plotly_chart(scenario_profit_chart(report.scenarios), **STRETCH)
    right.plotly_chart(monte_carlo_chart(report.monte_carlo), **STRETCH)
    with st.expander("Scenario table"):
        st.dataframe(report.scenarios.round(2), hide_index=True, **STRETCH)

    st.subheader("What-if: build your own scenario")
    st.caption("Stress-test the optimised plan under conditions you choose.")
    c = st.columns(3)
    factors = {
        "rainfall_factor": c[0].slider("Rainfall (× normal)", 0.2, 2.0, 1.0, 0.05),
        "temp_shift": c[1].slider("Temperature shift (°C)", -5.0, 5.0, 0.0, 0.5),
        "price_factor": c[2].slider("Crop prices (× normal)", 0.5, 1.5, 1.0, 0.05),
        "cost_factor": c[0].slider("Input costs (× normal)", 0.5, 1.5, 1.0, 0.05),
        "pest_pressure": c[1].slider("Pest pressure", 0.0, 1.0, 0.1, 0.05),
        "yield_shock": c[2].slider("Yield shock (× normal)", 0.5, 1.2, 1.0, 0.05),
    }
    custom = orchestrator.scenario_agent.custom(**factors)
    details = orchestrator.simulation_agent.what_if(report.context, report.ga_result.best_genes, custom)
    normal = report.details["profit"].sum()
    total = details["profit"].sum()
    m = st.columns(3)
    m[0].metric("Profit in your scenario", format_money(total), format_money(total - normal))
    m[1].metric("Revenue", format_money(details["revenue"].sum()))
    m[2].metric("Irrigation used", f"{details['irrigation_m3'].sum():,.0f} m³")
    by_season = details.groupby("season", sort=False, as_index=False)[["revenue", "cost", "profit"]].sum()
    fig = px.bar(by_season.melt(id_vars="season"), x="season", y="value", color="variable",
                 barmode="group", color_discrete_sequence=PALETTE)
    fig.update_layout(template=TEMPLATE, title="Your scenario by season", yaxis_title="USD", xaxis_title="")
    st.plotly_chart(fig, **STRETCH)
