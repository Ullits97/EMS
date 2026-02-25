from ems.models import (
    DistrictHeatingSource,
    ElectricResistanceHeater,
    ElectricVehicle,
    EnergyCarrier,
    House,
    TariffBook,
    TimeOfUseTariff,
)
from ems.simulation import EnergyManagementSimulator, HourInput


def _tariffs() -> TariffBook:
    return TariffBook(
        tariffs={
            EnergyCarrier.ELECTRICITY: TimeOfUseTariff([0.2] * 24),
            EnergyCarrier.DISTRICT_HEAT: TimeOfUseTariff([0.1] * 24),
        }
    )


def _house() -> House:
    return House(
        floor_area_m2=120,
        ua_kw_per_k=0.2,
        thermal_mass_kwh_per_k=20,
        indoor_temperature_c=20,
        target_temperature_c=21,
    )


def test_district_heating_import_goes_to_district_carrier() -> None:
    sim = EnergyManagementSimulator(
        house=_house(),
        heating_source=DistrictHeatingSource(max_heat_output_kw=12, network_efficiency=1.0),
        electric_vehicle=ElectricVehicle(70, 20, 11),
        tariff_book=_tariffs(),
    )
    report = sim.run([HourInput(outdoor_temperature_c=-5.0, ev_charge_request_kwh=0.0)])
    step = report.steps[0]
    assert step.district_heat_import_kwh > 0
    assert step.electricity_import_kwh == 0


def test_electric_heating_import_goes_to_electricity_carrier() -> None:
    sim = EnergyManagementSimulator(
        house=_house(),
        heating_source=ElectricResistanceHeater(max_heat_output_kw=12, cop=1.0),
        electric_vehicle=ElectricVehicle(70, 20, 11),
        tariff_book=_tariffs(),
    )
    report = sim.run([HourInput(outdoor_temperature_c=-5.0, ev_charge_request_kwh=0.0)])
    step = report.steps[0]
    assert step.electricity_import_kwh > 0
    assert step.district_heat_import_kwh == 0


def test_ev_manual_charge_is_limited_by_power() -> None:
    ev = ElectricVehicle(70, 20, 11)
    charged = ev.charge(requested_energy_kwh=20.0, duration_h=1.0)
    assert charged == 11.0
