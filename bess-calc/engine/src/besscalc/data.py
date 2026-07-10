"""Loaders for bundled config (YAML) and reference-year datasets (Parquet).

Runtime never touches the network. If a reference Parquet is missing the
loader raises DataError pointing at the ingestion script that produces it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

CONFIG_DIR = Path(__file__).parent / "config"

# bess-calc/engine/src/besscalc/data.py -> bess-calc/data/reference
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"

TIMEZONE = "Europe/Copenhagen"
STEP_HOURS = 0.25  # 15-minute resolution


class DataError(RuntimeError):
    """Raised when required reference data or config is missing/invalid."""


def data_dir() -> Path:
    import os

    override = os.environ.get("BESSCALC_DATA_DIR")
    return Path(override) if override else _DEFAULT_DATA_DIR


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise DataError(f"Missing bundled config file: {path}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=None)
def load_tariffs() -> dict:
    return _load_yaml("tariffs.yaml")


@lru_cache(maxsize=None)
def load_taxes() -> dict:
    return _load_yaml("taxes.yaml")


@lru_cache(maxsize=None)
def load_defaults() -> dict:
    return _load_yaml("defaults.yaml")


def _read_parquet(filename: str, produced_by: str) -> pd.DataFrame:
    path = data_dir() / filename
    if not path.exists():
        raise DataError(
            f"Reference dataset missing: {path}. Runtime never calls the network — "
            f"generate it first with `python ingestion/{produced_by}` (see SPEC.md §6)."
        )
    return pd.read_parquet(path)


def _to_series(df: pd.DataFrame, value_col: str) -> pd.Series:
    ts = pd.DatetimeIndex(df["timestamp"])
    if ts.tz is None:
        ts = ts.tz_localize("UTC").tz_convert(TIMEZONE)
    else:
        ts = ts.tz_convert(TIMEZONE)
    series = pd.Series(df[value_col].to_numpy(dtype=float), index=ts, name=value_col)
    if not series.index.is_monotonic_increasing:
        series = series.sort_index()
    return series


def load_spot(price_area: str) -> pd.Series:
    """Spot price [DKK/kWh] on the uniform 15-min reference-year index."""
    fname = f"spot_{price_area.lower()}.parquet"
    df = _read_parquet(fname, "fetch_spot.py")
    return _to_series(df, "price_dkk_per_kwh")


def load_pv_profile(orientation: str) -> pd.Series:
    """Normalized PV production [kWh per kWp per 15-min step] for an orientation preset."""
    df = _read_parquet("pv_profiles.parquet", "fetch_pv.py")
    col = f"kwh_per_kwp_{orientation.lower()}"
    if col not in df.columns:
        raise DataError(f"pv_profiles.parquet has no column {col!r}")
    return _to_series(df, col)


def load_consumption_profile(profile: str) -> pd.Series:
    """Normalized consumption profile (sums to 1.0 over the year)."""
    df = _read_parquet("consumption_profiles.parquet", "build_consumption.py")
    col = f"share_{profile}"
    if col not in df.columns:
        raise DataError(f"consumption_profiles.parquet has no column {col!r}")
    return _to_series(df, col)


def load_reference_meta() -> dict:
    """Provenance metadata written by the ingestion scripts."""
    path = data_dir() / "meta.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def reference_index(price_area: str = "DK1") -> pd.DatetimeIndex:
    return load_spot(price_area).index
