"""Fetch PVGIS hourly TMY for central Denmark and build normalized PV
profiles per orientation preset (SPEC §6.2).

Usage:
    python ingestion/fetch_pv.py [--year 2025] [--lat 56.0] [--lon 10.0]

Produces data/reference/pv_profiles.parquet with columns
[timestamp, kwh_per_kwp_s, kwh_per_kwp_se_sw, kwh_per_kwp_e_w]:
kWh per installed kWp per 15-min step (hourly TMY divided by 4).
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from common import DEFAULT_REFERENCE_YEAR, reference_index, update_meta, write_reference

API = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"

# Orientation presets: PVGIS azimuth convention (0 = south, -90 = east, 90 = west).
ORIENTATIONS: dict[str, list[float]] = {
    "s": [0.0],
    "se_sw": [-45.0, 45.0],  # averaged split array
    "e_w": [-90.0, 90.0],
}


def fetch_hourly_kwh_per_kwp(lat: float, lon: float, azimuth: float, tilt: int) -> pd.Series:
    """One TMY-like year of hourly production for a 1 kWp system [kWh/h]."""
    params = {
        "lat": lat,
        "lon": lon,
        "pvcalculation": 1,
        "peakpower": 1,
        "loss": 14,
        "angle": tilt,
        "aspect": azimuth,
        "outputformat": "json",
        "startyear": 2020,
        "endyear": 2020,
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    print(f"GET {url}")
    with urllib.request.urlopen(url, timeout=180) as resp:
        payload = json.load(resp)
    hourly = payload["outputs"]["hourly"]
    ts = pd.to_datetime([h["time"] for h in hourly], format="%Y%m%d:%H%M", utc=True)
    power_w = np.array([h["P"] for h in hourly], dtype=float)
    return pd.Series(power_w / 1000.0, index=ts)  # W -> kWh per hour


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_REFERENCE_YEAR)
    parser.add_argument("--lat", type=float, default=56.0)
    parser.add_argument("--lon", type=float, default=10.0)
    parser.add_argument("--tilt", type=int, default=35)
    args = parser.parse_args()

    idx = reference_index(args.year)
    out = pd.DataFrame({"timestamp": idx})
    for name, azimuths in ORIENTATIONS.items():
        series_list = [
            fetch_hourly_kwh_per_kwp(args.lat, args.lon, az, args.tilt) for az in azimuths
        ]
        hourly = sum(series_list) / len(series_list)
        # Map the fetched year onto the reference index by hour-of-year, then
        # upsample hourly -> 15-min by dividing by 4.
        values = hourly.to_numpy()
        hours_needed = len(idx) // 4
        if len(values) < hours_needed:
            raise SystemExit(f"PVGIS returned {len(values)} hours, need {hours_needed}")
        per_step = np.repeat(values[:hours_needed], 4) / 4.0
        out[f"kwh_per_kwp_{name}"] = per_step
        print(f"{name}: {per_step.sum():.0f} kWh/kWp/yr")

    write_reference(out, "pv_profiles.parquet")
    update_meta(pv_source=f"PVGIS seriescalc ({args.lat}N {args.lon}E, tilt {args.tilt})")


if __name__ == "__main__":
    main()
