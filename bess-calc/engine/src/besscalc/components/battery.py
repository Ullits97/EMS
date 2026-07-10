"""Battery component: SoC window, power caps, sqrt-efficiency per direction.

Energy origin (PV vs grid) is tracked in two stored-energy buckets so the
economics decomposition can attribute discharged energy to self-consumption
(PV origin) vs arbitrage (grid origin). Discharge draws proportionally.

All charge/discharge quantities in the public API are bus-side (AC) kWh:
losses are applied when energy crosses into/out of storage.
"""

from __future__ import annotations

import math

from ..models import BatterySpec

PV = "pv"
GRID = "grid"


class Battery:
    def __init__(self, spec: BatterySpec, capacity_factor: float = 1.0, step_hours: float = 0.25):
        if not 0 < capacity_factor <= 1:
            raise ValueError("capacity_factor must be in (0, 1]")
        capacity = spec.capacity_kwh * capacity_factor
        self.capacity_kwh = capacity
        self.soc_min = (1.0 - spec.depth_of_discharge) * capacity
        self.soc_max = capacity
        self.efficiency = math.sqrt(spec.roundtrip_efficiency)  # per direction
        self.power_step_kwh = spec.power_kw * step_hours  # energy cap per 15-min step
        # Start empty (at the bottom of the usable window); buckets track usable energy.
        self.soc = self.soc_min
        self.stored_pv = 0.0
        self.stored_grid = 0.0

    @property
    def usable_kwh(self) -> float:
        return self.soc - self.soc_min

    @property
    def headroom_bus_kwh(self) -> float:
        """Bus-side energy that can still be pushed in (before power cap)."""
        return (self.soc_max - self.soc) / self.efficiency

    def charge(self, energy_bus_kwh: float, source: str, power_budget_kwh: float | None = None) -> float:
        """Charge with up to `energy_bus_kwh` (bus side). Returns energy actually drawn."""
        budget = self.power_step_kwh if power_budget_kwh is None else power_budget_kwh
        drawn = min(energy_bus_kwh, budget, self.headroom_bus_kwh)
        if drawn <= 0.0:
            return 0.0
        stored = drawn * self.efficiency
        self.soc += stored
        if source == PV:
            self.stored_pv += stored
        else:
            self.stored_grid += stored
        return drawn

    def discharge(self, energy_bus_kwh: float) -> tuple[float, float]:
        """Discharge up to `energy_bus_kwh` (bus side, delivered).

        Returns (delivered_kwh, pv_fraction) where pv_fraction is the share of
        the delivered energy that originated from PV charging.
        """
        available = self.usable_kwh * self.efficiency
        delivered = min(energy_bus_kwh, self.power_step_kwh, available)
        if delivered <= 0.0:
            return 0.0, 0.0
        drawn_from_storage = delivered / self.efficiency
        total = self.usable_kwh
        pv_fraction = self.stored_pv / total if total > 0 else 0.0
        self.soc -= drawn_from_storage
        self.stored_pv -= drawn_from_storage * pv_fraction
        self.stored_grid -= drawn_from_storage * (1.0 - pv_fraction)
        # guard against tiny negative float residue
        if self.stored_pv < 0.0:
            self.stored_pv = 0.0
        if self.stored_grid < 0.0:
            self.stored_grid = 0.0
        return delivered, pv_fraction
