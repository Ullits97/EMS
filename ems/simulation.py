from __future__ import annotations

from dataclasses import dataclass

from ems.models import (
    ElectricVehicle,
    EnergyCarrier,
    HeatingSource,
    House,
    SimulationReport,
    SimulationStepResult,
    TariffBook,
)


@dataclass
class HourInput:
    outdoor_temperature_c: float
    ev_charge_request_kwh: float = 0.0
    temperature_setpoint_c: float | None = None


class EnergyManagementSimulator:
    """Coordinates subsystems with extensible, pluggable assets."""

    def __init__(
        self,
        house: House,
        heating_source: HeatingSource,
        electric_vehicle: ElectricVehicle,
        tariff_book: TariffBook,
    ) -> None:
        self.house = house
        self.heating_source = heating_source
        self.electric_vehicle = electric_vehicle
        self.tariff_book = tariff_book

    def run(self, hourly_inputs: list[HourInput], start_hour: int = 0) -> SimulationReport:
        report = SimulationReport()

        for i, hour_data in enumerate(hourly_inputs):
            hour_of_day = (start_hour + i) % 24

            if hour_data.temperature_setpoint_c is not None:
                self.house.set_target_temperature(hour_data.temperature_setpoint_c)

            heating_requested_kwh = self.house.estimate_hourly_heat_demand(hour_data.outdoor_temperature_c)
            heating_delivered_kwh = self.heating_source.deliver_heat(heating_requested_kwh)
            _ = self.house.advance_one_hour(
                supplied_heat_kwh=heating_delivered_kwh,
                outdoor_temperature_c=hour_data.outdoor_temperature_c,
            )

            ev_delivered_kwh = self.electric_vehicle.charge(hour_data.ev_charge_request_kwh)
            heating_input_energy_kwh = self.heating_source.required_input_energy_kwh(heating_delivered_kwh)

            electricity_import_kwh = ev_delivered_kwh
            district_heat_import_kwh = 0.0
            if self.heating_source.input_carrier == EnergyCarrier.ELECTRICITY:
                electricity_import_kwh += heating_input_energy_kwh
            elif self.heating_source.input_carrier == EnergyCarrier.DISTRICT_HEAT:
                district_heat_import_kwh += heating_input_energy_kwh

            step_cost = (
                electricity_import_kwh * self.tariff_book.price_for(EnergyCarrier.ELECTRICITY, hour_of_day)
                + district_heat_import_kwh * self.tariff_book.price_for(EnergyCarrier.DISTRICT_HEAT, hour_of_day)
            )

            report.steps.append(
                SimulationStepResult(
                    hour_index=i,
                    outdoor_temperature_c=hour_data.outdoor_temperature_c,
                    indoor_temperature_c=self.house.indoor_temperature_c,
                    target_temperature_c=self.house.target_temperature_c,
                    heating_requested_kwh=heating_requested_kwh,
                    heating_delivered_kwh=heating_delivered_kwh,
                    heating_input_carrier=self.heating_source.input_carrier,
                    heating_input_energy_kwh=heating_input_energy_kwh,
                    ev_requested_kwh=hour_data.ev_charge_request_kwh,
                    ev_delivered_kwh=ev_delivered_kwh,
                    electricity_import_kwh=electricity_import_kwh,
                    district_heat_import_kwh=district_heat_import_kwh,
                    step_cost=step_cost,
                )
            )

        return report
