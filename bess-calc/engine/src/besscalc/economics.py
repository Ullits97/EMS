"""Savings decomposition, realism scaling, payback interval and NPV (SPEC §7.3).

The decomposition (self-consumption / arbitrage / tariff avoidance) is
accumulated exactly in the simulation loop and sums to the total savings by
construction; a dedicated test pins this to within 1 DKK/yr.

Strategy-B gains *relative to A* are scaled by the realism factor to produce
the headline (low) figure; the unscaled run is the upper bound (high).
"""

from __future__ import annotations

from .data import load_reference_meta, load_tariffs, load_taxes
from .models import (
    PackageEconomics,
    PVEconomics,
    SavingsBreakdown,
    SimulationRequest,
    SimulationResult,
    StrategyEconomics,
)
from .simulate import LifetimeRaw, YearRun, make_strategies, simulate_lifetime


def _breakdown(run: YearRun) -> SavingsBreakdown:
    return SavingsBreakdown(
        savings_self_consumption_dkk=run.savings_self_consumption_dkk,
        savings_arbitrage_dkk=run.savings_arbitrage_dkk,
        savings_tariff_avoidance_dkk=run.savings_tariff_avoidance_dkk,
        savings_total_dkk=run.savings_total_dkk,
        baseline_cost_dkk=run.baseline_cost_dkk,
        cost_with_battery_dkk=run.cost_dkk,
    )


def _blend(b_run: YearRun, a_run: YearRun, realism: float) -> YearRun:
    """Headline strategy-B year: A + realism * (B - A), component-wise.

    Linear blending preserves the sum-to-total property exactly.
    """

    def mix(b: float, a: float) -> float:
        return a + realism * (b - a)

    return YearRun(
        cost_dkk=mix(b_run.cost_dkk, a_run.cost_dkk),
        baseline_cost_dkk=b_run.baseline_cost_dkk,  # baseline has no battery: identical
        savings_self_consumption_dkk=mix(
            b_run.savings_self_consumption_dkk, a_run.savings_self_consumption_dkk
        ),
        savings_arbitrage_dkk=mix(b_run.savings_arbitrage_dkk, a_run.savings_arbitrage_dkk),
        savings_tariff_avoidance_dkk=mix(
            b_run.savings_tariff_avoidance_dkk, a_run.savings_tariff_avoidance_dkk
        ),
        import_kwh=mix(b_run.import_kwh, a_run.import_kwh),
        export_kwh=mix(b_run.export_kwh, a_run.export_kwh),
        charge_kwh=mix(b_run.charge_kwh, a_run.charge_kwh),
        discharge_kwh=mix(b_run.discharge_kwh, a_run.discharge_kwh),
        losses_kwh=mix(b_run.losses_kwh, a_run.losses_kwh),
    )


def _aggregate(runs: list[YearRun]) -> YearRun:
    return YearRun(
        cost_dkk=sum(r.cost_dkk for r in runs),
        baseline_cost_dkk=sum(r.baseline_cost_dkk for r in runs),
        savings_self_consumption_dkk=sum(r.savings_self_consumption_dkk for r in runs),
        savings_arbitrage_dkk=sum(r.savings_arbitrage_dkk for r in runs),
        savings_tariff_avoidance_dkk=sum(r.savings_tariff_avoidance_dkk for r in runs),
        import_kwh=sum(r.import_kwh for r in runs),
        export_kwh=sum(r.export_kwh for r in runs),
        charge_kwh=sum(r.charge_kwh for r in runs),
        discharge_kwh=sum(r.discharge_kwh for r in runs),
        losses_kwh=sum(r.losses_kwh for r in runs),
    )


def payback_years(price_dkk: float, avg_annual_savings: float, horizon: int) -> float | None:
    """Simple payback from lifetime-average savings; None if not reached in horizon."""
    if avg_annual_savings <= 0:
        return None
    years = price_dkk / avg_annual_savings
    return round(years, 1) if years <= horizon else None


def npv(price_dkk: float, annual_savings: list[float], rate: float) -> float:
    return -price_dkk + sum(s / (1.0 + rate) ** (y + 1) for y, s in enumerate(annual_savings))


def _strategy_economics(
    name: str,
    label_da: str,
    headline_years: list[YearRun],
    upper_years: list[YearRun],
    request: SimulationRequest,
) -> StrategyEconomics:
    price = request.battery.price_dkk_installed
    horizon = request.battery.lifetime_years
    rate = request.scenario.discount_rate

    lifetime_headline = _aggregate(headline_years)
    lifetime_upper = _aggregate(upper_years)
    avg_low = lifetime_headline.savings_total_dkk / horizon
    avg_high = lifetime_upper.savings_total_dkk / horizon

    return StrategyEconomics(
        strategy=name,
        label_da=label_da,
        year1=_breakdown(headline_years[0]),
        year1_upper=_breakdown(upper_years[0]),
        lifetime=_breakdown(lifetime_headline),
        lifetime_upper=_breakdown(lifetime_upper),
        annual_savings_dkk_low=avg_low,
        annual_savings_dkk_high=avg_high,
        payback_years_low=payback_years(price, avg_high, horizon),
        payback_years_high=payback_years(price, avg_low, horizon),
        npv_dkk=npv(price, [r.savings_total_dkk for r in headline_years], rate),
        npv_dkk_high=npv(price, [r.savings_total_dkk for r in upper_years], rate),
    )


def _pv_economics(request: SimulationRequest, raw: LifetimeRaw) -> PVEconomics | None:
    """Standalone PV-only business case vs. no system at all (no battery)."""
    if request.pv is None or request.pv.price_dkk_installed is None:
        return None
    horizon = request.battery.lifetime_years
    rate = request.scenario.discount_rate
    price = request.pv.price_dkk_installed

    any_strategy_years = next(iter(raw.years.values()))
    cost_with_pv = [y.baseline_cost_dkk for y in any_strategy_years]
    cost_without_pv = raw.no_pv_years
    annual_savings = [wo - w for wo, w in zip(cost_without_pv, cost_with_pv)]
    avg_savings = sum(annual_savings) / horizon

    return PVEconomics(
        price_dkk_installed=price,
        cost_without_pv_dkk_year1=cost_without_pv[0],
        cost_with_pv_only_dkk_year1=cost_with_pv[0],
        savings_dkk_year1=annual_savings[0],
        savings_dkk_avg=avg_savings,
        payback_years=payback_years(price, avg_savings, horizon),
        npv_dkk=npv(price, annual_savings, rate),
    )


def _package_economics(
    request: SimulationRequest,
    raw: LifetimeRaw,
    b_headline: list[YearRun],
    b_years: list[YearRun],
) -> PackageEconomics | None:
    """Combined PV+battery investment vs. no system at all. Interval, because
    it includes the battery's dispatch strategy (price_optimized)."""
    if request.pv is None or request.pv.price_dkk_installed is None:
        return None
    horizon = request.battery.lifetime_years
    rate = request.scenario.discount_rate
    total_price = request.battery.price_dkk_installed + request.pv.price_dkk_installed

    savings_headline = [no - b.cost_dkk for no, b in zip(raw.no_pv_years, b_headline)]
    savings_upper = [no - b.cost_dkk for no, b in zip(raw.no_pv_years, b_years)]
    avg_low = sum(savings_headline) / horizon
    avg_high = sum(savings_upper) / horizon

    return PackageEconomics(
        price_dkk_installed=total_price,
        annual_savings_dkk_low=avg_low,
        annual_savings_dkk_high=avg_high,
        payback_years_low=payback_years(total_price, avg_high, horizon),
        payback_years_high=payback_years(total_price, avg_low, horizon),
        npv_dkk=npv(total_price, savings_headline, rate),
        npv_dkk_high=npv(total_price, savings_upper, rate),
    )


def build_assumptions(request: SimulationRequest, raw: LifetimeRaw) -> list[str]:
    """Machine-generated assumption list (Danish), SPEC §10 item 3."""
    meta = load_reference_meta()
    tariff_meta = load_tariffs().get("meta", {})
    taxes = load_taxes()
    dso_name = load_tariffs()["dsos"][request.site.dso].get("display_name", request.site.dso)

    source = meta.get("spot_source", "ukendt kilde")
    assumptions = [
        f"Referenceår for priser og profiler: {raw.reference_year} ({source}).",
    ]
    if meta.get("synthetic"):
        assumptions.append(
            "ADVARSEL: Referencedata er syntetiske pladsholdere — kør ingestion-scripts "
            "med rigtige data, før resultater vises eksternt."
        )
    assumptions += [
        f"Netselskab: {dso_name}, tarifversion {tariff_meta.get('version_date', 'ukendt')}"
        + (" (satser ikke verificeret)." if not tariff_meta.get("verified") else "."),
        f"Afgiftsscenarie: {request.scenario.tax_scenario} med årsindekseret elafgift; "
        f"moms {taxes['vat_rate'] * 100:.0f}% på hele købsprisen (satser ikke verificeret).",
        f"Elaftale: spotpris + {request.site.supplier_markup_dkk_kwh * 100:.1f} øre/kWh "
        "leverandørtillæg.",
        f"Forbrugsprofil: '{request.consumption.profile}' "
        f"({request.consumption.annual_kwh:.0f} kWh/år), standardiseret syntetisk profil.",
        (
            f"Solceller: {request.pv.kwp:.1f} kWp, orientering {request.pv.orientation}, "
            f"hældning {request.pv.tilt_deg}°."
            if request.pv
            else "Ingen solceller medregnet."
        ),
        f"Batteridegradering: lineær {request.battery.calendar_degradation_pct_yr:.1f}%/år "
        f"over {request.battery.lifetime_years} år; hvert år simuleres med reduceret kapacitet.",
        f"Prisoptimeret styring antager kendte day-ahead-priser; gevinsten er skaleret med "
        f"realismefaktor {request.scenario.realism_factor:.2f} (interval viser begge).",
        "Batteriet eksporterer ikke til nettet (kun solcelleoverskud sælges) — det holder "
        "afgiftsbehandlingen simpel.",
        "Salg afregnes som spot minus indfødningsgebyr; ingen elafgift eller moms på salg for "
        "private (regler ikke verificeret). " + taxes.get("sell_side_note_da", ""),
        f"Nutidsværdi (NPV) beregnet med {request.scenario.discount_rate * 100:.1f}% "
        "diskonteringsrente.",
    ]
    if request.pv and request.pv.price_dkk_installed:
        assumptions.append(
            "Solceller alene og den samlede pakke (solceller + batteri): tilbagebetalingstid "
            f"og nutidsværdi beregnes over samme horisont ({request.battery.lifetime_years} år) "
            "og diskonteringsrente som batteriet, uden separat levetid for solcelleanlægget."
        )
    return assumptions


def run_simulation(request: SimulationRequest) -> SimulationResult:
    """Full pipeline: simulate lifetime, apply realism scaling, build result."""
    raw = simulate_lifetime(request)
    realism = request.scenario.realism_factor
    strategies = {s.name: s for s in make_strategies()}

    a_years = raw.years["self_consumption"]
    b_years = raw.years["price_optimized"]
    b_headline = [_blend(b, a, realism) for b, a in zip(b_years, a_years)]

    result_strategies = {
        "self_consumption": _strategy_economics(
            "self_consumption",
            strategies["self_consumption"].label_da,
            a_years,
            a_years,  # rule mirrors reality closely: interval collapses
            request,
        ),
        "price_optimized": _strategy_economics(
            "price_optimized",
            strategies["price_optimized"].label_da,
            b_headline,
            b_years,
            request,
        ),
    }
    return SimulationResult(
        strategies=result_strategies,
        reference_year=raw.reference_year,
        assumptions=build_assumptions(request, raw),
        input_echo=request,
        cost_without_pv_dkk_year1=raw.no_pv_years[0],
        pv_economics=_pv_economics(request, raw),
        package_economics=_package_economics(request, raw, b_headline, b_years),
    )
