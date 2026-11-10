"""Small formatting and file helpers."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


def format_money(value: float, currency: str = "$") -> str:
    return f"-{currency}{abs(value):,.0f}" if value < 0 else f"{currency}{value:,.0f}"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "item"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data, path: str | Path) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def save_figure(fig, directory: str | Path, name: str) -> Path:
    path = ensure_dir(directory) / f"{slugify(name)}-{timestamp()}.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return path
