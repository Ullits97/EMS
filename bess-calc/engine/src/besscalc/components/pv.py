"""PV production from bundled normalized profiles."""

from __future__ import annotations

import numpy as np

from ..data import load_pv_profile
from ..models import PVSpec


def pv_generation(spec: PVSpec | None, n_steps: int) -> np.ndarray:
    """Per-step PV production [kWh]. Zeros when no PV is configured."""
    if spec is None:
        return np.zeros(n_steps)
    profile = load_pv_profile(spec.orientation)
    if len(profile) != n_steps:
        raise ValueError(
            f"PV profile length {len(profile)} does not match reference index {n_steps}"
        )
    return profile.to_numpy(dtype=float) * spec.kwp
