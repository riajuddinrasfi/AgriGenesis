"""Decides which crops can grow on a farm each season and how rotations interact."""
from __future__ import annotations

import numpy as np
import pandas as pd

from simulation.farm_simulator import FALLOW
from simulation.soil_simulator import rotation_matrix
from services.data_loader import DataLoader

PH_TOLERANCE = 0.5
TEMP_TOLERANCE = 3.0
MARGINAL_SCORE = 0.7


class AgronomyAgent:
    def __init__(self, loader: DataLoader):
        self.crops = loader.load_crops()

    def suitability(self, farm: dict, seasons: list[dict]) -> pd.DataFrame:
        """Score 0-1 for every crop in every season, with the limiting reason."""
        rows = []
        ph = float(farm["soil_ph"])
        for season in seasons:
            kind = season["type"]
            temp = float(farm[f"avg_temp_{kind}"])
            for _, crop in self.crops.iterrows():
                reasons, score = [], 1.0
                if crop["season_type"] not in (kind, "any"):
                    score, reasons = 0.0, [f"{crop['season_type']}-season crop"]
                else:
                    ph_gap = max(crop["ph_min"] - ph, 0, ph - crop["ph_max"])
                    if ph_gap > PH_TOLERANCE:
                        score = 0.0
                        reasons.append(f"soil pH {ph} outside {crop['ph_min']}-{crop['ph_max']}")
                    elif ph_gap > 0:
                        score = min(score, MARGINAL_SCORE)
                        reasons.append("soil pH marginal")
                    t_gap = max(crop["temp_min"] - temp, 0, temp - crop["temp_max"])
                    if t_gap > TEMP_TOLERANCE:
                        score = 0.0
                        reasons.append(f"{temp}°C outside {crop['temp_min']}-{crop['temp_max']}°C")
                    elif t_gap > 0:
                        score = min(score, MARGINAL_SCORE)
                        reasons.append("temperature marginal")
                rows.append({"season": season["name"], "crop": crop["crop"], "score": score,
                             "notes": "; ".join(reasons) or "suitable"})
        return pd.DataFrame(rows)

    def allowed_genes(self, farm: dict, seasons: list[dict]) -> list[list[int]]:
        table = self.suitability(farm, seasons)
        index = {name: i for i, name in enumerate(self.crops["crop"])}
        allowed = []
        for season in seasons:
            ok = table[(table["season"] == season["name"]) & (table["score"] > 0)]
            allowed.append([FALLOW] + [index[c] for c in ok["crop"]])
        return allowed

    def rotation_matrix(self, rotation_config: dict | None = None) -> np.ndarray:
        cfg = rotation_config or {}
        return rotation_matrix(
            self.crops["family"].to_numpy(),
            same_family_factor=float(cfg.get("same_family_factor", 0.9)),
            legume_bonus=float(cfg.get("legume_bonus", 1.08)),
        )
