"""Dataset loading and validation: missing files, bad columns and invalid values fail clearly."""
from __future__ import annotations

import json
import shutil

import pandas as pd
import pytest

from config import DATA_DIR
from services.data_loader import DataError, load_datasets, load_sample_farm, read_csv

CSV_FILES = ["crops.csv", "crop_requirements.csv", "input_costs.csv", "soil_profiles.csv", "farms.csv",
             "weather_scenarios.csv"]


@pytest.fixture
def data_copy(tmp_path):
    for name in [*CSV_FILES, "sample_farm.json"]:
        shutil.copy(DATA_DIR / name, tmp_path / name)
    return tmp_path


def _edit(directory, name, row, column, value):
    frame = pd.read_csv(directory / name)
    frame[column] = frame[column].astype(object)
    frame.at[row, column] = value
    frame.to_csv(directory / name, index=False)


def test_all_seven_files_load():
    datasets = load_datasets()
    assert len(datasets.crops) == 9 and datasets.crops["crop_id"].is_unique
    assert {"allowed_seasons", "suitable_soils", "seed_cost_usd_per_ha"} <= set(datasets.crops.columns)
    assert set(datasets.soil_types) == {"loam", "clay_loam", "sandy_loam", "clay"}
    assert len(datasets.farms) == 3
    assert {"normal", "drought", "excess_rainfall", "input_price_shock", "market_price_drop"} == set(
        datasets.scenarios["scenario_id"])
    assert load_sample_farm()["farm_name"] == "Green Valley Farm"


@pytest.mark.parametrize("name", CSV_FILES)
def test_every_file_is_labelled_synthetic(name):
    assert read_csv(name)["data_note"].str.contains("synthetic", case=False).all()


def test_sample_farm_is_labelled_synthetic():
    assert "synthetic" in load_sample_farm()["data_note"].lower()


def test_units_are_consistent():
    crops = load_datasets().crops
    assert crops["base_yield_t_per_ha"].gt(0).all() and crops["growth_duration_days"].le(365).all()
    assert crops["min_ph"].lt(crops["max_ph"]).all()


@pytest.mark.parametrize("name", [*CSV_FILES, "sample_farm.json"])
def test_missing_file(data_copy, name):
    (data_copy / name).unlink()
    with pytest.raises(DataError, match="Dataset not found"):
        load_datasets(data_copy) if name != "sample_farm.json" else load_sample_farm(data_copy)


def test_missing_column(data_copy):
    pd.read_csv(data_copy / "crops.csv").drop(columns="selling_price_usd_per_t").to_csv(
        data_copy / "crops.csv", index=False)
    with pytest.raises(DataError, match="missing columns: selling_price_usd_per_t"):
        load_datasets(data_copy)


@pytest.mark.parametrize("name,column,value,message", [
    ("crops.csv", "base_yield_t_per_ha", -2, "must be > 0"),
    ("crops.csv", "selling_price_usd_per_t", "cheap", "must be a number"),
    ("crops.csv", "growth_duration_days", 90.5, "whole number"),
    ("crop_requirements.csv", "drought_tolerance", 1.5, "<= 1"),
    ("crop_requirements.csv", "max_ph", 4.0, "min_ph must be below max_ph"),
    ("crop_requirements.csv", "allowed_seasons", "spring", "must list seasons"),
    ("input_costs.csv", "labor_cost_usd_per_ha", -5, "must be >= 0"),
    ("soil_profiles.csv", "drainage_factor", None, "must be a number"),
    ("farms.csv", "n_plots", 0, "must be >= 1"),
    ("farms.csv", "soil_health_index", 140, "<= 100"),
    ("weather_scenarios.csv", "rainfall_multiplier", 9, "<= 3.0"),
    ("weather_scenarios.csv", "data_note", "real prices", "synthetic"),
])
def test_invalid_values(data_copy, name, column, value, message):
    _edit(data_copy, name, 0, column, value)
    with pytest.raises(DataError, match=message) as err:
        load_datasets(data_copy)
    assert name in str(err.value)


def test_duplicate_ids(data_copy):
    frame = pd.read_csv(data_copy / "soil_profiles.csv")
    pd.concat([frame, frame.iloc[[0]]]).to_csv(data_copy / "soil_profiles.csv", index=False)
    with pytest.raises(DataError, match="duplicate soil_type"):
        load_datasets(data_copy)


def test_cross_reference_errors(data_copy):
    _edit(data_copy, "farms.csv", 0, "soil_type", "peat")
    with pytest.raises(DataError, match="unknown soil types"):
        load_datasets(data_copy)


def test_crop_ids_must_match_across_files(data_copy):
    _edit(data_copy, "input_costs.csv", 0, "crop_id", "BANANA")
    with pytest.raises(DataError, match="do not match crops.csv"):
        load_datasets(data_copy)


def test_baseline_scenario_required(data_copy):
    _edit(data_copy, "weather_scenarios.csv", 0, "scenario_id", "baseline")
    with pytest.raises(DataError, match="'normal' scenario"):
        load_datasets(data_copy)


def test_empty_and_malformed_files(data_copy):
    (data_copy / "farms.csv").write_text("", encoding="utf-8")
    with pytest.raises(DataError, match="Could not read farms.csv"):
        load_datasets(data_copy)


def test_bad_sample_farm(data_copy):
    (data_copy / "sample_farm.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError, match="not valid JSON"):
        load_sample_farm(data_copy)
    data = json.loads((DATA_DIR / "sample_farm.json").read_text(encoding="utf-8"))
    del data["budget_usd"]
    (data_copy / "sample_farm.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DataError, match="missing fields: budget_usd"):
        load_sample_farm(data_copy)
