"""The three canonical golden cases (SPEC §11) and the value fingerprint
compared against the committed baseline."""

from __future__ import annotations

from besscalc.models import (
    BatterySpec,
    ConsumptionSpec,
    PVSpec,
    ScenarioConfig,
    SimulationRequest,
    SimulationResult,
    SiteSpec,
)

_BATTERY_10 = dict(
    name="Golden 10 kWh",
    capacity_kwh=10.0,
    power_kw=5.0,
    roundtrip_efficiency=0.92,
    depth_of_discharge=0.90,
    calendar_degradation_pct_yr=1.5,
    lifetime_years=15,
    price_dkk_installed=45000.0,
)


def case_a_no_pv() -> SimulationRequest:
    """(a) no PV, 10 kWh battery, DK2/Radius."""
    return SimulationRequest(
        battery=BatterySpec(**_BATTERY_10),
        pv=None,
        consumption=ConsumptionSpec(annual_kwh=4500.0, profile="base"),
        site=SiteSpec(price_area="DK2", dso="radius"),
        scenario=ScenarioConfig(),
    )


def case_b_pv_battery() -> SimulationRequest:
    """(b) 6 kWp PV + 10 kWh battery, DK1/N1."""
    return SimulationRequest(
        battery=BatterySpec(**_BATTERY_10),
        pv=PVSpec(kwp=6.0, orientation="S"),
        consumption=ConsumptionSpec(annual_kwh=5500.0, profile="base_ev"),
        site=SiteSpec(price_area="DK1", dso="n1"),
        scenario=ScenarioConfig(),
    )


def case_c_pv_only_sanity() -> SimulationRequest:
    """(c) PV-only baseline sanity: tiny battery so battery effects vanish."""
    return SimulationRequest(
        battery=BatterySpec(
            **{**_BATTERY_10, "capacity_kwh": 0.001, "power_kw": 0.001, "name": "None"}
        ),
        pv=PVSpec(kwp=6.0, orientation="S"),
        consumption=ConsumptionSpec(annual_kwh=5500.0, profile="base"),
        site=SiteSpec(price_area="DK1", dso="n1"),
        scenario=ScenarioConfig(),
    )


GOLDEN_CASES = {
    "a_no_pv_dk2_radius": case_a_no_pv,
    "b_pv_battery_dk1_n1": case_b_pv_battery,
    "c_pv_only_sanity": case_c_pv_only_sanity,
}


def result_fingerprint(result: SimulationResult) -> dict[str, float]:
    """Flat dict of the economically meaningful outputs."""
    out: dict[str, float] = {"reference_year": result.reference_year}
    for name, s in result.strategies.items():
        for period, bd in (("year1", s.year1), ("lifetime", s.lifetime)):
            prefix = f"{name}.{period}"
            out[f"{prefix}.savings_total_dkk"] = round(bd.savings_total_dkk, 2)
            out[f"{prefix}.savings_self_consumption_dkk"] = round(
                bd.savings_self_consumption_dkk, 2
            )
            out[f"{prefix}.savings_arbitrage_dkk"] = round(bd.savings_arbitrage_dkk, 2)
            out[f"{prefix}.savings_tariff_avoidance_dkk"] = round(
                bd.savings_tariff_avoidance_dkk, 2
            )
            out[f"{prefix}.baseline_cost_dkk"] = round(bd.baseline_cost_dkk, 2)
            out[f"{prefix}.cost_with_battery_dkk"] = round(bd.cost_with_battery_dkk, 2)
        out[f"{name}.npv_dkk"] = round(s.npv_dkk, 2)
        out[f"{name}.annual_savings_dkk_low"] = round(s.annual_savings_dkk_low, 2)
        out[f"{name}.annual_savings_dkk_high"] = round(s.annual_savings_dkk_high, 2)
    return out
