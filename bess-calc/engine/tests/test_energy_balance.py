"""Property-style test: the energy balance invariant holds over the full
year for ~20 seeded random configs (SPEC §7.1/§11). The invariant itself is
checked inside run_year (violations raise EnergyBalanceError); here we just
drive it plus verify aggregate conservation on the returned figures.
"""

import random

import pytest

from besscalc.components.battery import Battery
from besscalc.components.consumption import consumption_series
from besscalc.components.pv import pv_generation
from besscalc.data import STEP_HOURS, load_defaults, load_spot
from besscalc.models import (
    BatterySpec,
    ConsumptionSpec,
    PVSpec,
    ScenarioConfig,
    SimulationRequest,
    SiteSpec,
)
from besscalc.prices import build_prices
from besscalc.simulate import _day_start_indices, build_year_plan, make_strategies, run_year

N_CONFIGS = 20
SEED = 1234


def random_request(rng: random.Random) -> SimulationRequest:
    battery = BatterySpec(
        name="prop",
        capacity_kwh=rng.uniform(3.0, 25.0),
        power_kw=rng.uniform(1.5, 12.0),
        roundtrip_efficiency=rng.uniform(0.80, 0.98),
        depth_of_discharge=rng.uniform(0.6, 1.0),
        calendar_degradation_pct_yr=rng.uniform(0.0, 4.0),
        lifetime_years=rng.randint(5, 20),
        price_dkk_installed=rng.uniform(20000, 90000),
    )
    pv = None
    if rng.random() < 0.7:
        pv = PVSpec(
            kwp=rng.uniform(1.0, 12.0),
            orientation=rng.choice(["S", "SE_SW", "E_W"]),
        )
    return SimulationRequest(
        battery=battery,
        pv=pv,
        consumption=ConsumptionSpec(
            annual_kwh=rng.uniform(1500, 12000),
            profile=rng.choice(["base", "base_ev", "base_hp", "base_ev_hp"]),
        ),
        site=SiteSpec(
            price_area=rng.choice(["DK1", "DK2"]),
            dso=rng.choice(["n1", "radius", "cerius"]),
            supplier_markup_dkk_kwh=rng.uniform(0.0, 0.15),
        ),
        scenario=ScenarioConfig(
            tax_scenario=rng.choice(["low_2026_27", "normalized_post_2027"]),
        ),
    )


@pytest.mark.parametrize("config_i", range(N_CONFIGS))
def test_energy_balance_invariant_full_year(config_i):
    rng = random.Random(SEED + config_i)
    request = random_request(rng)
    tolerance = float(load_defaults()["energy_balance_tolerance_kwh"])

    spot = load_spot(request.site.price_area)
    n = len(spot)
    pv = pv_generation(request.pv, n)
    load = consumption_series(request.consumption, n)
    prices = build_prices(spot, request.site, request.scenario.tax_scenario, 2026)
    day_starts = _day_start_indices(spot.index)

    for strategy in make_strategies(None, request.battery.roundtrip_efficiency):
        plan = build_year_plan(prices.buy, pv, load, day_starts, strategy)
        battery = Battery(request.battery, 1.0, STEP_HOURS)
        # run_year raises EnergyBalanceError on any per-step violation.
        result = run_year(pv, load, prices, plan, battery, tolerance)

        # Aggregate conservation: pv + import == load + export + losses + dSoC.
        d_soc = battery.soc - battery.soc_min
        lhs = pv.sum() + result.import_kwh
        rhs = load.sum() + result.export_kwh + result.losses_kwh + d_soc
        assert lhs == pytest.approx(rhs, abs=tolerance * n)

        # Physical sanity.
        assert result.import_kwh >= 0
        assert result.export_kwh >= 0
        assert result.losses_kwh >= 0
        assert battery.soc_min - tolerance <= battery.soc <= battery.soc_max + tolerance
