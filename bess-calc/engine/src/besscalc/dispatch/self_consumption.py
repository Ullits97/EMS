"""Strategy A — self-consumption (mirrors most inverters' default).

Charge from PV surplus only; discharge to cover residual load. No grid
charging, no price awareness.
"""

from __future__ import annotations

import numpy as np

from .base import DayPlan, DispatchStrategy


class SelfConsumptionStrategy(DispatchStrategy):
    name = "self_consumption"
    label_da = "Standardstyring (egetforbrug)"

    def plan_day(
        self, buy_price_day: np.ndarray, pv_day: np.ndarray, load_day: np.ndarray
    ) -> DayPlan:
        n = len(buy_price_day)
        ones = np.ones(n, dtype=bool)
        return DayPlan(
            pv_charge_ok=ones,
            grid_charge_ok=np.zeros(n, dtype=bool),
            discharge_ok=ones,
            grid_charge_budget_kwh=0.0,
        )
