"""Turns optimisation results into findings: rule-based insights plus an optional Gemini narrative."""
from __future__ import annotations

import pandas as pd

from services.gemini_service import GeminiService
from simulation.farm_simulator import FarmContext


class ResearchAgent:
    def __init__(self, gemini: GeminiService | None = None):
        self.gemini = gemini or GeminiService()

    def insights(self, context: FarmContext, plan: pd.DataFrame, comparison: pd.DataFrame,
                 scenarios: pd.DataFrame, usage: pd.DataFrame, violations: pd.DataFrame) -> list[str]:
        notes = []
        ga = comparison[comparison["strategy"] == "Genetic algorithm"].iloc[0]
        others = comparison[comparison["strategy"] != "Genetic algorithm"]
        if not others.empty:
            best_other = others.sort_values("fitness", ascending=False).iloc[0]
            gain = ga["expected_profit"] - best_other["expected_profit"]
            notes.append(
                f"The optimised plan's expected profit is ${ga['expected_profit']:,.0f}, "
                f"{'+' if gain >= 0 else '-'}${abs(gain):,.0f} versus the best baseline "
                f"({best_other['strategy']}).")

        counts = pd.Series(plan.to_numpy().ravel()).value_counts()
        planted = counts.drop("Fallow", errors="ignore")
        if not planted.empty:
            notes.append("Most used crops across plot-seasons: "
                         + ", ".join(f"{c} ({n})" for c, n in planted.head(3).items()) + ".")
        families = context.crops.set_index("crop")["family"]
        legumes = sum(n for c, n in planted.items() if families.get(c) == "Fabaceae")
        share = legumes / max(counts.sum(), 1)
        notes.append(f"Legumes fill {share:.0%} of plot-seasons, restoring soil nitrogen for the next crop."
                     if share else "No legumes are planned; soil nitrogen relies on fertiliser and fallow.")
        if counts.get("Fallow", 0):
            notes.append(f"{counts['Fallow']} plot-season(s) are left fallow to save inputs or rebuild soil.")

        ordered = scenarios.sort_values("profit")
        notes.append(f"Worst scenario is '{ordered.iloc[0]['scenario']}' with profit "
                     f"${ordered.iloc[0]['profit']:,.0f}; the best is '{ordered.iloc[-1]['scenario']}'.")
        if (scenarios["profit"] < 0).any():
            notes.append("The plan loses money in at least one scenario; consider a lower risk tolerance.")
        for col, cap, label in (("cost", "budget", "Budget"), ("labor_days", "labor_capacity", "Labour"),
                                ("irrigation_m3", "irrigation_capacity", "Irrigation")):
            util = (usage[col] / usage[cap]).max() if (usage[cap] > 0).all() else 0
            if util >= 0.9:
                notes.append(f"{label} is a binding constraint (peak use {util:.0%}).")
        notes.append(f"{len(violations)} constraint issue(s) remain; see the Constraints table."
                     if not violations.empty
                     else "The plan satisfies all budget, labour, suitability and rotation rules.")
        return notes

    @staticmethod
    def summary(context: FarmContext, plan: pd.DataFrame, comparison: pd.DataFrame,
                scenarios: pd.DataFrame, risk: dict, insights: list[str]) -> dict:
        farm = context.farm
        return {
            "farm": {k: farm[k] for k in ("name", "region", "soil_type", "soil_ph", "soil_nitrogen",
                                          "num_plots", "plot_area_ha", "budget", "labor_days",
                                          "irrigation_m3", "risk_tolerance")},
            "plan": plan.to_dict(orient="index"),
            "strategy_comparison": comparison.round(0).to_dict(orient="records"),
            "scenario_results": scenarios.round(2).to_dict(orient="records"),
            "monte_carlo_risk": {k: round(v, 3) for k, v in risk.items()},
            "rule_based_insights": insights,
        }

    def narrative(self, summary: dict) -> tuple[str | None, str]:
        """(Markdown narrative, source) where source is 'gemini' or 'rule-based'."""
        text = self.gemini.research_narrative(summary)
        return (text, "gemini") if text else (None, "rule-based")
