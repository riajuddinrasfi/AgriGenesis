"""AgriGenesis Streamlit entry point: `streamlit run app.py`."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="AgriGenesis", page_icon=":seedling:", layout="wide")

from dashboard import (apply_theme, evolution_lab, farm_setup, init_state, overview,  # noqa: E402
                       research_report, scenario_lab, strategy_comparison)

PAGES = {
    "Overview": overview.render,
    "Farm Setup": farm_setup.render,
    "Scenario Lab": scenario_lab.render,
    "Evolution Lab": evolution_lab.render,
    "Strategy Comparison": strategy_comparison.render,
    "Research Report": research_report.render,
}


def main() -> None:
    apply_theme()
    init_state()
    with st.sidebar:
        st.markdown("## AgriGenesis")
        st.caption("Evolutionary Agriculture Strategy Laboratory")
        page = st.radio("Navigate", list(PAGES), key="page", label_visibility="collapsed")
        st.divider()
        profile = st.session_state.farm_profile
        st.caption(f"Farm: {profile['farm_name'] if profile else 'not validated'}")
        result = st.session_state.result
        st.caption(f"Best fitness: {result['best_fitness']:.4f}" if result else "Optimiser: not run")
    PAGES[page]()


main()
