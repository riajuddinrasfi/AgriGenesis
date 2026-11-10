"""Overview page: farm summary, optimisation status and key results."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from config import SEASONS, SYNTHETIC_DATA_NOTICE
from dashboard import ACCENT, MUTED, badge, get_orchestrator, plan_pivot, result_is_stale, style_figure
from utils.helpers import money


def render() -> None:
    st.title("AgriGenesis")
    st.markdown("**An Evolutionary Agriculture Strategy Laboratory**: a Genetic Algorithm evolves whole-farm "
                "strategies, scored by a deterministic simulator under several scenarios.")
    st.caption(SYNTHETIC_DATA_NOTICE)

    gemini = get_orchestrator().gemini
    status = "Gemini connected" if gemini.available else "Gemini not configured (rule-based fallback)"
    st.markdown(badge(status) + badge("Simulation: deterministic") + badge("Optimiser: Genetic Algorithm"),
                unsafe_allow_html=True)

    farm = st.session_state.farm_profile or st.session_state.farm_input
    st.subheader("Farm summary")
    if st.session_state.farm_profile is None:
        st.warning("The farm below is not validated yet. Open **Farm Setup** and click *Validate farm*.")
    cols = st.columns(5)
    cols[0].metric("Farm", farm.get("farm_name") or "-")
    cols[1].metric("Land", f"{farm.get('total_area_ha', 0)} ha", f"{farm.get('n_plots', 0)} plots", delta_color="off")
    cols[2].metric("Budget", money(float(farm.get("budget_usd") or 0)))
    cols[3].metric("Water", f"{float(farm.get('available_water_m3') or 0):,.0f} m3")
    cols[4].metric("Soil", str(farm.get("soil_type", "-")), f"pH {farm.get('soil_ph')}", delta_color="off")
    st.caption("Seasons: " + ", ".join(SEASONS[s]["name"] for s in farm.get("seasons", []) if s in SEASONS))

    st.subheader("Optimisation status")
    result = st.session_state.result
    if result is None:
        st.info("Not optimised yet. Run the Genetic Algorithm in **Evolution Lab**.")
        return
    opt = result["optimization"]
    cols = st.columns(4)
    cols[0].metric("Best fitness", f"{result['best_fitness']:.4f}")
    cols[1].metric("Generations", len(result["fitness_history"]))
    cols[2].metric("Strategies evaluated", f"{opt['evaluations']:,}")
    cols[3].metric("Runtime", f"{opt['runtime_s']:.1f} s")
    if result_is_stale():
        st.warning("The farm, priorities or scenarios changed since this run; click **Evolve My Farm** in "
                   "Evolution Lab to update the results.")

    st.subheader("Key results (normal scenario)")
    m, c = result["best_strategy"]["metrics"], result["best_strategy"]["components"]
    cols = st.columns(5)
    cols[0].metric("Net profit", money(m["net_profit"]))
    cols[1].metric("Total yield", f"{m['total_yield_t']:.1f} t")
    cols[2].metric("Water used", f"{m['water_use_m3']:,.0f} m3")
    cols[3].metric("Final soil health", f"{m['final_soil_health']:.1f}", f"{m['soil_health_change']:+.1f}")
    cols[4].metric("Resilience", f"{c['resilience']:.2f}")

    left, right = st.columns([1, 1])
    with left:
        history = result["fitness_history"]
        fig = go.Figure()
        fig.add_scatter(x=[h["generation"] for h in history], y=[h["best_fitness"] for h in history],
                        name="Best", line=dict(color=ACCENT, width=3))
        fig.add_scatter(x=[h["generation"] for h in history], y=[h["mean_fitness"] for h in history],
                        name="Mean", line=dict(color=MUTED, dash="dot"))
        fig.update_layout(title="Fitness by generation", xaxis_title="Generation", yaxis_title="Fitness")
        st.plotly_chart(style_figure(fig, 320), width="stretch")
    with right:
        fig = go.Figure(go.Bar(x=list(c.keys()), y=list(c.values()), marker_color=ACCENT,
                               text=[f"{v:.2f}" for v in c.values()], textposition="outside"))
        fig.update_layout(title="Fitness components (0-1)", yaxis_range=[0, 1.1])
        st.plotly_chart(style_figure(fig, 320), width="stretch")
    st.markdown("**Best strategy**")
    st.dataframe(plan_pivot(result["best_strategy"]["plan"]), width="stretch")
