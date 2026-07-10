"""Strategy B — price-optimized, rule-based (SPEC §7.2).

Daily horizon; day-ahead prices assumed known (they are, in reality):
1. Rank the day's 15-min slots by buy price.
2. Grid charging allowed only in the cheapest `charge_quantile` of slots —
   never in the top-priced quartile (holds by construction).
3. Discharge to cover load in the most expensive slots (captures the 17-21
   peak band), subject to SoC.
4. Battery-to-grid export disallowed in MVP (only PV surplus exports).
PV surplus may be stored in any slot outside the top-priced quartile.
"""

from __future__ import annotations

import numpy as np

from .base import DayPlan, DispatchStrategy


class PriceOptimizedStrategy(DispatchStrategy):
    name = "price_optimized"
    label_da = "Prisoptimeret styring"

    def __init__(
        self,
        charge_quantile: float = 0.25,
        discharge_quantile: float = 0.25,
        no_charge_quantile: float = 0.75,
        roundtrip_efficiency: float = 0.92,
    ):
        for q in (charge_quantile, discharge_quantile, no_charge_quantile):
            if not 0.0 <= q <= 1.0:
                raise ValueError("quantiles must be in [0, 1]")
        if charge_quantile > no_charge_quantile:
            raise ValueError("charge_quantile must not exceed no_charge_quantile")
        self.charge_quantile = charge_quantile
        self.discharge_quantile = discharge_quantile
        self.no_charge_quantile = no_charge_quantile
        self.roundtrip_efficiency = roundtrip_efficiency

    def plan_day(
        self, buy_price_day: np.ndarray, pv_day: np.ndarray, load_day: np.ndarray
    ) -> DayPlan:
        n = len(buy_price_day)
        ranked = np.sort(buy_price_day)
        # Threshold by rank so ~charge_quantile of slots qualify even with ties.
        charge_thr = ranked[max(int(n * self.charge_quantile) - 1, 0)]
        discharge_thr = ranked[min(int(n * self.discharge_quantile), n - 1)]
        top_thr = ranked[min(int(n * self.no_charge_quantile), n - 1)]

        grid_charge_ok = buy_price_day <= charge_thr
        discharge_ok = (buy_price_day >= discharge_thr) & ~grid_charge_ok
        pv_charge_ok = buy_price_day < top_thr

        # Cap the day's grid charging by the shiftable need: residual load in
        # discharge slots not already covered by today's storable PV surplus.
        # This keeps grid energy from crowding out (free) PV surplus.
        net = load_day - pv_day
        residual_expensive = float(np.maximum(net, 0.0)[discharge_ok].sum())
        pv_surplus_storable = float(np.maximum(-net, 0.0)[pv_charge_ok].sum())
        eff = self.roundtrip_efficiency**0.5
        need_storage = residual_expensive / eff
        pv_storage = pv_surplus_storable * eff
        budget = max(0.0, (need_storage - pv_storage) / eff)

        return DayPlan(
            pv_charge_ok=pv_charge_ok,
            grid_charge_ok=grid_charge_ok,
            discharge_ok=discharge_ok,
            grid_charge_budget_kwh=budget,
        )
