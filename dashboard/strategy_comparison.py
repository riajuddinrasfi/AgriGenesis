"""Strategy comparison: the GA plan against baselines, constraint checks and saved strategies."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import PALETTE, STRETCH, TEMPLATE
from dashboard.overview import rotation_chart
from services.strategy_service import baseline_strategies, genes_to_frame, save_strategy, strategy_record

MONEY_COLS = ["fitness", "expected_profit", "profit_std", "worst_case_profit", "soil_health", "penalty"]


def comparison_chart(comparison: pd.DataFrame) -> go.Figure:
    df = comparison.sort_values("expected_profit")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["expected_profit"], y=df["strategy"], orientation="h",
                         name="Expected profit", marker_color=PALETTE[0]))
    fig.add_trace(go.Bar(x=df["worst_case_profit"], y=df["strategy"], orientation="h",
                         name="Worst-case profit", marker_color=PALETTE[1]))
    fig.update_layout(template=TEMPLATE, barmode="group", title="Strategy comparison",
                      xaxis_title="Profit (USD)")
    return fig


def render(report) -> None:
    context = report.context
    st.plotly_chart(comparison_chart(report.comparison), **STRETCH)
    st.dataframe(report.comparison.style.format({c: "{:,.0f}" for c in MONEY_COLS}),
                 hide_index=True, **STRETCH)
    st.caption("Baselines that break budget, labour or suitability rules get large penalties, "
               "so their fitness can be far below their raw profit.")

    st.subheader("Constraints (optimised plan)")
    if report.violations.empty:
        st.success("All budget, labour, suitability and rotation constraints are satisfied.")
    else:
        st.dataframe(report.violations, hide_index=True, **STRETCH)

    with st.expander("View a baseline plan"):
        baselines = baseline_strategies(context)
        choice = st.selectbox("Baseline", list(baselines))
        st.plotly_chart(rotation_chart(genes_to_frame(context, baselines[choice]), choice), **STRETCH)

    st.subheader("Export")
    c1, c2 = st.columns(2)
    c1.download_button("Download plan (CSV)", report.plan.to_csv().encode(),
                       file_name=f"agrigenesis_plan_{context.farm['farm_id']}.csv", mime="text/csv")
    if c2.button("Save strategy to outputs/strategies"):
        record = strategy_record(context, report.ga_result.best_genes, report.ga_result.best.as_dict(),
                                 "genetic-algorithm")
        st.success(f"Saved {save_strategy(record).name}")
