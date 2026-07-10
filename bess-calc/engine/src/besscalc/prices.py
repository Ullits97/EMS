"""Total buy/sell price construction (SPEC §6.6).

buy_price[t]  = (spot[t] + dso_tariff[t] + energinet_flat + elafgift[year] + supplier_markup) * (1 + VAT)
sell_price[t] = spot[t] - feed_in_fees

For the savings decomposition the buy price is split into two components
(both incl. VAT):
  spot_component     = (spot + supplier_markup) * (1 + VAT)
  tariff_tax_component = (dso_tariff + energinet_flat + elafgift) * (1 + VAT)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import DataError, load_taxes, load_tariffs
from .models import SiteSpec, TaxScenario

WINTER_MONTHS = frozenset({10, 11, 12, 1, 2, 3})


def _parse_hours(spec: str) -> set[int]:
    """Parse "06-17,21-24" into the set of local hours covered (half-open ranges)."""
    hours: set[int] = set()
    for part in spec.split(","):
        start_s, end_s = part.strip().split("-")
        start, end = int(start_s), int(end_s)
        if not (0 <= start < end <= 24):
            raise DataError(f"Invalid hour range in tariffs.yaml: {part!r}")
        hours.update(range(start, end))
    return hours


def _band_rates_by_season(dso: str) -> dict[str, np.ndarray]:
    """Per-season array of 24 hourly rates (DKK/kWh ex VAT) for a DSO."""
    cfg = load_tariffs()
    try:
        bands = cfg["dsos"][dso]["bands"]
    except KeyError as exc:
        raise DataError(f"DSO {dso!r} not found in tariffs.yaml") from exc

    rates = {"winter": np.full(24, np.nan), "summer": np.full(24, np.nan)}
    for band in bands:
        arr = rates[band["season"]]
        for hour in _parse_hours(band["hours"]):
            if not np.isnan(arr[hour]):
                raise DataError(f"Overlapping tariff bands for {dso} {band['season']} hour {hour}")
        arr_hours = _parse_hours(band["hours"])
        arr[list(arr_hours)] = float(band["rate_dkk_kwh"])
    for season, arr in rates.items():
        if np.isnan(arr).any():
            missing = [h for h in range(24) if np.isnan(arr[h])]
            raise DataError(f"Tariff bands for {dso}/{season} leave hours uncovered: {missing}")
    return rates


def dso_tariff_series(index: pd.DatetimeIndex, dso: str) -> np.ndarray:
    """DSO time-of-use tariff (DKK/kWh ex VAT) resolved per 15-min timestamp.

    Uses local (Europe/Copenhagen) hour and month, so DST transitions and
    season boundaries resolve naturally.
    """
    rates = _band_rates_by_season(dso)
    hours = index.hour.to_numpy()
    winter = np.isin(index.month.to_numpy(), list(WINTER_MONTHS))
    return np.where(winter, rates["winter"][hours], rates["summer"][hours])


def energinet_flat() -> float:
    cfg = load_tariffs()["energinet"]
    return float(cfg["system_tariff_dkk_kwh"]) + float(cfg["transmission_tariff_dkk_kwh"])


def elafgift_for_year(scenario: TaxScenario, year: int) -> float:
    timeline = load_taxes()["elafgift_dkk_kwh"][scenario]
    return float(timeline.get(year, timeline["default"]))


def feed_in_fees() -> float:
    return float(load_taxes()["feed_in_fees_dkk_kwh"])


def vat_factor() -> float:
    return 1.0 + float(load_taxes()["vat_rate"])


@dataclass(frozen=True)
class PriceSet:
    """All per-step price arrays needed for one simulation year."""

    buy: np.ndarray  # DKK/kWh incl. VAT
    sell: np.ndarray  # DKK/kWh (no VAT/elafgift on prosumer sales)
    spot_component: np.ndarray  # (spot + markup) * VAT — the "energy" share of buy
    tariff_tax_component: np.ndarray  # (dso + energinet + elafgift) * VAT


def build_prices(
    spot: pd.Series,
    site: SiteSpec,
    tax_scenario: TaxScenario,
    year: int,
) -> PriceSet:
    """Construct the SPEC §6.6 price arrays for one simulation year."""
    index = spot.index
    spot_arr = spot.to_numpy(dtype=float)
    vat = vat_factor()

    dso = dso_tariff_series(index, site.dso)
    grid_flat = energinet_flat() + elafgift_for_year(tax_scenario, year)

    spot_component = (spot_arr + site.supplier_markup_dkk_kwh) * vat
    tariff_tax_component = (dso + grid_flat) * vat
    buy = spot_component + tariff_tax_component
    sell = spot_arr - feed_in_fees()
    return PriceSet(
        buy=buy,
        sell=sell,
        spot_component=spot_component,
        tariff_tax_component=tariff_tax_component,
    )
