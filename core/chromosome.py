"""A chromosome is one crop plan: ``genes[plot, season]`` = crop index or FALLOW."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from simulation.farm_simulator import FALLOW, FarmContext


@dataclass
class Chromosome:
    genes: np.ndarray

    def __post_init__(self):
        self.genes = np.asarray(self.genes, dtype=int)

    @classmethod
    def random(cls, context: FarmContext, rng: np.random.Generator) -> "Chromosome":
        genes = np.empty((context.n_plots, context.n_seasons), dtype=int)
        for s, options in enumerate(context.allowed):
            genes[:, s] = rng.choice(options, size=context.n_plots)
        return cls(genes)

    @classmethod
    def fallow(cls, context: FarmContext) -> "Chromosome":
        return cls(np.full((context.n_plots, context.n_seasons), FALLOW, dtype=int))

    @property
    def key(self) -> bytes:
        return self.genes.tobytes()

    def copy(self) -> "Chromosome":
        return Chromosome(self.genes.copy())

    def to_frame(self, context: FarmContext) -> pd.DataFrame:
        return pd.DataFrame(
            [[context.crop_name(g) for g in row] for row in self.genes],
            index=[f"Plot {i + 1}" for i in range(context.n_plots)],
            columns=[s["name"] for s in context.seasons],
        )

    @classmethod
    def from_frame(cls, context: FarmContext, frame: pd.DataFrame) -> "Chromosome":
        return cls([[context.crop_index(name) for name in row] for row in frame.to_numpy()])
