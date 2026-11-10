import numpy as np
import pytest

from agents.orchestrator import Orchestrator
from simulation.farm_simulator import FALLOW


@pytest.fixture(scope="session")
def orchestrator():
    return Orchestrator()


@pytest.fixture
def context(orchestrator):
    return orchestrator.build_context("F001")[0]


@pytest.fixture
def fallow_genes(context):
    return np.full((context.n_plots, context.n_seasons), FALLOW, dtype=int)


@pytest.fixture
def wet_dry(context):
    """Indices of the first wet and first dry season."""
    types = [s["type"] for s in context.seasons]
    return types.index("wet"), types.index("dry")
