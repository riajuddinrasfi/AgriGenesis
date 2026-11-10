"""Chromosome = one complete farm strategy made of plot-season genes."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from config import FALLOW


@dataclass(frozen=True)
class Gene:
    """Management decision for one plot in one season.

    ``water_level`` is the share (0-1) of the crop's irrigation need that is supplied and
    ``fertilizer_level`` scales fertilizer from 0 to 125% of the crop requirement.
    """

    plot_id: int
    season: str
    crop_id: str
    water_level: float
    fertilizer_level: float
    planting_window: int

    @property
    def is_fallow(self) -> bool:
        return self.crop_id == FALLOW

    def with_changes(self, **changes) -> "Gene":
        return replace(self, **changes)

    def to_dict(self) -> dict:
        return asdict(self)


def fallow_gene(plot_id: int, season: str) -> Gene:
    return Gene(plot_id, season, FALLOW, 0.0, 0.0, 0)


@dataclass
class Chromosome:
    """Ordered list of genes, one per (plot, season) slot."""

    genes: list[Gene]

    @property
    def key(self) -> tuple:
        """Hashable identity used for caching and de-duplication."""
        return tuple((g.plot_id, g.season, g.crop_id, round(g.water_level, 3),
                      round(g.fertilizer_level, 3), g.planting_window) for g in self.genes)

    def copy(self) -> "Chromosome":
        return Chromosome(list(self.genes))

    def to_records(self) -> list[dict]:
        return [g.to_dict() for g in self.genes]

    @classmethod
    def from_records(cls, records: list[dict]) -> "Chromosome":
        return cls([Gene(int(r["plot_id"]), str(r["season"]), str(r["crop_id"]),
                         float(r["water_level"]), float(r["fertilizer_level"]),
                         int(r["planting_window"])) for r in records])

    def __len__(self) -> int:
        return len(self.genes)
