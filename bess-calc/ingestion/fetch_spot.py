"""Fetch one full calendar year of day-ahead spot prices from Energi Data
Service and save as reference Parquet (SPEC §6.1).

Usage:
    python ingestion/fetch_spot.py [--year 2025]

Produces data/reference/spot_dk1.parquet and spot_dk2.parquet with columns
[timestamp, price_dkk_per_kwh] on a uniform 15-min Europe/Copenhagen index.
Runtime code never calls the network — only this script does.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

import pandas as pd

from common import DEFAULT_REFERENCE_YEAR, reference_index, update_meta, write_reference

API = "https://api.energidataservice.dk/dataset/Elspotprices"


def fetch_area(year: int, area: str) -> pd.DataFrame:
    params = {
        "start": f"{year}-01-01T00:00",
        "end": f"{year + 1}-01-01T00:00",
        "filter": json.dumps({"PriceArea": [area]}),
        "columns": "HourUTC,SpotPriceDKK",
        "limit": 0,
        "timezone": "utc",
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    print(f"GET {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        payload = json.load(resp)
    records = payload["records"]
    if not records:
        raise SystemExit(f"No spot records returned for {area} {year}")
    df = pd.DataFrame(records)
    ts = pd.to_datetime(df["HourUTC"], utc=True)
    series = pd.Series(df["SpotPriceDKK"].astype(float).to_numpy() / 1000.0, index=ts)
    series = series.sort_index()

    # Resample/interpolate to the uniform 15-min local index.
    idx = reference_index(year)
    series = series.tz_convert("Europe/Copenhagen")
    # Hourly price applies to the whole hour -> forward-fill onto the 15-min grid.
    upsampled = series.reindex(series.index.union(idx)).ffill().bfill()
    out = upsampled.reindex(idx)
    if out.isna().any():
        raise SystemExit(f"Gaps remain in {area} {year} after resampling")
    return pd.DataFrame({"timestamp": idx, "price_dkk_per_kwh": out.to_numpy()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_REFERENCE_YEAR)
    args = parser.parse_args()

    for area in ("DK1", "DK2"):
        df = fetch_area(args.year, area)
        write_reference(df, f"spot_{area.lower()}.parquet")

    update_meta(
        reference_year=args.year,
        spot_source="Energi Data Service (Elspotprices)",
        synthetic=False,
    )


if __name__ == "__main__":
    main()
