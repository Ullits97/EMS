"""Build synthetic but realistic normalized household consumption profiles
(SPEC §6.3). Deterministic (seeded). Runs fully offline.

Usage:
    python ingestion/build_consumption.py [--year 2025]

Produces data/reference/consumption_profiles.parquet with one column per
profile (share_base, share_base_ev, share_base_hp, share_base_ev_hp), each
normalized to sum = 1 over the year.

TODO(product): replace with empirical category profiles in Phase 2.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from common import DEFAULT_REFERENCE_YEAR, reference_index, update_meta, write_reference

SEED = 20260101
EV_ANNUAL_KWH = 3500.0  # night-weighted charging block, relative to base weight
BASE_ANNUAL_KWH = 4000.0  # nominal base for combining blocks before normalization
HP_ANNUAL_KWH = 4500.0


def base_shape(idx: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Morning/evening peaks, weekday/weekend variation, seasonal factor."""
    hour = idx.hour.to_numpy() + idx.minute.to_numpy() / 60.0
    weekend = np.asarray(idx.dayofweek >= 5)
    doy = idx.dayofyear.to_numpy()

    morning = np.exp(-0.5 * ((hour - 7.0) / 1.4) ** 2)
    evening = np.exp(-0.5 * ((hour - 18.5) / 2.2) ** 2)
    night_floor = 0.25
    daytime = 0.35 * np.exp(-0.5 * ((hour - 13.0) / 3.5) ** 2)

    shape = night_floor + 0.9 * morning + 1.5 * evening + daytime
    # Weekends: flatter morning, more daytime load.
    shape = np.where(weekend, night_floor + 0.5 * morning + 1.4 * evening + 1.8 * daytime, shape)
    # Seasonal lighting/appliance factor: +25% mid-winter, -15% mid-summer.
    seasonal = 1.0 + 0.25 * np.cos(2 * np.pi * (doy - 10) / 365.0) - 0.05
    shape = shape * seasonal
    # Small deterministic noise for realism.
    shape = shape * (1.0 + 0.05 * rng.standard_normal(len(idx)))
    return np.clip(shape, 0.01, None)


def ev_shape(idx: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Night-weighted charging block (23-06), a few sessions per week."""
    hour = idx.hour.to_numpy()
    night = (hour >= 23) | (hour < 6)
    # Charge on a deterministic-pseudorandom ~4 nights/week pattern.
    day_number = idx.dayofyear.to_numpy() + (idx.year.to_numpy() - idx.year.to_numpy().min()) * 366
    charge_day = rng.random(int(day_number.max()) + 1) < 0.57
    active = night & charge_day[day_number]
    return active.astype(float)


def hp_shape(idx: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Heating-season load from a simple degree-day curve."""
    doy = idx.dayofyear.to_numpy()
    # Sinusoidal outdoor temperature proxy: min ~0C late Jan, max ~17C late Jul.
    t_out = 8.5 - 8.5 * np.cos(2 * np.pi * (doy - 25) / 365.0)
    t_out = t_out + 1.5 * rng.standard_normal(len(idx)) * 0.3
    degree = np.clip(17.0 - t_out, 0.0, None)
    hour = idx.hour.to_numpy()
    # Mild diurnal modulation (night setback).
    diurnal = np.where((hour >= 22) | (hour < 5), 0.8, 1.05)
    return degree * diurnal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_REFERENCE_YEAR)
    args = parser.parse_args()

    idx = reference_index(args.year)
    rng = np.random.default_rng(SEED)

    base = base_shape(idx, rng)
    ev = ev_shape(idx, rng)
    hp = hp_shape(idx, rng)

    def normalize(arr: np.ndarray) -> np.ndarray:
        return arr / arr.sum()

    base_n = normalize(base)
    ev_n = normalize(ev) if ev.sum() > 0 else ev
    hp_n = normalize(hp)

    def combine(*blocks: tuple[np.ndarray, float]) -> np.ndarray:
        total = sum(shape * kwh for shape, kwh in blocks)
        return normalize(total)

    out = pd.DataFrame(
        {
            "timestamp": idx,
            "share_base": base_n,
            "share_base_ev": combine((base_n, BASE_ANNUAL_KWH), (ev_n, EV_ANNUAL_KWH)),
            "share_base_hp": combine((base_n, BASE_ANNUAL_KWH), (hp_n, HP_ANNUAL_KWH)),
            "share_base_ev_hp": combine(
                (base_n, BASE_ANNUAL_KWH), (ev_n, EV_ANNUAL_KWH), (hp_n, HP_ANNUAL_KWH)
            ),
        }
    )
    write_reference(out, "consumption_profiles.parquet")
    update_meta(consumption_source=f"synthetic standard profiles (seed {SEED})")


if __name__ == "__main__":
    main()
