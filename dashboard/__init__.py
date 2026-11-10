"""Streamlit dashboard pages and shared UI helpers."""
from __future__ import annotations

import streamlit as st

from agents.orchestrator import Orchestrator
from config import DEFAULT_WEIGHTS, GAConfig
from services.data_loader import load_sample_farm

ACCENT = "#8B5CF6"
ACCENT_LIGHT = "#C4B5FD"
MUTED = "#64748B"
PALETTE = [ACCENT, "#A78BFA", "#38BDF8", "#94A3B8", "#F472B6", "#FBBF24", "#34D399", "#F87171", "#E2E8F0"]

CSS = f"""
<style>
.block-container {{padding-top: 2rem; max-width: 1300px;}}
div[data-testid="stMetric"] {{background: #1A1C25; border: 1px solid #2A2D3A; border-radius: 10px;
  padding: 12px 16px;}}
div[data-testid="stMetricValue"] {{font-size: 1.5rem;}}
h1, h2, h3 {{letter-spacing: -0.01em;}}
.ag-badge {{display:inline-block; padding:2px 10px; border-radius:999px; background:{ACCENT}22;
  color:{ACCENT_LIGHT}; border:1px solid {ACCENT}55; font-size:0.8rem; margin-right:6px;}}
.ag-note {{color:#9CA3AF; font-size:0.85rem;}}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def style_figure(fig, height: int = 360):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      colorway=PALETTE, height=height, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    return fig


@st.cache_resource(show_spinner=False)
def get_orchestrator() -> Orchestrator:
    """One orchestrator per server process; datasets are loaded once and cached."""
    return Orchestrator()


def init_state() -> None:
    defaults = {
        "farm_input": {k: v for k, v in load_sample_farm().items() if k not in ("data_note", "weights")},
        "farm_profile": None,
        "agronomy": None,
        "farm_errors": [],
        "weights": dict(DEFAULT_WEIGHTS),
        "ga_config": GAConfig(),
        "scenario_ids": list(get_orchestrator().scenario.available()),
        "custom_scenarios": [],
        "use_gemini": True,
        "result": None,
        "result_path": None,
        "scenario_eval": None,
        "nl_parse": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def badge(text: str) -> str:
    return f'<span class="ag-badge">{text}</span>'


def require_result() -> dict | None:
    result = st.session_state.get("result")
    if result is None:
        st.info("No optimisation results yet. Validate the farm in **Farm Setup**, then run the "
                "optimiser in **Evolution Lab**.")
    return result


def plan_pivot(plan: list[dict]):
    """Plot x season grid of crop names with management levels."""
    import pandas as pd

    frame = pd.DataFrame(plan)
    frame["cell"] = frame.apply(lambda r: r["crop"] if r["crop_id"] == "FALLOW" else
                                f"{r['crop']} (W {r['water_level']:.2f}, F {r['fertilizer_level']:.2f}, "
                                f"{r['planting_window']})", axis=1)
    pivot = frame.pivot(index="plot", columns="season", values="cell")
    order = [s for s in ("monsoon", "winter", "summer") if s in pivot.columns]
    pivot = pivot[order]
    pivot.index = [f"Plot {i}" for i in pivot.index]
    return pivot
