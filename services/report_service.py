"""Markdown research reports and exports written to ``outputs/``."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import REPORT_DIR
from utils.helpers import ensure_dir, format_money, slugify, timestamp


def _table(df: pd.DataFrame, index: bool = False) -> str:
    df = df.reset_index() if index else df
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = [f"{v:,.0f}" if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_markdown(report) -> str:
    """Full research report for a ``PlanningReport``."""
    farm, best, risk = report.context.farm, report.ga_result.best, report.risk
    plan = report.plan.copy()
    plan.index.name = "Plot"
    parts = [
        f"# AgriGenesis research report: {farm['name']}",
        f"*{farm['region']} · {int(farm['num_plots'])} plots × {farm['plot_area_ha']} ha · "
        f"soil {farm['soil_type']}, pH {farm['soil_ph']}*",
        "## Key results",
        f"- Expected profit: **{format_money(best.expected_profit)}**",
        f"- Worst-case scenario profit: {format_money(best.worst_case_profit)}",
        f"- Monte Carlo 5th percentile: {format_money(risk['p5'])}; "
        f"probability of loss {risk['loss_probability']:.1%}",
        f"- Feasible: {'yes' if best.feasible else 'no'}",
        "## Recommended crop plan",
        _table(plan, index=True),
        "## Findings",
        *[f"- {note}" for note in report.insights],
    ]
    if report.narrative:
        parts += ["## Analyst narrative (Gemini)", report.narrative]
    parts += [
        "## Scenario results",
        _table(report.scenarios[["scenario", "probability", "revenue", "cost", "profit"]]
               .assign(probability=lambda d: d["probability"].map("{:.0%}".format))),
        "## Strategy comparison",
        _table(report.comparison[["strategy", "fitness", "expected_profit", "worst_case_profit",
                                  "profit_std", "feasible"]]),
    ]
    if report.warnings:
        parts += ["## Data warnings", *[f"- {w}" for w in report.warnings]]
    return "\n\n".join(parts) + "\n"


def save_report(report, directory: str | Path = REPORT_DIR, markdown: str | None = None) -> Path:
    path = ensure_dir(directory) / f"{slugify(report.context.farm['farm_id'])}-report-{timestamp()}.md"
    path.write_text(markdown or build_markdown(report), encoding="utf-8")
    return path
