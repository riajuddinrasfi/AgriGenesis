"""Formatting and serialisation helpers."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

import numpy as np


def split_list(value) -> list[str]:
    """Turn ``"A|B"``, ``"A, B"`` or a list into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, float) and np.isnan(value):
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = str(value).replace(",", "|").split("|")
    return [str(i).strip() for i in items if str(i).strip()]


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def to_jsonable(obj):
    """Recursively convert dataclasses, numpy values and DataFrames to JSON-safe types."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "to_dict") and hasattr(obj, "columns"):
        return to_jsonable(obj.to_dict(orient="records"))
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), indent=2), encoding="utf-8")
    return path
