"""Scenario Lab page: choose built-in scenarios, add custom ones and stress-test the best strategy."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard import ACCENT, get_orchestrator, style_figure
from simulation.weather_simulator import SCENARIO_LIMITS

PARAM_LABELS = {
    "rainfall_multiplier": "Rainfall x",
    "yield_stress_factor": "Yield stress x",
    "input_cost_multiplier": "Input cost x",
    "market_price_multiplier": "Market price x",
    "water_availability_multiplier": "Water availability x",
}


def _custom_builder() -> None:
    orch = get_orchestrator()
    by_params, by_text = st.tabs(["Set parameters", "Describe in words"])
    with by_params, st.form("custom_scenario"):
        name = st.text_input("Scenario name", "Custom scenario")
        cols = st.columns(len(PARAM_LABELS))
        params = {k: cols[i].number_input(label, low, high, 1.0, 0.05)
                  for i, (k, label) in enumerate(PARAM_LABELS.items()) for low, high in [SCENARIO_LIMITS[k]]}
        if st.form_submit_button("Add scenario"):
            st.session_state.custom_scenarios.append(orch.scenario.custom_from_params(name, params))
            st.rerun()
    with by_text:
        text = st.text_input("Describe the scenario", placeholder="e.g. a severe drought with fertilizer prices up 40%")
        if st.button("Interpret and add", disabled=not text.strip()):
            scenario, source, notes = orch.scenario.custom_from_text(text, st.session_state.use_gemini)
            st.session_state.custom_scenarios.append(scenario)
            st.session_state.scenario_note = (source, notes, scenario.to_dict())
            st.rerun()
        if note := st.session_state.get("scenario_note"):
            st.caption(f"Interpreted by: {'Gemini' if note[0] == 'gemini' else 'rule-based keywords'}")
            for n in note[1]:
                st.warning(n)
            st.json(note[2])


def render() -> None:
    st.title("Scenario Lab")
    orch = get_orchestrator()
    builtin = orch.scenario.available()
    st.markdown("Scenarios scale rainfall, yields, input costs, prices and water. The GA's resilience score is "
                "the average share of normal-condition profit a strategy keeps across the selected scenarios.")
    st.markdown('<span style="display:inline-block;background:#f1f1f1;color:#000;padding:4px 9px;border-radius:6px;font-weight:600;">Built-in scenarios used for optimisation</span>', unsafe_allow_html=True)
    ids = st.multiselect("Built-in scenarios used for optimisation", list(builtin), st.session_state.scenario_ids,
                         format_func=lambda s: builtin[s].scenario_name, label_visibility="collapsed")
    st.session_state.scenario_ids = ids
    st.caption("Normal conditions are always included as the baseline.")

    st.subheader("Custom scenarios")
    _custom_builder()
    for i, scenario in enumerate(list(st.session_state.custom_scenarios)):
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"**{scenario.scenario_name}**: " + ", ".join(
            f"{PARAM_LABELS[k]} {getattr(scenario, k):.2f}" for k in PARAM_LABELS))
        if c2.button("Remove", key=f"rm_{scenario.scenario_id}_{i}"):
            st.session_state.custom_scenarios.pop(i)
            st.rerun()

    scenarios = orch.scenario.select(ids, st.session_state.custom_scenarios)
    frame = pd.DataFrame([s.to_dict() for s in scenarios])
    st.subheader("Selected scenarios")
    st.dataframe(frame[["scenario_name", *PARAM_LABELS, "description"]], width="stretch", hide_index=True)
    long = frame.melt(id_vars="scenario_name", value_vars=list(PARAM_LABELS), var_name="parameter")
    long["parameter"] = long["parameter"].map(PARAM_LABELS)
    fig = px.bar(long, x="parameter", y="value", color="scenario_name", barmode="group",
                 title="Scenario multipliers (1.0 = normal)")
    fig.add_hline(y=1.0, line_dash="dot", line_color="#64748B")
    st.plotly_chart(style_figure(fig), width="stretch")

    st.subheader("Stress-test the best strategy")
    result = st.session_state.result
    if result is None:
        st.info("Run the optimiser in **Evolution Lab** first; then you can test its best strategy here.")
        return
    if st.button("Evaluate best strategy under these scenarios", type="primary"):
        evaluation = orch.evaluate_strategy(result["farm_profile"], result["best_strategy"]["genes"], scenarios)
        st.session_state.scenario_eval = {"table": evaluation["table"], "resilience": evaluation["resilience"],
                                          "retention": evaluation["retention"]}
    evaluation = st.session_state.scenario_eval
    if evaluation is None:
        return
    table = evaluation["table"]
    st.metric("Resilience (mean profit retention)", f"{evaluation['resilience']:.2f}")
    fig = px.bar(table, x="scenario", y="net_profit", text_auto=".0f", title="Net profit by scenario (USD)",
                 color_discrete_sequence=[ACCENT])
    st.plotly_chart(style_figure(fig), width="stretch")
    st.dataframe(table.drop(columns=["scenario_id"]), width="stretch", hide_index=True,
                 column_config={"net_profit": st.column_config.NumberColumn(format="$%.0f"),
                                "revenue": st.column_config.NumberColumn(format="$%.0f"),
                                "total_cost": st.column_config.NumberColumn(format="$%.0f"),
                                "total_yield_t": st.column_config.NumberColumn(format="%.1f"),
                                "water_use_m3": st.column_config.NumberColumn(format="%.0f"),
                                "final_soil_health": st.column_config.NumberColumn(format="%.1f"),
                                "irrigation_supply_share": st.column_config.NumberColumn(format="%.2f")})
