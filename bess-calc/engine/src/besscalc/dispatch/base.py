"""Dispatch strategy interface (ported HEMS dispatcher pattern).

A strategy is stateless w.r.t. the battery: given one day's buy prices it
returns boolean per-slot permissions; the simulation loop applies physics
(SoC window, power caps, efficiency).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DayPlan:
    """Per-slot permissions for one local day (92/96/100 slots with DST)."""

    pv_charge_ok: np.ndarray  # bool: may store PV surplus this slot
    grid_charge_ok: np.ndarray  # bool: may charge from the grid this slot
    discharge_ok: np.ndarray  # bool: may discharge to cover residual load
    grid_charge_budget_kwh: float  # bus-side cap on the day's total grid charging


class DispatchStrategy(ABC):
    name: str
    label_da: str

    @abstractmethod
    def plan_day(
        self, buy_price_day: np.ndarray, pv_day: np.ndarray, load_day: np.ndarray
    ) -> DayPlan:
        """Compute slot permissions for one day.

        Day-ahead prices are known in reality; PV/load forecasts are assumed
        known too — the realism factor discounts this optimism (SPEC §7.2).
        """
