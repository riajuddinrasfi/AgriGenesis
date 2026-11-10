"""Shared fixtures: datasets, the validated sample farm and its simulation context."""
from __future__ import annotations

import numpy as np
import pytest

from agents.agronomy_agent import AgronomyAgent
from services.data_loader import load_datasets, load_sample_farm
from services.validation_service import validate_farm_input
from simulation.farm_simulator import build_context
from simulation.scenario_engine import scenarios_from_frame


@pytest.fixture(scope="session")
def datasets():
    return load_datasets()


@pytest.fixture
def sample_input():
    return {k: v for k, v in load_sample_farm().items() if k not in ("data_note", "weights")}


@pytest.fixture
def profile(datasets, sample_input):
    return validate_farm_input(sample_input, datasets.crop_ids, datasets.soils["soil_type"].tolist())


@pytest.fixture
def context(datasets, profile):
    return build_context(profile, datasets, AgronomyAgent(datasets).assess(profile).feasible_options)


@pytest.fixture(scope="session")
def scenarios(datasets):
    return scenarios_from_frame(datasets.scenarios)


@pytest.fixture
def rng():
    return np.random.default_rng(7)
