"""Decomposition sums to total (±1 DKK/yr), degradation schedule, payback
interval and NPV (SPEC §7.3/§11)."""

import pytest

from besscalc.data import load_defaults
from besscalc.economics import npv, payback_years, run_simulation
from besscalc.simulate import simulate_lifetime


def test_decomposition_sums_to_total_every_year(request_pv):
    raw = simulate_lifetime(request_pv)
    tol = float(load_defaults()["decomposition_tolerance_dkk"])
    for strategy, years in raw.years.items():
        for i, year in enumerate(years):
            total = (
                year.savings_self_consumption_dkk
                + year.savings_arbitrage_dkk
                + year.savings_tariff_avoidance_dkk
            )
            assert total == pytest.approx(year.savings_total_dkk, abs=tol), (
                f"{strategy} year {i + 1}"
            )


def test_decomposition_no_pv_has_no_self_consumption(request_no_pv):
    raw = simulate_lifetime(request_no_pv)
    for year in raw.years["price_optimized"]:
        assert year.savings_self_consumption_dkk == pytest.approx(0.0, abs=1e-9)
    for year in raw.years["self_consumption"]:
        # Strategy A cannot do anything without PV.
        assert year.savings_total_dkk == pytest.approx(0.0, abs=1e-9)
        assert year.charge_kwh == pytest.approx(0.0)


def test_degradation_reduces_savings_over_years(request_pv):
    raw = simulate_lifetime(request_pv)
    years = raw.years["self_consumption"]
    # With constant prices (same tax years), savings shrink as capacity degrades.
    tax_change_year = 2028 - raw.start_year
    post = years[tax_change_year:]
    totals = [y.savings_total_dkk for y in post]
    assert all(a >= b for a, b in zip(totals, totals[1:]))


def test_result_intervals_and_scaling(request_pv):
    result = run_simulation(request_pv)
    b = result.strategies["price_optimized"]
    a = result.strategies["self_consumption"]
    # Headline (low) never exceeds upper bound.
    assert b.annual_savings_dkk_low <= b.annual_savings_dkk_high + 1e-9
    # Strategy A interval collapses.
    assert a.annual_savings_dkk_low == pytest.approx(a.annual_savings_dkk_high)
    # Realism scaling: headline = A + f * (B_raw - A) on year-1 totals.
    f = request_pv.scenario.realism_factor
    expected = a.year1.savings_total_dkk + f * (
        b.year1_upper.savings_total_dkk - a.year1.savings_total_dkk
    )
    assert b.year1.savings_total_dkk == pytest.approx(expected, abs=1e-6)
    # Blended decomposition still sums.
    s = (
        b.year1.savings_self_consumption_dkk
        + b.year1.savings_arbitrage_dkk
        + b.year1.savings_tariff_avoidance_dkk
    )
    assert s == pytest.approx(b.year1.savings_total_dkk, abs=1.0)


def test_payback_years_basic():
    assert payback_years(40000, 5000, 15) == pytest.approx(8.0)
    assert payback_years(40000, 0, 15) is None
    assert payback_years(40000, -100, 15) is None
    assert payback_years(40000, 2000, 15) is None  # 20 yr > horizon


def test_npv_hand_computed():
    # -1000 + 500/1.1 + 500/1.21 = -132.23...
    assert npv(1000, [500, 500], 0.10) == pytest.approx(-132.2314, abs=0.001)


def test_cost_without_pv_always_present(request_pv, request_no_pv):
    for req in (request_pv, request_no_pv):
        result = run_simulation(req)
        assert result.cost_without_pv_dkk_year1 > 0


def test_pv_economics_none_without_price_or_pv(request_pv, request_no_pv):
    assert run_simulation(request_no_pv).pv_economics is None
    assert run_simulation(request_no_pv).package_economics is None
    # request_pv has PV but no price by default.
    assert run_simulation(request_pv).pv_economics is None
    assert run_simulation(request_pv).package_economics is None


def test_pv_economics_arithmetic(request_pv):
    priced = request_pv.model_copy(
        update={"pv": request_pv.pv.model_copy(update={"price_dkk_installed": 40000.0})}
    )
    result = run_simulation(priced)
    pv_econ = result.pv_economics
    assert pv_econ is not None
    assert pv_econ.price_dkk_installed == 40000.0
    # Savings year 1 = cost without PV minus cost with PV only (both single points).
    assert pv_econ.savings_dkk_year1 == pytest.approx(
        pv_econ.cost_without_pv_dkk_year1 - pv_econ.cost_with_pv_only_dkk_year1, abs=1e-6
    )
    assert pv_econ.cost_without_pv_dkk_year1 == pytest.approx(result.cost_without_pv_dkk_year1)
    assert pv_econ.payback_years == payback_years(
        40000.0, pv_econ.savings_dkk_avg, priced.battery.lifetime_years
    )


def test_package_economics_combines_prices_and_is_an_interval(request_pv):
    priced = request_pv.model_copy(
        update={"pv": request_pv.pv.model_copy(update={"price_dkk_installed": 40000.0})}
    )
    result = run_simulation(priced)
    pkg = result.package_economics
    assert pkg is not None
    assert pkg.price_dkk_installed == pytest.approx(
        priced.battery.price_dkk_installed + 40000.0
    )
    assert pkg.annual_savings_dkk_low <= pkg.annual_savings_dkk_high + 1e-9
    assert pkg.npv_dkk <= pkg.npv_dkk_high + 1e-9


def test_result_contract(request_pv):
    result = run_simulation(request_pv)
    # SPEC §10 hard requirements.
    assert "vejledende" in result.disclaimer
    assert result.engine_version
    assert result.input_echo == request_pv
    joined = " ".join(result.assumptions)
    for token in ("Referenceår", "tarifversion", "realismefaktor", "degradering", "profil"):
        assert token.lower() in joined.lower(), f"assumption missing: {token}"
    assert result.reference_year >= 2020
