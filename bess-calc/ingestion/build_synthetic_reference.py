"""OFFLINE FALLBACK: generate deterministic synthetic spot-price and PV
reference datasets with the exact schema the real ingestion scripts produce.

Use this only when fetch_spot.py / fetch_pv.py cannot reach the network
(e.g. sandboxed CI). The resulting datasets are clearly flagged
`synthetic: true` in data/reference/meta.json, and the engine surfaces a
warning in every result's assumptions until real data replaces them.

Usage:
    python ingestion/build_synthetic_reference.py [--year 2025]
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from common import DEFAULT_REFERENCE_YEAR, reference_index, update_meta, write_reference

SEED = 42


def synthetic_spot(idx: pd.DatetimeIndex, area: str) -> np.ndarray:
    """Two-peak diurnal shape + seasonal level + autocorrelated noise, DKK/kWh."""
    rng = np.random.default_rng(SEED + (0 if area == "DK1" else 1))
    hour = idx.hour.to_numpy() + idx.minute.to_numpy() / 60.0
    doy = idx.dayofyear.to_numpy()

    morning_peak = 0.30 * np.exp(-0.5 * ((hour - 8.0) / 1.8) ** 2)
    evening_peak = 0.55 * np.exp(-0.5 * ((hour - 18.5) / 2.0) ** 2)
    midday_solar_dip = -0.25 * np.exp(-0.5 * ((hour - 13.0) / 2.5) ** 2)
    seasonal = 0.15 * np.cos(2 * np.pi * (doy - 15) / 365.0)

    base_level = 0.55 if area == "DK1" else 0.60
    # Daily level noise (autocorrelated via per-day draw) + fast noise.
    n_days = int(doy.max())
    day_level = rng.normal(0.0, 0.18, n_days + 1)
    fast = rng.normal(0.0, 0.05, len(idx))
    price = (
        base_level
        + seasonal
        + morning_peak
        + evening_peak
        + midday_solar_dip
        + day_level[doy]
        + fast
    )
    # Occasional negative prices around sunny midday hours, like real DK data.
    return np.round(price, 5)


def synthetic_pv(idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Clear-sky-ish diurnal/seasonal PV shape per orientation, kWh/kWp/step."""
    rng = np.random.default_rng(SEED + 10)
    hour = idx.hour.to_numpy() + idx.minute.to_numpy() / 60.0
    doy = idx.dayofyear.to_numpy()

    # Day length / solar elevation proxy for ~56N.
    season = np.cos(2 * np.pi * (doy - 172) / 365.0)  # 1 at winter solstice-ish
    half_day = 4.35 + 2.35 * -season  # hours from noon to sunset: ~2h winter, ~8.7h summer... scaled below
    amplitude = np.clip(0.55 - 0.45 * season, 0.05, None)

    def orientation(center_hours: list[float], width: float, scale: float) -> np.ndarray:
        prod = np.zeros(len(idx))
        for c in center_hours:
            prod += np.exp(-0.5 * ((hour - c) / width) ** 2)
        prod /= len(center_hours)
        daylight = np.abs(hour - 13.0) < half_day
        out = prod * amplitude * daylight * scale
        # Per-day cloud factor, deterministic.
        n_days = int(doy.max())
        cloud = np.clip(rng.beta(2.2, 1.3, n_days + 1), 0.05, 1.0)
        return out * cloud[doy]

    df = pd.DataFrame({"timestamp": idx})
    raw = {
        "s": orientation([13.0], 2.6, 1.0),
        "se_sw": orientation([10.5, 15.5], 2.4, 0.95),
        "e_w": orientation([9.5, 16.5], 2.3, 0.88),
    }
    # Normalize to realistic Danish annual yields per kWp.
    targets = {"s": 1050.0, "se_sw": 980.0, "e_w": 880.0}
    for name, arr in raw.items():
        df[f"kwh_per_kwp_{name}"] = arr * (targets[name] / arr.sum())
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_REFERENCE_YEAR)
    args = parser.parse_args()

    idx = reference_index(args.year)
    for area in ("DK1", "DK2"):
        df = pd.DataFrame({"timestamp": idx, "price_dkk_per_kwh": synthetic_spot(idx, area)})
        write_reference(df, f"spot_{area.lower()}.parquet")
    write_reference(synthetic_pv(idx), "pv_profiles.parquet")

    update_meta(
        reference_year=args.year,
        spot_source=f"SYNTHETIC placeholder (seed {SEED}) — run fetch_spot.py for real data",
        pv_source=f"SYNTHETIC placeholder (seed {SEED}) — run fetch_pv.py for real data",
        synthetic=True,
    )


if __name__ == "__main__":
    main()
