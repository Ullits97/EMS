from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class EnergyCarrier(str, Enum):
    ELECTRICITY = "electricity"
    DISTRICT_HEAT = "district_heat"


class HeatingSource(Protocol):
    name: str

    def deliver_heat(self, requested_heat_kwh: float, duration_h: float = 1.0) -> float:
        ...

    def required_input_energy_kwh(self, delivered_heat_kwh: float) -> float:
        ...

    @property
    def input_carrier(self) -> EnergyCarrier:
        ...


@dataclass
class TimeOfUseTariff:
    """Simple hourly tariff schedule [currency/kWh] for one energy carrier."""

    hourly_prices: list[float]

    def __post_init__(self) -> None:
        if len(self.hourly_prices) != 24:
            raise ValueError("hourly_prices must contain 24 values")

    def price_for_hour(self, hour_of_day: int) -> float:
        return self.hourly_prices[hour_of_day % 24]


@dataclass
class TariffBook:
    tariffs: dict[EnergyCarrier, TimeOfUseTariff]

    def price_for(self, carrier: EnergyCarrier, hour_of_day: int) -> float:
        tariff = self.tariffs.get(carrier)
        if tariff is None:
            raise ValueError(f"No tariff configured for carrier: {carrier}")
        return tariff.price_for_hour(hour_of_day)


@dataclass
class HeatDemandResult:
    heat_loss_kwh: float
    indoor_temperature_c: float


@dataclass
class House:
    """Single-zone thermal model with linear heat-loss approximation.

    UA is overall heat transfer coefficient [kW/K].
    Thermal mass is equivalent heat capacity [kWh/K].
    """

    floor_area_m2: float
    ua_kw_per_k: float
    thermal_mass_kwh_per_k: float
    indoor_temperature_c: float
    target_temperature_c: float

    def estimate_hourly_heat_demand(self, outdoor_temperature_c: float) -> float:
        delta_t = max(self.target_temperature_c - outdoor_temperature_c, 0.0)
        return self.ua_kw_per_k * delta_t

    def advance_one_hour(self, supplied_heat_kwh: float, outdoor_temperature_c: float) -> HeatDemandResult:
        heat_loss_kwh = max((self.indoor_temperature_c - outdoor_temperature_c) * self.ua_kw_per_k, 0.0)
        net_energy_kwh = supplied_heat_kwh - heat_loss_kwh
        self.indoor_temperature_c += net_energy_kwh / self.thermal_mass_kwh_per_k
        return HeatDemandResult(heat_loss_kwh=heat_loss_kwh, indoor_temperature_c=self.indoor_temperature_c)


@dataclass
class DistrictHeatingSource:
    name: str = "district-heating"
    max_heat_output_kw: float = 12.0
    network_efficiency: float = 0.95

    @property
    def input_carrier(self) -> EnergyCarrier:
        return EnergyCarrier.DISTRICT_HEAT

    def deliver_heat(self, requested_heat_kwh: float, duration_h: float = 1.0) -> float:
        max_deliverable = self.max_heat_output_kw * duration_h
        return min(max(requested_heat_kwh, 0.0), max_deliverable)

    def required_input_energy_kwh(self, delivered_heat_kwh: float) -> float:
        if self.network_efficiency <= 0:
            raise ValueError("network_efficiency must be > 0")
        return delivered_heat_kwh / self.network_efficiency


@dataclass
class ElectricResistanceHeater:
    name: str = "electric-resistance"
    max_heat_output_kw: float = 9.0
    cop: float = 1.0

    @property
    def input_carrier(self) -> EnergyCarrier:
        return EnergyCarrier.ELECTRICITY

    def deliver_heat(self, requested_heat_kwh: float, duration_h: float = 1.0) -> float:
        max_deliverable = self.max_heat_output_kw * duration_h
        return min(max(requested_heat_kwh, 0.0), max_deliverable)

    def required_input_energy_kwh(self, delivered_heat_kwh: float) -> float:
        if self.cop <= 0:
            raise ValueError("cop must be > 0")
        return delivered_heat_kwh / self.cop


@dataclass
class ElectricVehicle:
    battery_capacity_kwh: float
    soc_kwh: float
    max_charging_power_kw: float

    def charge(self, requested_energy_kwh: float, duration_h: float = 1.0) -> float:
        max_energy_this_step = self.max_charging_power_kw * duration_h
        available_battery_room = max(self.battery_capacity_kwh - self.soc_kwh, 0.0)
        accepted = min(max(requested_energy_kwh, 0.0), max_energy_this_step, available_battery_room)
        self.soc_kwh += accepted
        return accepted

    @property
    def soc_percent(self) -> float:
        if self.battery_capacity_kwh == 0:
            return 0.0
        return 100 * self.soc_kwh / self.battery_capacity_kwh


@dataclass
class SimulationStepResult:
    hour_index: int
    outdoor_temperature_c: float
    indoor_temperature_c: float
    target_temperature_c: float
    heating_requested_kwh: float
    heating_delivered_kwh: float
    heating_input_carrier: EnergyCarrier
    heating_input_energy_kwh: float
    ev_requested_kwh: float
    ev_delivered_kwh: float
    electricity_import_kwh: float
    district_heat_import_kwh: float
    step_cost: float


@dataclass
class SimulationReport:
    steps: list[SimulationStepResult] = field(default_factory=list)

    @property
    def total_electricity_import_kwh(self) -> float:
        return sum(s.electricity_import_kwh for s in self.steps)

    @property
    def total_district_heat_import_kwh(self) -> float:
        return sum(s.district_heat_import_kwh for s in self.steps)

    @property
    def total_cost(self) -> float:
        return sum(s.step_cost for s in self.steps)
