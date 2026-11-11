"""Overview bento: turns farm inputs and optimiser results into data for the farm_bento web component."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import streamlit as st

from config import SEASONS, SYNTHETIC_DATA_NOTICE

ASSETS = Path(__file__).parent / "assets"
MIX_COLORS = ["#FFFFFF", "#A9B2FF", "#FFB37A", "rgba(255,255,255,.35)"]
COST_LABELS = {"labor_cost": "Labor", "fertilizer_cost": "Fertilizer", "seed_cost": "Seed",
               "irrigation_cost": "Irrigation"}
SCENARIO_SHORT = {"normal": "Normal", "drought": "Drought", "excess_rainfall": "Flood",
                  "input_price_shock": "Inputs+", "market_price_drop": "Price−"}
SEASON_SHORT = {"monsoon": "Mon", "winter": "Win", "summer": "Sum"}


@st.cache_resource(show_spinner=False)
def _component():
    return st.components.v2.component(
        "agrigenesis_farm_bento",
        css=(ASSETS / "farm_bento.css").read_text(encoding="utf-8"),
        js=(ASSETS / "farm_bento.js").read_text(encoding="utf-8"),
    )


def _go_to_evolution() -> None:
    st.session_state.page = "Evolution Lab"


def render_bento(data: dict, key: str = "farm_bento") -> None:
    _component()(data=data, key=key, width="stretch", height="content", on_go_change=_go_to_evolution)


def _season_name(season: str) -> str:
    return SEASONS.get(season, {}).get("name", season.title()).split(" (")[0]


def _short_scenario(scenario_id: str, name: str) -> str:
    return SCENARIO_SHORT.get(scenario_id) or (name.split()[0][:8] if name else scenario_id[:8])


def _mix(allocation: dict, slots: int) -> tuple[list[dict], float]:
    counts: dict[str, int] = defaultdict(int)
    for crops in allocation.values():
        for crop, n in crops.items():
            counts[crop] += n
    fallow = sum(n for crop, n in counts.items() if crop.lower() == "fallow")
    crops = sorted(((c, n) for c, n in counts.items() if c.lower() != "fallow"), key=lambda x: (-x[1], x[0]))
    total = max(slots, 1)
    mix = [{"name": c, "count": n, "share": n / total, "color": MIX_COLORS[i]} for i, (c, n) in enumerate(crops[:3])]
    rest = sum(n for _, n in crops[3:]) + fallow
    if rest:
        label = "Fallow" if not crops[3:] else ("Other" if not fallow else "Other + fallow")
        mix.append({"name": label, "count": rest, "share": rest / total, "color": MIX_COLORS[3]})
    return mix, (total - fallow) / total


def _from_genes(gene_results: list[dict], seasons: list[str]) -> dict:
    costs = {label: sum(g[k] for g in gene_results) for k, label in COST_LABELS.items()}
    water = defaultdict(float)
    crops: dict[str, dict] = {}
    for g in gene_results:
        water[g["season"]] += g["water_use_m3"]
        if g["crop_id"] == "FALLOW":
            continue
        c = crops.setdefault(g["crop_name"], {"name": g["crop_name"], "revenue": 0.0, "cost": 0.0, "yield_t": 0.0,
                                              "by_season": defaultdict(float), "slots": defaultdict(int)})
        c["revenue"] += g["revenue"]
        c["cost"] += g["total_cost"]
        c["yield_t"] += g["yield_t"]
        c["by_season"][g["season"]] += g["revenue"]
        c["slots"][g["season"]] += 1
    crop_rows = [{
        "name": c["name"], "revenue": c["revenue"], "profit": c["revenue"] - c["cost"], "yield_t": c["yield_t"],
        "where": " · ".join(f"{_season_name(s)} ×{c['slots'][s]}" for s in seasons if c["slots"][s]),
        "series": [c["by_season"][s] for s in seasons],
    } for c in crops.values()]
    return {
        "costs": sorted(({"name": k, "value": v} for k, v in costs.items()), key=lambda x: -x["value"]),
        "water": [{"season": _season_name(s), "short": SEASON_SHORT.get(s, s[:3].title()), "m3": water[s]}
                  for s in seasons],
        "crops": sorted(crop_rows, key=lambda x: -x["revenue"]),
    }


def _strategy(record: dict, scenarios: list[dict], gene_results: list[dict], farm: dict) -> dict:
    m = record["metrics"]
    seasons = list(farm.get("seasons", []))
    slots = len(record["plan"])
    mix, cropped = _mix(record["allocation"], slots)
    return {
        "label": f"#{record['rank']}", "rank": record["rank"], "fitness": record["fitness"],
        "net_profit": m["net_profit"], "revenue": m["revenue"], "total_cost": m["total_cost"],
        "yield_t": m["total_yield_t"], "yield_ach": m["yield_achievement"],
        "water_use": m["water_use_m3"], "water_avail": m["water_available_m3"],
        "soil": m["final_soil_health"], "soil_delta": m["soil_health_change"],
        "resilience": record["components"]["resilience"], "budget": float(farm.get("budget_usd") or 0),
        "roi": m["net_profit"] / m["total_cost"] if m["total_cost"] else 0.0,
        "mix": mix, "cropped_share": cropped, "slots": slots,
        "scenarios": [{"name": s["scenario"], "short": _short_scenario(s["scenario_id"], s["scenario"]),
                       "revenue": s["revenue"], "cost": s["total_cost"], "profit": s["net_profit"],
                       "yield_t": s["total_yield_t"]} for s in scenarios],
        **_from_genes(gene_results, seasons),
    }


def _pills(gemini_available: bool, stale: bool) -> list[dict]:
    pills = [{"label": "Gemini connected" if gemini_available else "Rule-based fallback", "on": gemini_available},
             {"label": "Deterministic simulator", "on": True}, {"label": "Genetic Algorithm", "on": True}]
    if stale:
        pills.append({"label": "Results out of date", "on": False})
    return pills


def farm_data(farm: dict, validated: bool, gemini_available: bool) -> dict:
    """Bento data before any optimisation: the farm profile itself."""
    rain = farm.get("rainfall_mm") or {}
    return {
        "title": "AgriGenesis", "subtitle": farm.get("farm_name") or "Farm overview",
        "pills": _pills(gemini_available, False), "strategies": [], "history": [], "note": SYNTHETIC_DATA_NOTICE,
        "credit": True,
        "farm": {
            "name": farm.get("farm_name") or "Farm", "area": float(farm.get("total_area_ha") or 0),
            "plots": int(farm.get("n_plots") or 0), "budget": float(farm.get("budget_usd") or 0),
            "water": float(farm.get("available_water_m3") or 0), "soil_type": str(farm.get("soil_type", "-")),
            "ph": float(farm.get("soil_ph") or 0), "soil_health": float(farm.get("soil_health_index") or 0),
            "seasons": [{"name": _season_name(s), "rain": float(rain.get(s) or 0)}
                        for s in farm.get("seasons", []) if s in SEASONS],
            "status": "Validated" if validated else "Not validated",
            "hint": ("Farm validated. Run the Genetic Algorithm to evolve whole-farm strategies and fill this "
                     "dashboard with results." if validated else
                     "Validate the farm first, then run the Genetic Algorithm in Evolution Lab."),
            "cta": "Evolution Lab → Evolve My Farm" if validated else "Farm Setup → Validate farm",
        },
    }


def result_data(result: dict, gene_results: dict[str, list[dict]], gemini_available: bool, stale: bool) -> dict:
    """Bento data for a finished run. ``gene_results`` maps strategy labels (``#1``...) to normal-scenario
    per-plot simulation rows."""
    farm = result["farm_profile"]
    ranked = result["ranked_strategies"] or [result["best_strategy"]]
    tables = result["scenario_results"]["ranked"]
    strategies = [_strategy(r, tables.get(f"#{r['rank']}", result["scenario_results"]["best"]),
                            gene_results[f"#{r['rank']}"], farm) for r in ranked if f"#{r['rank']}" in gene_results]
    history = [{"g": h["generation"], "best": h["best_fitness"], "mean": h["mean_fitness"],
                "worst": h["worst_fitness"], "profit": h["best_profit"], "unique": h["unique_strategies"]}
               for h in result["fitness_history"]]
    return {
        "title": "AgriGenesis", "subtitle": farm.get("farm_name") or "Farm overview",
        "pills": _pills(gemini_available, stale), "strategies": strategies, "history": history,
        "generations": len(history), "evaluations": result["optimization"]["evaluations"],
        "note": SYNTHETIC_DATA_NOTICE, "credit": True,
    }
