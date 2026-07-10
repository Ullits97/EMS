"""Battery physics: SoC limits, efficiency split, power caps, origin buckets."""

import math

import pytest

from besscalc.components.battery import GRID, PV, Battery
from besscalc.models import BatterySpec


def make(capacity=10.0, power=5.0, rte=0.81, dod=0.9, factor=1.0) -> Battery:
    spec = BatterySpec(
        name="t",
        capacity_kwh=capacity,
        power_kw=power,
        roundtrip_efficiency=rte,
        depth_of_discharge=dod,
        price_dkk_installed=1.0,
    )
    return Battery(spec, capacity_factor=factor, step_hours=0.25)


def test_starts_empty_at_soc_min():
    b = make()
    assert b.soc == pytest.approx(1.0)  # (1 - 0.9) * 10
    assert b.usable_kwh == 0.0


def test_charge_applies_sqrt_efficiency():
    b = make(rte=0.81)  # eff per direction = 0.9
    drawn = b.charge(1.0, PV)
    assert drawn == pytest.approx(1.0)
    assert b.usable_kwh == pytest.approx(0.9)


def test_discharge_applies_sqrt_efficiency():
    b = make(rte=0.81)
    b.charge(1.0, PV)
    delivered, pv_frac = b.discharge(10.0)
    assert delivered == pytest.approx(0.9 * 0.9)  # full roundtrip = rte
    assert pv_frac == pytest.approx(1.0)
    assert b.usable_kwh == pytest.approx(0.0, abs=1e-12)


def test_power_cap_per_step():
    b = make(power=5.0)  # 1.25 kWh per 15-min step
    assert b.charge(100.0, PV) == pytest.approx(1.25)
    b2 = make(power=5.0)
    b2.charge(1.25, PV)
    b2.charge(1.25, PV)
    delivered, _ = b2.discharge(100.0)
    assert delivered == pytest.approx(1.25)


def test_soc_never_exceeds_window():
    b = make(capacity=2.0, power=100.0, dod=0.9)
    for _ in range(100):
        b.charge(5.0, GRID)
    assert b.soc <= b.soc_max + 1e-12
    for _ in range(100):
        b.discharge(5.0)
    assert b.soc >= b.soc_min - 1e-12


def test_depth_of_discharge_limits_usable_energy():
    b = make(capacity=10.0, power=1000.0, rte=1.0, dod=0.8)
    b.charge(100.0, PV)
    delivered, _ = b.discharge(100.0)
    assert delivered == pytest.approx(8.0)


def test_origin_buckets_proportional_discharge():
    b = make(capacity=10.0, power=1000.0, rte=1.0)
    b.charge(3.0, PV)
    b.charge(6.0, GRID)
    delivered, pv_frac = b.discharge(4.5)
    assert delivered == pytest.approx(4.5)
    assert pv_frac == pytest.approx(1.0 / 3.0)
    # Remaining buckets keep the same mix.
    assert b.stored_pv == pytest.approx(1.5)
    assert b.stored_grid == pytest.approx(3.0)


def test_capacity_factor_scales_window():
    b = make(capacity=10.0, factor=0.9)
    assert b.soc_max == pytest.approx(9.0)
    assert b.soc_min == pytest.approx(0.9)
    assert math.isclose(b.soc_max - b.soc_min, 8.1)


def test_charge_budget_argument():
    b = make(power=5.0)
    assert b.charge(10.0, PV, power_budget_kwh=0.5) == pytest.approx(0.5)


def test_invalid_capacity_factor_rejected():
    with pytest.raises(ValueError):
        make(factor=0.0)
