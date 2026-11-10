"""Builds the Markdown research report from the orchestrator result."""
from __future__ import annotations

from pathlib import Path

from config import REPORT_DIR, SEASONS
from utils.helpers import money, timestamp

COST_KEYS = ["seed_cost", "fertilizer_cost", "labor_cost", "irrigation_cost"]


def cost_breakdown(gene_results: list[dict]) -> dict[str, float]:
    return {k: sum(r[k] for r in gene_results) for k in COST_KEYS}


def risks_and_tradeoffs(result: dict) -> list[str]:
    """Deterministic observations derived from the simulation numbers."""
    best = result["best_strategy"]
    m, c = best["metrics"], best["components"]
    notes = []
    profits = best["scenario_profits"]
    normal = profits.get("normal", 0.0)
    for sid, profit in profits.items():
        if sid != "normal" and normal > 0 and profit < 0.6 * normal:
            name = result["scenarios"].get(sid, {}).get("scenario_name", sid)
            notes.append(f"{name} cuts profit to {money(profit)} ({profit / normal:.0%} of normal).")
    if m["water_available_m3"] > 0 and m["water_use_m3"] / m["water_available_m3"] > 0.9:
        notes.append("Irrigation uses over 90% of the available water, leaving little buffer.")
    if m["soil_health_change"] < 0:
        notes.append(f"Soil health declines by {abs(m['soil_health_change']):.1f} points over the plan.")
    if m["total_cost"] > 0.9 * result["farm_profile"]["budget_usd"]:
        notes.append("Planned costs use over 90% of the budget.")
    fallow = sum(1 for g in best["genes"] if g["crop_id"] == "FALLOW")
    if fallow:
        notes.append(f"{fallow} plot-season slot(s) are left fallow because of resource limits or low returns.")
    weakest = min(c, key=c.get)
    notes.append(f"Weakest objective: {weakest} (score {c[weakest]:.2f}).")
    return notes


def build_markdown_report(result: dict) -> str:
    farm, best = result["farm_profile"], result["best_strategy"]
    m = best["metrics"]
    lines = [f"# AgriGenesis report: {farm['farm_name']}", "",
             f"> {result['assumptions'][0]}", "",
             "## Farm", f"- Area: {farm['total_area_ha']} ha in {farm['n_plots']} plots",
             f"- Soil: {farm['soil_type']} (pH {farm['soil_ph']}, health {farm['soil_health_index']})",
             f"- Water: {farm['available_water_m3']:,.0f} m3, budget {money(farm['budget_usd'])}",
             f"- Seasons: {', '.join(SEASONS[s]['name'] for s in farm['seasons'])}", "",
             "## Optimised plan", f"Fitness {best['fitness']:.4f} after {len(result['fitness_history'])} generations.", "",
             "| Plot | Season | Crop | Water | Fertilizer | Window |", "|---|---|---|---|---|---|"]
    for p in best["plan"]:
        lines.append(f"| {p['plot']} | {p['season']} | {p['crop']} | {p['water_level']:.2f} | "
                     f"{p['fertilizer_level']:.2f} | {p['planting_window']} |")
    costs = cost_breakdown(result["simulation_metrics"]["gene_results"])
    lines += ["", "## Economics (normal scenario)",
              f"- Revenue {money(m['revenue'])}, cost {money(m['total_cost'])}, net profit {money(m['net_profit'])}",
              "- Costs: " + ", ".join(f"{k.replace('_', ' ')} {money(v)}" for k, v in costs.items()),
              f"- Yield {m['total_yield_t']:.1f} t, water {m['water_use_m3']:,.0f} m3, final soil health "
              f"{m['final_soil_health']:.1f}", "", "## Scenario performance",
              "| Scenario | Net profit |", "|---|---|"]
    for sid, profit in best["scenario_profits"].items():
        lines.append(f"| {result['scenarios'].get(sid, {}).get('scenario_name', sid)} | {money(profit)} |")
    lines += ["", "## Risks and trade-offs"] + [f"- {n}" for n in risks_and_tradeoffs(result)]
    report = result.get("research_report", {})
    lines += ["", f"## Explanation ({report.get('source', 'n/a')})", report.get("text", "")]
    lines += ["", "## Assumptions"] + [f"- {a}" for a in result["assumptions"]]
    return "\n".join(lines)


def save_report(markdown: str, directory: Path = REPORT_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"agrigenesis_report_{timestamp()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
