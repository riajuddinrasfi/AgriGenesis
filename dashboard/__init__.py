"""Streamlit dashboard pages and shared UI helpers."""
from __future__ import annotations

import streamlit as st

from agents.orchestrator import Orchestrator
from config import DEFAULT_WEIGHTS, GAConfig
from services.data_loader import load_sample_farm

ACCENT = "#E8FF1F"
ACCENT_LIGHT = "#A9B2FF"
MUTED = "#8A8A94"
PALETTE = [ACCENT, "#A9B2FF", "#FFB37A", "#FF5FA2", "#5CD6A0", "#6D7DFF", "#F4FFB8", "#FFD0E6", "#FFFFFF"]

# Black canvas, glass cards and a lime accent, matching the Overview bento (dashboard/assets/farm_bento.css).
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');
html, body, .stApp, [data-testid="stSidebar"], button, input, textarea, select {{
  font-family: Geist, ui-sans-serif, system-ui, -apple-system, sans-serif;}}
code, pre, [data-testid="stMetricValue"] {{font-family: "Geist Mono", ui-monospace, monospace;}}
.stApp {{background: #000;}}
.block-container {{padding-top: 3.5rem; max-width: 1360px;}}
[data-testid="stSidebar"] {{background: #0b0b0c; border-right: 1px solid rgba(255,255,255,.08);}}
h1, h2, h3 {{letter-spacing: -0.03em; font-weight: 500;}}
div[data-testid="stMetric"] {{background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.12);
  border-radius: 22px; padding: 16px 20px; backdrop-filter: blur(18px);}}
div[data-testid="stMetricLabel"] p {{color: rgba(255,255,255,.56); font-size: .8rem; font-weight: 500;}}
div[data-testid="stMetricValue"] {{font-size: 1.55rem; letter-spacing: -0.04em;}}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] details, [data-testid="stForm"] {{
  border-radius: 22px !important; border-color: rgba(255,255,255,.12) !important; background: rgba(255,255,255,.03);}}
[data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPlotlyChart"] {{border-radius: 18px; overflow: hidden;}}
[data-testid="stPlotlyChart"] {{background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1); padding: 6px;}}
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {{border-radius: 999px;
  border: 1px solid rgba(255,255,255,.16); font-weight: 600;}}
.stButton button[kind^="primary"], [data-testid="stFormSubmitButton"] button[kind^="primary"],
[data-testid="stFormSubmitButton"] button {{
  background: {ACCENT}; border-color: {ACCENT}; color: #0b0b0c;}}
span[data-baseweb="tag"], span[data-baseweb="tag"] * {{color: #0b0b0c !important; font-weight: 600;}}
.stButton button[kind^="primary"]:hover, [data-testid="stFormSubmitButton"] button:hover {{background: #F4FFB8; border-color: #F4FFB8; color: #0b0b0c;}}
[data-testid="stAlert"] {{border-radius: 18px;}}
.ag-badge {{display:inline-flex; align-items:center; gap:6px; height:24px; padding:0 10px; border-radius:12px;
  background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.12); color:rgba(255,255,255,.72);
  font: 600 11px "Geist Mono", monospace; margin:0 6px 6px 0;}}
.ag-badge::before {{content:""; width:6px; height:6px; border-radius:50%; background:{ACCENT}; box-shadow:0 0 8px {ACCENT};}}
.ag-note {{color: rgba(255,255,255,.45); font-size:0.85rem;}}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def style_figure(fig, height: int = 360):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Geist, sans-serif", color="rgba(255,255,255,.75)"),
                      colorway=PALETTE, height=height,
                      margin=dict(l=10, r=10, t=90 if fig.layout.title.text else 40, b=10),
                      title=dict(y=0.98, yanchor="top"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""))
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
        "result_inputs": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def current_inputs() -> dict:
    """What the next optimisation would use; compared with the inputs of the stored result."""
    return {"farm": st.session_state.farm_profile, "weights": dict(st.session_state.weights),
            "scenario_ids": list(st.session_state.scenario_ids),
            "custom": [s.to_dict() for s in st.session_state.custom_scenarios]}


def result_is_stale() -> bool:
    return st.session_state.get("result") is not None and st.session_state.get("result_inputs") != current_inputs()


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
