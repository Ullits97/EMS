"""Main simulation loop: full reference year at 15-min resolution, plus the
lifetime driver that re-runs the year with calendar degradation (SPEC §7).

Energy balance invariant (ported HEMS pattern), checked at runtime on every
step with battery activity and aggregated per year:

    pv + import == load + export + losses + delta_SoC

which is the SPEC §7.1 formulation `pv + import + discharge == load + export
+ charge + losses` with charge/discharge measured on the storage side.
delta_SoC is read from the Battery instance, so the check verifies the
battery physics against the loop's cash-flow quantities. Violations raise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .components.battery import GRID, PV, Battery
from .components.consumption import consumption_series
from .components.pv import pv_generation
from .data import STEP_HOURS, load_defaults, load_spot
from .dispatch import DispatchStrategy, PriceOptimizedStrategy, SelfConsumptionStrategy
from .models import SimulationRequest
from .prices import PriceSet, build_prices, elafgift_for_year, vat_factor


class EnergyBalanceError(RuntimeError):
    """The per-step energy balance invariant was violated."""


@dataclass
class YearRun:
    """Raw (unscaled) results of simulating one strategy for one year."""

    cost_dkk: float
    baseline_cost_dkk: float
    savings_self_consumption_dkk: float
    savings_arbitrage_dkk: float
    savings_tariff_avoidance_dkk: float
    import_kwh: float
    export_kwh: float
    charge_kwh: float
    discharge_kwh: float
    losses_kwh: float

    @property
    def savings_total_dkk(self) -> float:
        return self.baseline_cost_dkk - self.cost_dkk


@dataclass
class LifetimeRaw:
    """Raw per-year results for both strategies over the battery lifetime."""

    years: dict[str, list[YearRun]]  # strategy name -> YearRun per year (index 0 = year 1)
    reference_year: int
    start_year: int


def _day_start_indices(index: pd.DatetimeIndex) -> np.ndarray:
    """First slot index of each local day (variable day length across DST)."""
    days = index.normalize()
    return np.unique(days, return_index=True)[1]


@dataclass
class YearPlan:
    """Full-year slot permissions plus per-day grid-charge budgets."""

    pv_charge_ok: list[bool]
    grid_charge_ok: list[bool]
    discharge_ok: list[bool]
    day_starts: list[int]  # slot index where each local day begins
    grid_budgets_kwh: list[float]  # one per day, bus-side


def build_year_plan(
    buy: np.ndarray,
    pv: np.ndarray,
    load: np.ndarray,
    day_starts: np.ndarray,
    strategy: DispatchStrategy,
) -> YearPlan:
    """Concatenate per-day slot permissions into full-year lists.

    Buy-price *rankings* within a day are invariant across simulation years
    (elafgift shifts the whole year by a constant), so one plan per strategy
    serves the whole lifetime.
    """
    n = len(buy)
    bounds = list(day_starts) + [n]
    pv_ok = np.empty(n, dtype=bool)
    grid_ok = np.empty(n, dtype=bool)
    dis_ok = np.empty(n, dtype=bool)
    budgets: list[float] = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        plan = strategy.plan_day(buy[lo:hi], pv[lo:hi], load[lo:hi])
        pv_ok[lo:hi] = plan.pv_charge_ok
        grid_ok[lo:hi] = plan.grid_charge_ok
        dis_ok[lo:hi] = plan.discharge_ok
        budgets.append(plan.grid_charge_budget_kwh)
    return YearPlan(
        pv_charge_ok=pv_ok.tolist(),
        grid_charge_ok=grid_ok.tolist(),
        discharge_ok=dis_ok.tolist(),
        day_starts=[int(s) for s in day_starts],
        grid_budgets_kwh=budgets,
    )


def baseline_cost(pv: np.ndarray, load: np.ndarray, prices: PriceSet) -> float:
    """Grid cost without a battery (same PV), vectorized."""
    net = load - pv
    imp = np.maximum(net, 0.0)
    exp = np.maximum(-net, 0.0)
    return float(imp @ prices.buy - exp @ prices.sell)


def run_year(
    pv: np.ndarray,
    load: np.ndarray,
    prices: PriceSet,
    plan: YearPlan,
    battery: Battery,
    tolerance_kwh: float,
) -> YearRun:
    """Simulate one calendar year for one strategy. Mutates `battery` SoC."""
    n = len(load)
    pv_l = pv.tolist()
    load_l = load.tolist()
    buy_l = prices.buy.tolist()
    sell_l = prices.sell.tolist()
    spot_c = prices.spot_component.tolist()
    grid_c = prices.tariff_tax_component.tolist()
    pv_ok = plan.pv_charge_ok
    grid_ok = plan.grid_charge_ok
    dis_ok = plan.discharge_ok
    budgets = plan.grid_budgets_kwh
    next_day_starts = plan.day_starts[1:] + [n + 1]

    bat_charge = battery.charge
    bat_discharge = battery.discharge
    power_step = battery.power_step_kwh
    eff = battery.efficiency
    loss_c = 1.0 - eff  # bus->storage loss fraction
    loss_d = 1.0 / eff - 1.0  # storage->bus loss per delivered kWh

    cost = 0.0
    sc = 0.0  # self-consumption value
    arb = 0.0  # arbitrage value
    tar = 0.0  # tariff+tax avoidance value
    imp_tot = 0.0
    exp_tot = 0.0
    charge_tot = 0.0
    discharge_tot = 0.0
    losses_tot = 0.0

    day_i = -1
    next_day_at = 0
    grid_budget = 0.0
    for t in range(n):
        if t == next_day_at:
            day_i += 1
            grid_budget = budgets[day_i]
            next_day_at = next_day_starts[day_i]
        lo = load_l[t]
        p = pv_l[t]
        diff = p - lo
        if diff > 0.0:
            pvs = diff
            res = 0.0
        else:
            pvs = 0.0
            res = -diff

        c_pv = 0.0
        c_g = 0.0
        d = 0.0
        if pvs > 0.0 and pv_ok[t]:
            c_pv = bat_charge(pvs, PV)
            if c_pv > 0.0:
                sc -= c_pv * sell_l[t]  # lost export revenue
        if grid_ok[t] and grid_budget > 0.0:
            c_g = bat_charge(grid_budget, GRID, power_step - c_pv)
            if c_g > 0.0:
                grid_budget -= c_g
                arb -= c_g * spot_c[t]
                tar -= c_g * grid_c[t]
        if res > 0.0 and dis_ok[t] and c_pv == 0.0 and c_g == 0.0:
            d, pv_frac = bat_discharge(res)
            if d > 0.0:
                spot_value = d * spot_c[t]
                sc += spot_value * pv_frac
                arb += spot_value * (1.0 - pv_frac)
                tar += d * grid_c[t]

        imp = res + c_g - d
        exp = pvs - c_pv
        cost += imp * buy_l[t] - exp * sell_l[t]

        if c_pv > 0.0 or c_g > 0.0 or d > 0.0:
            c = c_pv + c_g
            step_loss = c * loss_c + d * loss_d
            charge_tot += c
            discharge_tot += d
            losses_tot += step_loss
            soc = battery.soc
            if soc < battery.soc_min - tolerance_kwh or soc > battery.soc_max + tolerance_kwh:
                raise EnergyBalanceError(f"SoC {soc:.9f} outside window at step {t}")
            delta_soc = c * eff - d / eff
            err = p + imp - lo - exp - step_loss - delta_soc
            if err > tolerance_kwh or err < -tolerance_kwh:
                raise EnergyBalanceError(f"Energy balance violated by {err:.3e} kWh at step {t}")
        imp_tot += imp
        exp_tot += exp

    # Year-aggregate consistency between loop bookkeeping and battery state.
    expected_soc = battery.soc_min + charge_tot * eff - discharge_tot / eff
    if abs(expected_soc - battery.soc) > tolerance_kwh * n:
        raise EnergyBalanceError("Year-aggregate SoC bookkeeping diverged from battery state")
    buckets = battery.stored_pv + battery.stored_grid
    if abs(buckets - battery.usable_kwh) > tolerance_kwh * n:
        raise EnergyBalanceError("Battery origin buckets diverged from SoC")

    return YearRun(
        cost_dkk=cost,
        baseline_cost_dkk=baseline_cost(pv, load, prices),
        savings_self_consumption_dkk=sc,
        savings_arbitrage_dkk=arb,
        savings_tariff_avoidance_dkk=tar,
        import_kwh=imp_tot,
        export_kwh=exp_tot,
        charge_kwh=charge_tot,
        discharge_kwh=discharge_tot,
        losses_kwh=losses_tot,
    )


def make_strategies(
    defaults: dict | None = None, roundtrip_efficiency: float = 0.92
) -> list[DispatchStrategy]:
    cfg = (defaults or load_defaults()).get("strategy_b", {})
    return [
        SelfConsumptionStrategy(),
        PriceOptimizedStrategy(
            charge_quantile=cfg.get("charge_quantile", 0.25),
            discharge_quantile=cfg.get("discharge_quantile", 0.25),
            no_charge_quantile=cfg.get("no_charge_quantile", 0.75),
            roundtrip_efficiency=roundtrip_efficiency,
        ),
    ]


def simulate_lifetime(request: SimulationRequest) -> LifetimeRaw:
    """Simulate year 1 in full detail and re-run every lifetime year with
    linearly degraded capacity and the year-indexed tax timeline."""
    defaults = load_defaults()
    tolerance = float(defaults["energy_balance_tolerance_kwh"])
    start_year = int(defaults["start_year"])

    spot = load_spot(request.site.price_area)
    index = spot.index
    n = len(index)
    reference_year = int(index[0].year)

    pv = pv_generation(request.pv, n)
    load = consumption_series(request.consumption, n)
    day_starts = _day_start_indices(index)

    vat = vat_factor()
    year1_prices = build_prices(spot, request.site, request.scenario.tax_scenario, start_year)
    elafgift_y1 = elafgift_for_year(request.scenario.tax_scenario, start_year)

    strategies = make_strategies(defaults, request.battery.roundtrip_efficiency)
    plans = {
        s.name: build_year_plan(year1_prices.buy, pv, load, day_starts, s) for s in strategies
    }

    deg_rate = request.battery.calendar_degradation_pct_yr / 100.0
    years: dict[str, list[YearRun]] = {s.name: [] for s in strategies}

    for year_offset in range(request.battery.lifetime_years):
        sim_year = start_year + year_offset
        delta = (elafgift_for_year(request.scenario.tax_scenario, sim_year) - elafgift_y1) * vat
        if delta == 0.0:
            prices = year1_prices
        else:
            prices = PriceSet(
                buy=year1_prices.buy + delta,
                sell=year1_prices.sell,
                spot_component=year1_prices.spot_component,
                tariff_tax_component=year1_prices.tariff_tax_component + delta,
            )
        capacity_factor = max(1.0 - deg_rate * year_offset, 0.05)
        for strategy in strategies:
            battery = Battery(request.battery, capacity_factor, STEP_HOURS)
            years[strategy.name].append(
                run_year(pv, load, prices, plans[strategy.name], battery, tolerance)
            )

    return LifetimeRaw(years=years, reference_year=reference_year, start_year=start_year)
