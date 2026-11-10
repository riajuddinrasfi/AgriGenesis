"""Strategy Comparison page: compare the top strategies found by the GA."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import ACCENT, PALETTE, plan_pivot, require_result, style_figure
from services.strategy_service import comparison_frame


def _bar(frame: pd.DataFrame, column: str, title: str, fmt: str):
    fig = px.bar(frame, x="strategy", y=column, text_auto=fmt, title=title, color_discrete_sequence=[ACCENT])
    return style_figure(fig, 300)


def render() -> None:
    st.title("Strategy Comparison")
    result = require_result()
    if result is None:
        return
    strategies = result["ranked_strategies"]
    frame = comparison_frame(strategies)
    st.markdown(f"The {len(strategies)} best distinct strategies found by the Genetic Algorithm, ranked by fitness. "
                "Metrics are for normal conditions unless stated otherwise.")
    st.dataframe(frame, width="stretch", hide_index=True, column_config={
        "fitness": st.column_config.ProgressColumn("fitness", min_value=0.0, max_value=1.0, format="%.4f"),
        "net_profit": st.column_config.NumberColumn(format="$%.0f"),
        "total_yield_t": st.column_config.NumberColumn(format="%.1f t"),
        "water_use_m3": st.column_config.NumberColumn(format="%.0f m3"),
        "final_soil_health": st.column_config.NumberColumn(format="%.1f"),
        "resilience": st.column_config.ProgressColumn("resilience", min_value=0.0, max_value=1.0, format="%.2f"),
    })

    c1, c2 = st.columns(2)
    c1.plotly_chart(_bar(frame, "net_profit", "Net profit (USD)", ".0f"), width="stretch")
    c2.plotly_chart(_bar(frame, "total_yield_t", "Total yield (t)", ".1f"), width="stretch")
    c1, c2 = st.columns(2)
    c1.plotly_chart(_bar(frame, "water_use_m3", "Irrigation water used (m3)", ".0f"), width="stretch")
    c2.plotly_chart(_bar(frame, "final_soil_health", "Final soil health index", ".1f"), width="stretch")

    keys = list(strategies[0]["components"])
    fig = go.Figure()
    for s, color in zip(strategies, PALETTE):
        values = [s["components"][k] for k in keys]
        fig.add_scatterpolar(r=values + values[:1], theta=keys + keys[:1], name=f"#{s['rank']}", line=dict(color=color))
    fig.update_layout(title="Normalised objective scores", polar=dict(radialaxis=dict(range=[0, 1])))
    c1, c2 = st.columns(2)
    c1.plotly_chart(style_figure(fig, 380), width="stretch")

    rows = [{"strategy": label, "scenario": r["scenario"], "net_profit": r["net_profit"]}
            for label, records in result["scenario_results"]["ranked"].items() for r in records]
    heat = pd.DataFrame(rows).pivot(index="strategy", columns="scenario", values="net_profit")
    heat = heat[[c for c in dict.fromkeys(r["scenario"] for r in rows)]]
    fig = px.imshow(heat, text_auto=".0f", aspect="auto", color_continuous_scale="Purples",
                    title="Net profit by scenario (USD)")
    c2.plotly_chart(style_figure(fig, 380), width="stretch")

    st.subheader("Inspect a strategy")
    pick = st.selectbox("Strategy", [f"#{s['rank']}" for s in strategies])
    chosen = next(s for s in strategies if f"#{s['rank']}" == pick)
    st.dataframe(plan_pivot(chosen["plan"]), width="stretch")
    if chosen["violations"]:
        for v in chosen["violations"]:
            st.error(v)
    else:
        st.caption("All constraints satisfied (land, budget, water, crop-season and planting window).")
