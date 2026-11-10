"""Research report: rule-based findings plus an optional Gemini-written narrative."""
from __future__ import annotations

import streamlit as st

from services.report_service import build_markdown, save_report


def render(orchestrator, report) -> None:
    gemini = orchestrator.research_agent.gemini
    if gemini.available:
        st.caption(f"Gemini is configured ({gemini.model}).")
        if st.button("Write narrative with Gemini", type="primary"):
            with st.spinner("Asking Gemini…"):
                orchestrator.write_narrative(report)
            if report.narrative_source != "gemini":
                st.warning(f"Gemini did not return a narrative ({gemini.last_error or 'empty response'}); "
                           "showing rule-based findings only.")
    else:
        st.info("Add `GEMINI_API_KEY` to `.env` to get a Gemini-written narrative. "
                "The report below uses the built-in rule-based research agent.")

    markdown = build_markdown(report)
    st.markdown(markdown)
    c1, c2 = st.columns(2)
    c1.download_button("Download report (Markdown)", markdown.encode(),
                       file_name=f"agrigenesis_report_{report.context.farm['farm_id']}.md",
                       mime="text/markdown")
    if c2.button("Save report to outputs/reports"):
        st.success(f"Saved {save_report(report, markdown=markdown).name}")
