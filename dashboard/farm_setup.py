"""Farm Setup page: structured form, natural-language input, samples and agronomy validation."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import DEFAULT_WEIGHTS, SEASONS
from dashboard import get_orchestrator
from services.data_loader import farm_row_to_input, load_sample_farm
from services.validation_service import FarmValidationError, validate_weights


def _samples() -> dict[str, dict]:
    datasets = get_orchestrator().datasets
    sample = {k: v for k, v in load_sample_farm().items() if k not in ("data_note", "weights")}
    options = {f"{sample['farm_name']} (sample_farm.json)": sample}
    for _, row in datasets.farms.iterrows():
        options[f"{row['farm_name']} (farms.csv)"] = farm_row_to_input(row)
    return options


def _natural_language() -> None:
    orch = get_orchestrator()
    with st.expander("Describe your farm in words", expanded=False):
        text = st.text_area("Farm description", placeholder="e.g. My farm called Sunny Acres has 3 hectares in "
                            "3 plots of clay loam, pH 6.8, 15000 m3 of water and a budget of $8,000. "
                            "We grow in monsoon (1200 mm rain) and winter. I prefer rice and lentil.")
        if st.button("Parse description", disabled=not text.strip()):
            st.session_state.nl_parse = orch.farm_input.from_text(text, st.session_state.use_gemini)
        parsed = st.session_state.nl_parse
        if parsed is None:
            return
        st.caption(f"Parsed by: {'Gemini' if parsed.source == 'gemini' else 'rule-based parser'}")
        st.json(parsed.values)
        for note in parsed.notes:
            st.warning(note)
        if parsed.missing:
            st.warning("Not found in the text (current form values are kept, please check them): "
                       + ", ".join(parsed.missing))
        if st.button("Apply parsed values to the form"):
            st.session_state.farm_input = {**st.session_state.farm_input, **parsed.values}
            st.session_state.farm_profile = None
            st.session_state.nl_parse = None
            st.rerun()


def _form() -> None:
    orch = get_orchestrator()
    data = st.session_state.farm_input
    crops = orch.datasets.crops
    crop_names = dict(zip(crops["crop_id"], crops["crop_name"]))
    soils = orch.datasets.soils["soil_type"].tolist()
    with st.form("farm_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Farm name", data.get("farm_name", ""))
        area = c2.number_input("Total land (ha)", 0.1, 1000.0, float(data.get("total_area_ha", 1.0)), 0.5)
        plots = c3.number_input("Number of plots", 1, 20, int(data.get("n_plots", 1)))
        c1, c2, c3 = st.columns(3)
        soil = c1.selectbox("Soil type", soils, soils.index(data["soil_type"]) if data.get("soil_type") in soils else 0)
        ph = c2.number_input("Soil pH", 3.0, 10.0, float(data.get("soil_ph", 6.5)), 0.1)
        health = c3.number_input("Soil health index (0-100)", 0.0, 100.0, float(data.get("soil_health_index", 60.0)), 1.0)
        c1, c2 = st.columns(2)
        water = c1.number_input("Available irrigation water (m3, whole plan)", 0.0, 10_000_000.0,
                                float(data.get("available_water_m3", 0.0)), 500.0)
        budget = c2.number_input("Budget (USD, whole plan)", 0.0, 10_000_000.0, float(data.get("budget_usd", 0.0)), 500.0)
        st.markdown('<span style="display:inline-block;background:#f1f1f1;color:#000;padding:4px 9px;border-radius:6px;font-weight:600;">Seasons to plan</span>', unsafe_allow_html=True)
        seasons = st.multiselect("Seasons to plan", list(SEASONS), [s for s in data.get("seasons", []) if s in SEASONS],
                                 format_func=lambda s: SEASONS[s]["name"], label_visibility="collapsed")
        rain_cols = st.columns(len(SEASONS))
        rainfall = {s: col.number_input(f"{SEASONS[s]['name']} rainfall (mm)", 0.0, 5000.0,
                                        float((data.get("rainfall_mm") or {}).get(s) or 0.0), 10.0)
                    for col, s in zip(rain_cols, SEASONS)}
        c1, c2 = st.columns(2)
        preferred = c1.multiselect("Preferred crops (optional)", list(crop_names), data.get("preferred_crops", []),
                                   format_func=crop_names.get)
        excluded = c2.multiselect("Excluded crops (optional)", list(crop_names), data.get("excluded_crops", []),
                                  format_func=crop_names.get)
        st.markdown("**Optimisation priorities** (normalised to sum to 1)")
        wcols = st.columns(5)
        weights = {k: wcols[i].slider(k.capitalize(), 0.0, 1.0, float(st.session_state.weights[k]), 0.05)
                   for i, k in enumerate(DEFAULT_WEIGHTS)}
        submitted = st.form_submit_button("Validate farm", type="primary")
    if not submitted:
        return
    farm = {"farm_name": name, "total_area_ha": area, "n_plots": int(plots), "soil_type": soil, "soil_ph": ph,
            "soil_health_index": health, "available_water_m3": water, "budget_usd": budget, "seasons": seasons,
            "rainfall_mm": {s: rainfall[s] for s in seasons}, "preferred_crops": preferred,
            "excluded_crops": excluded}
    st.session_state.farm_input = farm
    try:
        st.session_state.weights = validate_weights(weights)
        profile, agronomy, _ = orch.prepare(farm)
    except (FarmValidationError, ValueError) as exc:
        st.session_state.farm_profile, st.session_state.agronomy = None, None
        st.session_state.farm_errors = getattr(exc, "errors", [str(exc)])
        return
    st.session_state.farm_profile, st.session_state.agronomy = profile.to_dict(), agronomy
    st.session_state.farm_errors = []


def _validation() -> None:
    for error in st.session_state.farm_errors:
        st.error(error)
    agronomy = st.session_state.agronomy
    if st.session_state.farm_profile is None or agronomy is None:
        return
    st.success(f"Farm validated: {st.session_state.farm_profile['farm_name']}. Weights: "
               + ", ".join(f"{k} {v:.2f}" for k, v in st.session_state.weights.items()))
    for m in agronomy.messages:
        {"error": st.error, "warning": st.warning}.get(m["level"], st.info)(m["message"])
    st.subheader("Agronomy check")
    for season, crops in agronomy.feasible_options.items():
        names = [get_orchestrator().datasets.crops.set_index("crop_id").loc[c, "crop_name"] for c in crops]
        st.markdown(f"**{SEASONS[season]['name']}**: {', '.join(names) or 'none (fallow)'}")
    table = agronomy.table[["season", "crop_name", "feasible", "season_ok", "soil_ok", "ph_status", "valid_windows",
                            "irrigation_need_m3_per_plot", "full_input_cost_per_plot", "notes"]]
    st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)


def render() -> None:
    st.title("Farm Setup")
    samples = _samples()
    c1, c2 = st.columns([3, 1])
    choice = c1.selectbox("Load sample farm", list(samples))
    if c2.button("Load sample", width="stretch"):
        st.session_state.farm_input = dict(samples[choice])
        st.session_state.farm_profile = None
        st.rerun()
    _natural_language()
    _form()
    _validation()
