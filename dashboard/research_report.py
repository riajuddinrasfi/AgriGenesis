"""Research Report page: final plan, economics, risks and the AI/rule-based explanation."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import SEASONS
from dashboard import ACCENT, PALETTE, get_orchestrator, require_result, style_figure
from services.report_service import build_markdown_report, cost_breakdown, risks_and_tradeoffs, save_report
from utils.helpers import money


def render() -> None:
    st.title("Research Report")
    result = require_result()
    if result is None:
        return
    orch = get_orchestrator()
    best, m = result["best_strategy"], result["best_strategy"]["metrics"]
    st.caption(result["assumptions"][0])

    c = st.columns(4)
    c[0].metric("Net profit", money(m["net_profit"]))
    c[1].metric("Revenue", money(m["revenue"]))
    c[2].metric("Total cost", money(m["total_cost"]))
    c[3].metric("Fitness", f"{best['fitness']:.4f}")

    st.subheader("Final plan (normal conditions)")
    genes = pd.DataFrame(result["simulation_metrics"]["gene_results"])
    genes["planting_window"] = [p["planting_window"] for p in best["plan"]]
    st.dataframe(genes[["plot_id", "season_name", "crop_name", "water_level", "fertilizer_level", "planting_window",
                        "yield_t", "water_use_m3", "revenue", "total_cost", "profit", "soil_health_end"]],
                 width="stretch", hide_index=True, column_config={
                     "yield_t": st.column_config.NumberColumn(format="%.2f"),
                     "water_use_m3": st.column_config.NumberColumn(format="%.0f"),
                     "revenue": st.column_config.NumberColumn(format="$%.0f"),
                     "total_cost": st.column_config.NumberColumn(format="$%.0f"),
                     "profit": st.column_config.NumberColumn(format="$%.0f"),
                     "soil_health_end": st.column_config.NumberColumn(format="%.1f")})

    c1, c2 = st.columns(2)
    alloc = genes.groupby(["season", "crop_name"], as_index=False)["area_ha"].sum()
    alloc["season"] = alloc["season"].map(lambda s: SEASONS[s]["name"])
    fig = px.bar(alloc, x="season", y="area_ha", color="crop_name", title="Crop allocation (ha)",
                 color_discrete_sequence=PALETTE)
    c1.plotly_chart(style_figure(fig), width="stretch")
    costs = cost_breakdown(result["simulation_metrics"]["gene_results"])
    fig = px.pie(names=[k.replace("_", " ") for k in costs], values=list(costs.values()), hole=0.5,
                 title="Cost breakdown", color_discrete_sequence=PALETTE)
    c2.plotly_chart(style_figure(fig), width="stretch")

    scen = pd.DataFrame(result["scenario_results"]["best"])
    fig = px.bar(scen, x="scenario", y="net_profit", text_auto=".0f", title="Scenario performance: net profit (USD)",
                 color_discrete_sequence=[ACCENT])
    st.plotly_chart(style_figure(fig, 320), width="stretch")

    st.subheader("Risks and trade-offs")
    for note in risks_and_tradeoffs(result):
        st.markdown(f"- {note}")

    st.subheader("Explanation")
    report = result["research_report"]
    label = f"Gemini ({report['model']})" if report["source"] == "gemini" else "rule-based template"
    st.caption(f"Source: {label}. Numbers come from the simulator; the text only explains them.")
    for w in report["warnings"]:
        st.warning(w)
    st.markdown(report["text"])
    if orch.gemini.available:
        label = "Regenerate Gemini explanation" if report["source"] == "gemini" else "Generate Gemini explanation"
        if st.button(label):
            with st.spinner("Asking Gemini to explain the simulated results..."):
                result["research_report"] = orch.explain_result(result, use_gemini=True)
            st.rerun()
    else:
        st.caption("Set GEMINI_API_KEY in .env to generate an AI explanation of these results.")

    st.subheader("Assumptions")
    for a in result["assumptions"]:
        st.markdown(f"- {a}")

    markdown = build_markdown_report(result)
    c1, c2 = st.columns(2)
    c1.download_button("Download report (Markdown)", markdown, "agrigenesis_report.md", "text/markdown")
    if c2.button("Save report to outputs/reports"):
        st.success(f"Saved to {save_report(markdown)}")
