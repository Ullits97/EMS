"""Pydantic domain models for the BESS calculator engine.

All energy quantities are kWh, all power kW, all prices DKK unless stated
otherwise. End-user facing strings (disclaimer, assumptions) are Danish.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from . import ENGINE_VERSION

# Hard requirement (SPEC §10): fixed disclaimer, returned in every result.
DISCLAIMER = (
    "Beregningen er vejledende og baseret på historiske priser og "
    "standardforudsætninger. Den udgør ikke finansiel, teknisk eller "
    "skattemæssig rådgivning. Faktiske besparelser afhænger af fremtidige "
    "elpriser, afgifter, tariffer, forbrugsmønster og batteriets faktiske "
    "ydelse og kan afvige væsentligt."
)

Orientation = Literal["S", "SE_SW", "E_W"]
ConsumptionProfile = Literal["base", "base_ev", "base_hp", "base_ev_hp"]
PriceArea = Literal["DK1", "DK2"]
Dso = Literal["n1", "radius", "cerius"]
TaxScenario = Literal["low_2026_27", "normalized_post_2027"]
StrategyName = Literal["self_consumption", "price_optimized"]


class BatterySpec(BaseModel):
    name: str
    capacity_kwh: float = Field(gt=0, description="Nominal capacity [kWh]")
    power_kw: float = Field(gt=0, description="Charge = discharge power limit [kW] (MVP)")
    roundtrip_efficiency: float = Field(
        gt=0, le=1, description="AC roundtrip efficiency 0-1, applied as sqrt() per direction"
    )
    depth_of_discharge: float = Field(gt=0, le=1, description="Usable fraction, e.g. 0.90")
    calendar_degradation_pct_yr: float = Field(
        default=1.5, ge=0, lt=100, description="Linear capacity loss per year [%]"
    )
    cycle_life: int = Field(
        default=6000, gt=0, description="Full equivalent cycles to 80% SoH (informative in MVP)"
    )
    lifetime_years: int = Field(default=15, ge=1, le=30, description="Economic horizon [years]")
    price_dkk_installed: float = Field(gt=0, description="Installed price incl. VAT [DKK]")


class PVSpec(BaseModel):
    kwp: float = Field(gt=0, description="Installed DC capacity [kWp]")
    orientation: Orientation = Field(description="Maps to bundled PVGIS profiles")
    tilt_deg: int = Field(default=35, ge=0, le=90)


class ConsumptionSpec(BaseModel):
    annual_kwh: float = Field(gt=0, description="Annual household consumption [kWh]")
    profile: ConsumptionProfile = "base"


class SiteSpec(BaseModel):
    price_area: PriceArea
    dso: Dso
    supplier_markup_dkk_kwh: float = Field(
        default=0.04, ge=0, description="Supplier spot add-on [DKK/kWh, ex VAT]"
    )
    contract: Literal["spot"] = "spot"  # fixed-price contracts out of scope in MVP


class ScenarioConfig(BaseModel):
    tax_scenario: TaxScenario = "low_2026_27"
    realism_factor: float = Field(
        default=0.90, gt=0, le=1,
        description="Scales strategy-B gains vs perfect-information upper bound",
    )
    discount_rate: float = Field(default=0.04, ge=0, lt=1)


class SimulationRequest(BaseModel):
    battery: BatterySpec
    pv: PVSpec | None = None
    consumption: ConsumptionSpec
    site: SiteSpec
    scenario: ScenarioConfig = ScenarioConfig()


class SavingsBreakdown(BaseModel):
    """Decomposed annual (or lifetime-aggregate) figures for one strategy."""

    savings_self_consumption_dkk: float
    savings_arbitrage_dkk: float
    savings_tariff_avoidance_dkk: float
    savings_total_dkk: float
    baseline_cost_dkk: float = Field(description="Grid cost without battery, same PV [DKK]")
    cost_with_battery_dkk: float


class StrategyEconomics(BaseModel):
    strategy: StrategyName
    label_da: str = Field(description="Danish display label for the strategy")
    year1: SavingsBreakdown = Field(description="Year-1 figures, headline (realism-scaled)")
    year1_upper: SavingsBreakdown = Field(description="Year-1 upper bound (unscaled)")
    lifetime: SavingsBreakdown = Field(description="Lifetime aggregate, headline")
    lifetime_upper: SavingsBreakdown = Field(description="Lifetime aggregate, upper bound")
    annual_savings_dkk_low: float = Field(description="Lifetime-average annual savings, headline")
    annual_savings_dkk_high: float = Field(description="Lifetime-average annual savings, upper bound")
    payback_years_low: float | None = Field(
        description="Shortest payback (from upper-bound savings); None if never within horizon"
    )
    payback_years_high: float | None = Field(
        description="Longest payback (from headline savings); None if never within horizon"
    )
    npv_dkk: float = Field(description="NPV over lifetime at discount rate, headline savings")
    npv_dkk_high: float = Field(description="NPV upper bound (unscaled savings)")


class SimulationResult(BaseModel):
    strategies: dict[StrategyName, StrategyEconomics]
    reference_year: int
    assumptions: list[str] = Field(description="Machine-generated, rendered in UI (Danish)")
    disclaimer: str = DISCLAIMER
    engine_version: str = ENGINE_VERSION
    input_echo: SimulationRequest = Field(description="Exact input, so results are reproducible")
