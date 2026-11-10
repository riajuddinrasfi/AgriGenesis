"""Overview: headline metrics, the recommended rotation and where profit comes from."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import PALETTE, STRETCH, TEMPLATE
from utils.helpers import format_money


def crop_colors(crops) -> dict:
    crops = sorted(set(crops), key=lambda c: (c == "Fallow", c))
    return {c: ("#d9d9d9" if c == "Fallow" else PALETTE[i % len(PALETTE)]) for i, c in enumerate(crops)}


def rotation_chart(plan: pd.DataFrame, title: str = "Crop rotation plan") -> go.Figure:
    """Plot-by-season grid coloured by crop."""
    long = plan.reset_index(names="plot").melt(id_vars="plot", var_name="season", value_name="crop")
    colors = crop_colors(long["crop"])
    fig = go.Figure()
    for crop, color in colors.items():
        part = long[long["crop"] == crop]
        fig.add_trace(go.Bar(
            x=[1] * len(part), y=part["plot"], base=[list(plan.columns).index(s) for s in part["season"]],
            orientation="h", name=crop, marker_color=color, text=part["crop"],
            textposition="inside", insidetextanchor="middle", customdata=part["season"],
            hovertemplate="%{y} · %{customdata}<br>" + crop + "<extra></extra>",
        ))
    fig.update_layout(
        template=TEMPLATE, barmode="overlay", title=title, legend_title="Crop",
        xaxis={"tickvals": [i + 0.5 for i in range(len(plan.columns))],
               "ticktext": list(plan.columns), "range": [0, len(plan.columns)]},
        yaxis={"categoryorder": "array", "categoryarray": list(plan.index)[::-1]},
        height=max(300, 55 * len(plan)),
    )
    return fig


def season_profit_chart(details: pd.DataFrame) -> go.Figure:
    df = details.groupby(["season", "crop"], sort=False, as_index=False)["profit"].sum()
    colors = crop_colors(df["crop"])
    fig = px.bar(df, x="season", y="profit", color="crop", color_discrete_map=colors)
    fig.update_layout(template=TEMPLATE, title="Profit by season and crop (normal year)",
                      yaxis_title="Profit (USD)", xaxis_title="")
    return fig


def resource_chart(usage: pd.DataFrame) -> go.Figure:
    rows = []
    for col, cap, label in (("cost", "budget", "Budget"), ("labor_days", "labor_capacity", "Labour"),
                            ("irrigation_m3", "irrigation_capacity", "Irrigation")):
        for _, r in usage.iterrows():
            rows.append({"season": r["season"], "resource": label,
                         "utilisation": r[col] / r[cap] if r[cap] else 0})
    fig = px.bar(pd.DataFrame(rows), x="season", y="utilisation", color="resource", barmode="group",
                 color_discrete_sequence=PALETTE, text_auto=".0%")
    fig.add_hline(y=1.0, line_dash="dot", line_color="red", annotation_text="capacity")
    fig.update_layout(template=TEMPLATE, title="Resource utilisation per season",
                      yaxis_tickformat=".0%", yaxis_title="Share of capacity", xaxis_title="")
    return fig


def render(report) -> None:
    best = report.ga_result.best
    for warning in report.warnings:
        st.warning(warning)
    cols = st.columns(5)
    cols[0].metric("Expected profit", format_money(best.expected_profit))
    cols[1].metric("Worst-case scenario", format_money(best.worst_case_profit))
    cols[2].metric("Profit volatility (σ)", format_money(best.profit_std))
    cols[3].metric("Probability of loss", f"{report.risk['loss_probability']:.1%}")
    cols[4].metric("Feasible", "Yes" if best.feasible else "No")
    st.plotly_chart(rotation_chart(report.plan), **STRETCH)
    st.subheader("Key findings")
    for note in report.insights:
        st.markdown(f"- {note}")
    left, right = st.columns(2)
    left.plotly_chart(season_profit_chart(report.details), **STRETCH)
    right.plotly_chart(resource_chart(report.usage), **STRETCH)
    with st.expander("Plot-by-plot details (normal year)"):
        st.dataframe(report.details.round(1), hide_index=True, **STRETCH)
