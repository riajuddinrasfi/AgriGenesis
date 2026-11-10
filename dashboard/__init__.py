"""Streamlit dashboard pages. Each module exposes ``render(...)`` for one tab of ``app.py``."""
import plotly.express as px

PALETTE = px.colors.qualitative.Safe
TEMPLATE = "plotly_white"
STRETCH = {"width": "stretch"}
