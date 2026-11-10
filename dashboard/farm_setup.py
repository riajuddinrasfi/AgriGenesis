"""Farm setup: the farm profile, crop suitability and the input datasets."""
from __future__ import annotations

import streamlit as st

from dashboard import STRETCH


def render(orchestrator, report) -> None:
    context = report.context
    summary = orchestrator.farm_agent.summarize(context.farm)
    st.subheader(f"{summary['Farm']} · {summary['Region']}")
    cols = st.columns(4)
    for col, key in zip(cols, ["Total area (ha)", "Budget / season", "Labour / season", "Irrigation / season"]):
        col.metric(key, summary[key])
    st.write(f"{summary['Plots']} plots · {summary['Soil']} · risk tolerance {summary['Risk tolerance']}")
    st.caption("Change budget, labour, irrigation and risk tolerance in the sidebar.")

    st.subheader("Crop suitability (agronomy agent)")
    suitability = orchestrator.agronomy_agent.suitability(context.farm, context.seasons)
    pivot = suitability.pivot(index="crop", columns="season", values="score")[
        [s["name"] for s in context.seasons]]
    bars = {c: st.column_config.ProgressColumn(c, min_value=0.0, max_value=1.0, format="%.1f")
            for c in pivot.columns}
    st.dataframe(pivot, column_config=bars, **STRETCH)
    with st.expander("Why crops were excluded or marked marginal"):
        st.dataframe(suitability[suitability["score"] < 1], hide_index=True, **STRETCH)

    st.subheader("Datasets")
    loader = orchestrator.loader
    tables = {
        "Crops (with requirements and input costs)": loader.load_crops(),
        "Farms (with soil profiles)": loader.load_farms(),
        "Weather and market scenarios": loader.load_scenarios(),
    }
    for title, df in tables.items():
        with st.expander(title):
            st.dataframe(df, hide_index=True, **STRETCH)
    with st.expander("Planning configuration (sample_farm.json)"):
        st.json(orchestrator.config, expanded=False)
