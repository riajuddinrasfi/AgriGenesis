"""Evolution Lab page: configure and run the Genetic Algorithm, then inspect convergence."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from config import GAConfig
from dashboard import (ACCENT, ACCENT_LIGHT, MUTED, current_inputs, get_orchestrator, plan_pivot, result_is_stale,
                       style_figure)
from services.strategy_service import save_result
from utils.helpers import money


def fitness_figure(history: list[dict]) -> go.Figure:
    gens = [h["generation"] for h in history]
    fig = go.Figure()
    fig.add_scatter(x=gens, y=[h["best_fitness"] for h in history], name="Best so far", line=dict(color=ACCENT, width=3))
    fig.add_scatter(x=gens, y=[h["mean_fitness"] for h in history], name="Population mean", line=dict(color=ACCENT_LIGHT))
    fig.add_scatter(x=gens, y=[h["worst_fitness"] for h in history], name="Worst", line=dict(color=MUTED, dash="dot"))
    fig.update_layout(title="Fitness history", xaxis_title="Generation", yaxis_title="Fitness")
    return style_figure(fig)


def _settings() -> GAConfig:
    cfg = st.session_state.ga_config
    with st.expander("Genetic Algorithm settings", expanded=True):
        c = st.columns(4)
        pop = c[0].number_input("Population size", 6, 300, cfg.population_size, 2)
        gens = c[1].number_input("Generations", 1, 200, cfg.generations)
        seed = c[2].number_input("Random seed", 0, 1_000_000, cfg.seed)
        tour = c[3].number_input("Tournament size", 2, 10, cfg.tournament_size)
        c = st.columns(4)
        cx = c[0].slider("Crossover probability", 0.0, 1.0, cfg.crossover_probability, 0.05)
        mut = c[1].slider("Mutation probability (per gene)", 0.0, 1.0, cfg.mutation_probability, 0.01)
        elite = c[2].number_input("Elitism (kept per generation)", 0, 10, cfg.elitism)
        top_k = c[3].number_input("Strategies to keep", 2, 10, cfg.top_k)
        gemini = get_orchestrator().gemini
        st.session_state.use_gemini = st.checkbox(
            "Use Gemini for the explanation", st.session_state.use_gemini and gemini.available,
            disabled=not gemini.available, help=None if gemini.available else "Set GEMINI_API_KEY in .env to enable")
    cfg = GAConfig(int(pop), int(gens), int(seed), int(tour), float(cx), float(mut), int(min(elite, pop)), int(top_k))
    st.session_state.ga_config = cfg
    return cfg


def _run(cfg: GAConfig) -> None:
    orch = get_orchestrator()
    bar = st.progress(0.0, text="Starting evolution...")
    chart = st.empty()
    history: list[dict] = []

    def progress(generation: int, total: int, row: dict) -> None:
        history.append(row)
        bar.progress(generation / total, text=f"Generation {generation}/{total}: best fitness "
                     f"{row['best_fitness']:.4f}, {row['evaluations']} strategies simulated")
        chart.plotly_chart(fitness_figure(history), width="stretch", key=f"live_{generation}")

    try:
        result = orch.run(st.session_state.farm_profile, st.session_state.weights, cfg, st.session_state.scenario_ids,
                          st.session_state.custom_scenarios, st.session_state.use_gemini, progress)
    except ValueError as exc:
        bar.empty()
        st.error(str(exc))
        return
    st.session_state.result = result
    st.session_state.result_inputs = current_inputs()
    st.session_state.scenario_eval = None
    st.session_state.result_path = str(save_result(result))
    bar.empty()
    chart.empty()


def render() -> None:
    st.title("Evolution Lab")
    cfg = _settings()
    if st.session_state.farm_profile is None:
        st.warning("Validate a farm in **Farm Setup** before running the optimiser.")
        return
    orch = get_orchestrator()
    scenarios = orch.scenario.select(st.session_state.scenario_ids, st.session_state.custom_scenarios)
    st.markdown("**Scenarios:** " + ", ".join(s.scenario_name for s in scenarios)
                + "  \n**Priorities:** " + ", ".join(f"{k} {v:.2f}" for k, v in st.session_state.weights.items()))
    st.caption(f"Each candidate is simulated under {len(scenarios)} scenario(s); up to "
               f"{cfg.population_size * cfg.generations:,} candidate evaluations (repeats are cached). "
               "Change scenarios in Scenario Lab and priorities in Farm Setup.")
    if st.button("Evolve My Farm", type="primary"):
        _run(cfg)
    result = st.session_state.result
    if result is None:
        return
    if result_is_stale():
        st.warning("The farm, priorities or scenarios changed since this run. Click **Evolve My Farm** to update.")
    history = result["fitness_history"]
    opt = result["optimization"]
    c = st.columns(4)
    c[0].metric("Best fitness", f"{result['best_fitness']:.4f}",
                f"{result['best_fitness'] - history[0]['best_fitness']:+.4f} vs generation 1")
    c[1].metric("Best net profit", money(result["best_strategy"]["metrics"]["net_profit"]))
    c[2].metric("Strategies simulated", f"{opt['evaluations']:,}")
    c[3].metric("Runtime", f"{opt['runtime_s']:.2f} s")
    st.plotly_chart(fitness_figure(history), width="stretch")
    fig = go.Figure(go.Scatter(x=[h["generation"] for h in history], y=[h["unique_strategies"] for h in history],
                               line=dict(color=ACCENT_LIGHT), name="Unique strategies"))
    fig.update_layout(title="Population diversity", xaxis_title="Generation", yaxis_title="Unique chromosomes")
    st.plotly_chart(style_figure(fig, 260), width="stretch")
    st.subheader("Best strategy")
    st.dataframe(plan_pivot(result["best_strategy"]["plan"]), width="stretch")
    contributions = result["best_strategy"]["contributions"]
    st.caption("Weighted fitness = " + " + ".join(f"{k} {v:.3f}" for k, v in contributions.items())
               + f" = {result['best_fitness']:.4f}")
    if st.session_state.result_path:
        st.caption(f"Saved to {st.session_state.result_path}")
