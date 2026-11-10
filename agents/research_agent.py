"""Research Agent: explains the optimised strategy from actual simulation numbers."""
from __future__ import annotations

import re

from config import SYNTHETIC_DATA_NOTICE
from services.gemini_service import GeminiService
from utils.helpers import money

NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _numbers_in(obj) -> set[float]:
    found: set[float] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            found |= _numbers_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found |= _numbers_in(v)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        found.add(float(obj))
    elif isinstance(obj, str):
        found |= {float(m.replace(",", "")) for m in NUMBER.findall(obj) if m.replace(",", "").strip("-.")}
    return found


def unverified_numbers(text: str, facts: dict) -> list[str]:
    """Numbers in ``text`` that do not match any fact (within 1% or common rounding)."""
    known = _numbers_in(facts)
    suspicious = []
    for token in NUMBER.findall(text):
        clean = token.replace(",", "").rstrip(".")
        try:
            value = float(clean)
        except ValueError:
            continue
        if abs(value) <= 12 and value == int(value):
            continue  # small counts like plots, seasons, list numbering
        ok = any(abs(value - k) <= max(1.0, 0.01 * abs(k)) or abs(value - k * 100) <= 1.0 for k in known)
        if not ok:
            suspicious.append(token)
    return sorted(set(suspicious))


class ResearchAgent:
    def __init__(self, gemini: GeminiService | None = None):
        self.gemini = gemini or GeminiService()

    def deterministic_explanation(self, facts: dict) -> str:
        m, c = facts["best_metrics"], facts["fitness_components"]
        lines = [f"### Summary\nThe optimiser selected a plan for **{facts['farm']['farm_name']}** with a "
                 f"fitness of {facts['best_fitness']:.3f}. Under normal conditions it earns "
                 f"{money(m['net_profit'])} net profit on {money(m['revenue'])} revenue and "
                 f"{money(m['total_cost'])} cost, uses {m['water_use_m3']:,.0f} m3 of "
                 f"{m['water_available_m3']:,.0f} m3 irrigation water and ends with a soil-health index "
                 f"of {m['final_soil_health']:.1f} (change {m['soil_health_change']:+.1f})."]
        lines.append("### Why this crop allocation")
        for season, crops in facts["allocation"].items():
            lines.append(f"- **{season}**: " + ", ".join(f"{crop} on {n} plot(s)" for crop, n in crops.items()))
        strongest = max(c, key=lambda k: facts["weights"][k] * c[k])
        weakest = min(c, key=c.get)
        lines.append("### Trade-offs")
        lines.append(f"- Normalised scores: " + ", ".join(f"{k} {v:.2f}" for k, v in c.items()) + ".")
        lines.append(f"- The largest weighted contribution comes from **{strongest}**; the weakest score is "
                     f"**{weakest}**, which is where this plan gives ground.")
        lines.append("### Performance under adverse scenarios")
        for name, profit in facts["scenario_profits"].items():
            lines.append(f"- {name}: {money(profit)} net profit")
        lines.append(f"- Resilience score (mean profit retention vs. normal): {c['resilience']:.2f}")
        lines.append("### Assumptions and uncertainty")
        lines.append(f"- {SYNTHETIC_DATA_NOTICE}")
        lines.append("- Results come from a simplified deterministic model; real outcomes vary with local "
                     "conditions, pests, markets and management.")
        return "\n".join(lines)

    def explain(self, facts: dict, use_gemini: bool = True) -> dict:
        """Gemini explanation when available, otherwise the deterministic one."""
        fallback = self.deterministic_explanation(facts)
        result = {"source": "deterministic", "text": fallback, "deterministic_text": fallback,
                  "warnings": [], "model": None}
        if not (use_gemini and self.gemini.available):
            if use_gemini:
                result["warnings"].append("Gemini API key not configured; showing the rule-based explanation.")
            return result
        text = self.gemini.explain_strategy(facts)
        if not text:
            result["warnings"].append(f"Gemini explanation unavailable ({self.gemini.last_error}); "
                                      "showing the rule-based explanation.")
            return result
        result.update(source="gemini", text=text, model=self.gemini.model)
        flagged = unverified_numbers(text, facts)
        if flagged:
            result["warnings"].append("These numbers in the AI text could not be matched to simulation "
                                      f"results; rely on the tables instead: {', '.join(flagged[:10])}")
        return result
