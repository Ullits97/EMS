"""Household consumption from bundled normalized profiles."""

from __future__ import annotations

import numpy as np

from ..data import load_consumption_profile
from ..models import ConsumptionSpec


def consumption_series(spec: ConsumptionSpec, n_steps: int) -> np.ndarray:
    """Per-step household load [kWh], scaled so the year sums to annual_kwh."""
    profile = load_consumption_profile(spec.profile)
    if len(profile) != n_steps:
        raise ValueError(
            f"Consumption profile length {len(profile)} does not match reference index {n_steps}"
        )
    arr = profile.to_numpy(dtype=float)
    return arr * (spec.annual_kwh / arr.sum())
