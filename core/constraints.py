"""Hard and soft constraints on a planting strategy."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from simulation.farm_simulator import FALLOW, FarmContext, simulate

DEFAULT_PENALTIES = {
    "budget_per_usd": 10.0,
    "labor_per_day": 300.0,
    "unsuitable_crop": 5000.0,
    "same_family": 800.0,
}
HARD_KINDS = {"budget", "labor", "unsuitable"}


@dataclass
class Violation:
    kind: str
    season: str
    message: str
    amount: float = 0.0
    plot: int | None = None

    @property
    def hard(self) -> bool:
        return self.kind in HARD_KINDS


@dataclass
class ConstraintReport:
    violations: list[Violation] = field(default_factory=list)
    penalty: float = 0.0

    @property
    def feasible(self) -> bool:
        return not any(v.hard for v in self.violations)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "type": v.kind,
                    "severity": "hard" if v.hard else "soft",
                    "season": v.season,
                    "plot": "" if v.plot is None else f"Plot {v.plot + 1}",
                    "message": v.message,
                }
                for v in self.violations
            ],
            columns=["type", "severity", "season", "plot", "message"],
        )


def penalty_weights(context: FarmContext) -> dict:
    return {**DEFAULT_PENALTIES, **context.config.get("fitness", {}).get("penalties", {})}


def _allowed_mask(context: FarmContext) -> np.ndarray:
    """Boolean ``(n_seasons, n_crops + 1)``; the last column is fallow (always allowed)."""
    mask = getattr(context, "_allowed_mask", None)
    if mask is None:
        mask = np.zeros((context.n_seasons, context.n_crops + 1), dtype=bool)
        for s, options in enumerate(context.allowed):
            mask[s, [context.fallow_index if o == FALLOW else o for o in options]] = True
        context._allowed_mask = mask
    return mask


def check_constraints(context: FarmContext, genes: np.ndarray) -> ConstraintReport:
    genes = np.asarray(genes, dtype=int)
    weights = penalty_weights(context)
    report = ConstraintReport()
    usage = simulate(context, genes)
    budget = float(context.farm["budget"])
    labor_cap = float(context.farm["labor_days"])
    families = context.crops["family"].to_numpy()
    columns = np.where(genes == FALLOW, context.fallow_index, genes)
    suitable = _allowed_mask(context)[np.arange(context.n_seasons)[None, :], columns]
    planted = genes != FALLOW
    fam = np.where(planted, families[np.where(planted, genes, 0)], "")
    repeat = np.zeros_like(planted)
    repeat[:, 1:] = planted[:, 1:] & planted[:, :-1] & (fam[:, 1:] == fam[:, :-1])

    for s, season in enumerate(context.seasons):
        name = season["name"]
        over_budget = usage.cost[0, s] - budget
        if over_budget > 1e-6:
            report.violations.append(Violation(
                "budget", name, f"Costs exceed budget by ${over_budget:,.0f}", over_budget))
            report.penalty += over_budget * weights["budget_per_usd"]
        over_labor = usage.labor_days[0, s] - labor_cap
        if over_labor > 1e-6:
            report.violations.append(Violation(
                "labor", name, f"Labour exceeds capacity by {over_labor:,.0f} days", over_labor))
            report.penalty += over_labor * weights["labor_per_day"]

    for plot, s in zip(*np.nonzero(~suitable)):
        name = context.seasons[s]["name"]
        report.violations.append(Violation(
            "unsuitable", name,
            f"{context.crop_name(genes[plot, s])} is not suitable for this farm in {name}", 1, int(plot)))
        report.penalty += weights["unsuitable_crop"]
    for plot, s in zip(*np.nonzero(repeat)):
        report.violations.append(Violation(
            "same_family", context.seasons[s]["name"],
            f"{context.crop_name(genes[plot, s - 1])} followed by {context.crop_name(genes[plot, s])} "
            f"(both {families[genes[plot, s]]})", 1, int(plot)))
        report.penalty += weights["same_family"]
    return report
