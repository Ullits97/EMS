from __future__ import annotations

import argparse

from ems.models import (
    DistrictHeatingSource,
    ElectricResistanceHeater,
    ElectricVehicle,
    EnergyCarrier,
    House,
    TariffBook,
    TimeOfUseTariff,
)
from ems.reporting import build_console_summary, write_temp_report
from ems.simulation import EnergyManagementSimulator, HourInput


def default_tariff_book() -> TariffBook:
    electricity_tou = TimeOfUseTariff(
        hourly_prices=[
            0.12, 0.12, 0.11, 0.11, 0.11, 0.13, 0.17, 0.20, 0.22, 0.23, 0.21, 0.19,
            0.18, 0.18, 0.19, 0.23, 0.27, 0.31, 0.29, 0.24, 0.20, 0.17, 0.15, 0.13,
        ]
    )
    district_heat_tou = TimeOfUseTariff(hourly_prices=[0.09] * 24)
    return TariffBook(
        tariffs={
            EnergyCarrier.ELECTRICITY: electricity_tou,
            EnergyCarrier.DISTRICT_HEAT: district_heat_tou,
        }
    )


def build_hourly_inputs(hours: int, manual_ev_charge_kwh: float, charge_start_hour: int) -> list[HourInput]:
    inputs: list[HourInput] = []
    for h in range(hours):
        hod = h % 24
        outdoor = 1.0 if 8 <= hod <= 18 else -4.0
        ev_request = manual_ev_charge_kwh if hod == charge_start_hour else 0.0
        setpoint = 21.0 if 6 <= hod <= 22 else 19.0
        inputs.append(HourInput(outdoor_temperature_c=outdoor, ev_charge_request_kwh=ev_request, temperature_setpoint_c=setpoint))
    return inputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OOP Energy Management System MVP")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--ev-charge-kwh", type=float, default=7.0)
    parser.add_argument("--ev-charge-hour", type=int, default=22)
    parser.add_argument("--heating-source", choices=["district", "electric"], default="district")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    house = House(
        floor_area_m2=140.0,
        ua_kw_per_k=0.18,
        thermal_mass_kwh_per_k=18.0,
        indoor_temperature_c=20.0,
        target_temperature_c=21.0,
    )
    heating_source = DistrictHeatingSource(max_heat_output_kw=12.0) if args.heating_source == "district" else ElectricResistanceHeater(max_heat_output_kw=9.0, cop=1.0)
    ev = ElectricVehicle(battery_capacity_kwh=70.0, soc_kwh=20.0, max_charging_power_kw=11.0)

    sim = EnergyManagementSimulator(house, heating_source, ev, default_tariff_book())
    report = sim.run(build_hourly_inputs(args.hours, args.ev_charge_kwh, args.ev_charge_hour))

    print(f"Heating source: {heating_source.name}")
    print(build_console_summary(report))
    report_path = write_temp_report(report)
    print(f"\nTemporary report written to: {report_path}")
    print(f"EV SoC at end: {ev.soc_kwh:.2f} kWh ({ev.soc_percent:.1f}%)")


if __name__ == "__main__":
    main()
