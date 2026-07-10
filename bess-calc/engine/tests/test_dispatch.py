"""Dispatch strategy rules (SPEC §7.2)."""

import numpy as np
import pytest

from besscalc.dispatch import PriceOptimizedStrategy, SelfConsumptionStrategy


def day(prices):
    return np.asarray(prices, dtype=float)


def test_strategy_a_never_grid_charges():
    plan = SelfConsumptionStrategy().plan_day(day(range(96)), np.zeros(96), np.ones(96))
    assert not plan.grid_charge_ok.any()
    assert plan.pv_charge_ok.all()
    assert plan.discharge_ok.all()
    assert plan.grid_charge_budget_kwh == 0.0


def test_strategy_b_never_charges_in_top_quartile():
    prices = day(range(96))  # strictly increasing
    strat = PriceOptimizedStrategy(no_charge_quantile=0.75)
    plan = strat.plan_day(prices, np.zeros(96), np.ones(96))
    top_quartile = prices >= np.sort(prices)[72]
    assert not (plan.grid_charge_ok & top_quartile).any()
    assert not (plan.pv_charge_ok & top_quartile).any()


def test_strategy_b_grid_charges_only_cheapest_slots():
    prices = day(range(96))
    strat = PriceOptimizedStrategy(charge_quantile=0.25)
    plan = strat.plan_day(prices, np.zeros(96), np.ones(96))
    assert plan.grid_charge_ok.sum() == 24
    assert plan.grid_charge_ok[:24].all()
    # Charge and discharge sets are disjoint.
    assert not (plan.grid_charge_ok & plan.discharge_ok).any()


def test_strategy_b_discharges_in_expensive_slots():
    prices = day(range(96))
    plan = PriceOptimizedStrategy().plan_day(prices, np.zeros(96), np.ones(96))
    assert plan.discharge_ok[-24:].all()  # top quartile always dischargeable


def test_strategy_b_budget_reflects_shiftable_need():
    prices = day(range(96))
    load = np.full(96, 0.5)
    no_pv_plan = PriceOptimizedStrategy(roundtrip_efficiency=1.0).plan_day(
        prices, np.zeros(96), load
    )
    # Without PV the budget equals the residual load in discharge slots.
    expected = load[no_pv_plan.discharge_ok].sum()
    assert no_pv_plan.grid_charge_budget_kwh == pytest.approx(expected)

    # Abundant PV surplus wipes out the grid-charge budget.
    pv = np.full(96, 5.0)
    pv_plan = PriceOptimizedStrategy(roundtrip_efficiency=1.0).plan_day(prices, pv, load)
    assert pv_plan.grid_charge_budget_kwh == 0.0


def test_strategy_b_handles_dst_day_lengths():
    for n in (92, 96, 100):
        plan = PriceOptimizedStrategy().plan_day(day(range(n)), np.zeros(n), np.ones(n))
        assert len(plan.grid_charge_ok) == n


def test_invalid_quantiles_rejected():
    with pytest.raises(ValueError):
        PriceOptimizedStrategy(charge_quantile=1.5)
    with pytest.raises(ValueError):
        PriceOptimizedStrategy(charge_quantile=0.8, no_charge_quantile=0.5)
