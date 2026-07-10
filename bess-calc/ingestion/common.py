"""Shared helpers for ingestion scripts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TIMEZONE = "Europe/Copenhagen"
REFERENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "reference"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

DEFAULT_REFERENCE_YEAR = 2025  # most recent complete calendar year


def reference_index(year: int) -> pd.DatetimeIndex:
    """Uniform 15-min index over one calendar year, Europe/Copenhagen local time."""
    return pd.date_range(
        start=pd.Timestamp(f"{year}-01-01 00:00", tz=TIMEZONE),
        end=pd.Timestamp(f"{year + 1}-01-01 00:00", tz=TIMEZONE),
        freq="15min",
        inclusive="left",
    )


def update_meta(**fields) -> None:
    """Merge provenance fields into data/reference/meta.json."""
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = REFERENCE_DIR / "meta.json"
    meta = {}
    if path.exists():
        meta = json.loads(path.read_text(encoding="utf-8"))
    meta.update(fields)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_reference(df: pd.DataFrame, filename: str) -> Path:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = REFERENCE_DIR / filename
    df.to_parquet(out, index=False)
    print(f"wrote {out} ({len(df)} rows)")
    return out
