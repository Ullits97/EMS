from ems.models import House


def _house() -> House:
    return House(
        floor_area_m2=120,
        ua_kw_per_k=0.2,
        thermal_mass_kwh_per_k=20,
        indoor_temperature_c=20,
        target_temperature_c=21,
    )


def test_heat_loss_depends_on_outdoor_temperature() -> None:
    house = _house()
    loss_cold = house.compute_heat_loss_kwh(outdoor_temperature_c=-5.0)
    loss_warm = house.compute_heat_loss_kwh(outdoor_temperature_c=10.0)
    assert loss_cold > loss_warm


def test_heat_loss_factor_is_variable() -> None:
    house = _house()
    base = house.compute_heat_loss_kwh(outdoor_temperature_c=0.0)
    house.set_heat_loss_factor(0.4)
    changed = house.compute_heat_loss_kwh(outdoor_temperature_c=0.0)
    assert changed > base


def test_target_temperature_can_be_set() -> None:
    house = _house()
    before = house.estimate_hourly_heat_demand(outdoor_temperature_c=0.0)
    house.set_target_temperature(24.0)
    after = house.estimate_hourly_heat_demand(outdoor_temperature_c=0.0)
    assert after > before
