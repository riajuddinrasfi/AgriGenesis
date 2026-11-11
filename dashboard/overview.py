"""Overview page: a bento dashboard of the farm and the latest optimisation results."""
from __future__ import annotations

import streamlit as st

from config import SEASONS
from dashboard import get_orchestrator, plan_pivot, result_is_stale
from dashboard.bento import farm_data, render_bento, result_data
from simulation.weather_simulator import Scenario
from utils.helpers import money


def _gene_results(result: dict) -> dict[str, list[dict]]:
    """Normal-scenario per-plot rows for every ranked strategy, simulated once per result."""
    cached = st.session_state.get("_bento_genes")
    if cached and cached[0] is result:
        return cached[1]
    normal = [Scenario(**result["scenarios"]["normal"])]
    rows = {"#1": result["simulation_metrics"]["gene_results"]}
    for record in result["ranked_strategies"]:
        label = f"#{record['rank']}"
        if label not in rows:
            rows[label] = get_orchestrator().evaluate_strategy(
                result["farm_profile"], record["genes"], normal)["results"]["normal"].gene_results
    st.session_state["_bento_genes"] = (result, rows)
    return rows


def render() -> None:
    st.markdown("**An Evolutionary Agriculture Strategy Laboratory**: a Genetic Algorithm evolves whole-farm "
                "strategies, scored by a deterministic simulator under several scenarios.")
    gemini = get_orchestrator().gemini.available
    result = st.session_state.result
    farm = st.session_state.farm_profile or st.session_state.farm_input

    if result is None:
        if st.session_state.farm_profile is None:
            st.warning("The farm below is not validated yet. Open **Farm Setup** and click *Validate farm*.")
        else:
            st.info("Not optimised yet. Run the Genetic Algorithm in **Evolution Lab**.")
        render_bento(farm_data(farm, st.session_state.farm_profile is not None, gemini))
        st.caption("Seasons: " + ", ".join(SEASONS[s]["name"] for s in farm.get("seasons", []) if s in SEASONS))
        return

    stale = result_is_stale()
    if stale:
        st.warning("The farm, priorities or scenarios changed since this run; click **Evolve My Farm** in "
                   "Evolution Lab to update the results.")
    render_bento(result_data(result, _gene_results(result), gemini, stale))

    m, opt = result["best_strategy"]["metrics"], result["optimization"]
    cols = st.columns(5)
    cols[0].metric("Net profit", money(m["net_profit"]))
    cols[1].metric("Best fitness", f"{result['best_fitness']:.4f}")
    cols[2].metric("Generations", len(result["fitness_history"]))
    cols[3].metric("Strategies evaluated", f"{opt['evaluations']:,}")
    cols[4].metric("Runtime", f"{opt['runtime_s']:.1f} s")
    st.markdown("**Best strategy**")
    st.dataframe(plan_pivot(result["best_strategy"]["plan"]), width="stretch")
