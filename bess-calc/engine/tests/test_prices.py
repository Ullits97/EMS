"""Price construction pinned with hand-computed fixtures (SPEC §6.6/§11)."""

import numpy as np
import pandas as pd
import pytest

from besscalc.data import load_tariffs, load_taxes
from besscalc.models import SiteSpec
from besscalc.prices import (
    build_prices,
    dso_tariff_series,
    elafgift_for_year,
    energinet_flat,
    feed_in_fees,
    vat_factor,
)


def _index(*stamps: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([pd.Timestamp(s, tz="Europe/Copenhagen") for s in stamps])


def test_buy_price_formula_pinned():
    """buy = (spot + dso + energinet + elafgift + markup) * 1.25, by hand."""
    # 2026-01-15 18:00 local = winter peak band.
    idx = _index("2026-01-15 18:00")
    spot = pd.Series([0.50], index=idx)
    site = SiteSpec(price_area="DK1", dso="radius", supplier_markup_dkk_kwh=0.04)

    tariffs = load_tariffs()
    peak_rate = next(
        b["rate_dkk_kwh"]
        for b in tariffs["dsos"]["radius"]["bands"]
        if b["season"] == "winter" and b["name"] == "peak"
    )
    energinet = (
        tariffs["energinet"]["system_tariff_dkk_kwh"]
        + tariffs["energinet"]["transmission_tariff_dkk_kwh"]
    )
    elafgift = load_taxes()["elafgift_dkk_kwh"]["low_2026_27"][2026]
    expected = (0.50 + peak_rate + energinet + elafgift + 0.04) * 1.25

    prices = build_prices(spot, site, "low_2026_27", 2026)
    assert prices.buy[0] == pytest.approx(expected)
    # Components must sum to the total buy price.
    assert prices.spot_component[0] + prices.tariff_tax_component[0] == pytest.approx(expected)


def test_sell_price_formula_pinned():
    idx = _index("2026-06-15 12:00")
    spot = pd.Series([0.30], index=idx)
    site = SiteSpec(price_area="DK1", dso="n1")
    prices = build_prices(spot, site, "low_2026_27", 2026)
    assert prices.sell[0] == pytest.approx(0.30 - feed_in_fees())
    # No VAT and no elafgift on the sell side.
    assert prices.sell[0] < 0.30


def test_elafgift_year_indexed_timeline():
    low_2026 = elafgift_for_year("low_2026_27", 2026)
    low_2027 = elafgift_for_year("low_2026_27", 2027)
    low_2028 = elafgift_for_year("low_2026_27", 2028)
    normal = elafgift_for_year("normalized_post_2027", 2026)
    assert low_2026 == low_2027
    assert low_2028 > low_2026  # normalization kicks in mid-horizon
    assert low_2028 == normal


def test_vat_applied_to_full_buy_side():
    assert vat_factor() == pytest.approx(1.25)


def test_tariff_band_resolution_seasons_and_hours():
    idx = _index(
        "2026-01-10 03:00",  # winter low
        "2026-01-10 10:00",  # winter high
        "2026-01-10 17:00",  # winter peak (inclusive start)
        "2026-01-10 20:45",  # winter peak (last slot)
        "2026-01-10 21:00",  # winter high again
        "2026-07-10 18:00",  # summer peak
        "2026-03-31 18:00",  # last winter day
        "2026-04-01 18:00",  # first summer day
    )
    rates = dso_tariff_series(idx, "radius")
    bands = {
        (b["season"], b["name"]): b["rate_dkk_kwh"]
        for b in load_tariffs()["dsos"]["radius"]["bands"]
    }
    assert rates[0] == bands[("winter", "low")]
    assert rates[1] == bands[("winter", "high")]
    assert rates[2] == bands[("winter", "peak")]
    assert rates[3] == bands[("winter", "peak")]
    assert rates[4] == bands[("winter", "high")]
    assert rates[5] == bands[("summer", "peak")]
    assert rates[6] == bands[("winter", "peak")]
    assert rates[7] == bands[("summer", "peak")]


def test_tariff_resolution_across_dst_transitions():
    """Local-hour resolution must hold through both DST transitions."""
    # Spring forward 2026-03-29: 02:00 -> 03:00 (02:xx does not exist).
    spring = pd.date_range(
        "2026-03-29 00:00", "2026-03-29 06:00", freq="15min", tz="Europe/Copenhagen"
    )
    rates = dso_tariff_series(spring, "radius")
    bands = {
        (b["season"], b["name"]): b["rate_dkk_kwh"]
        for b in load_tariffs()["dsos"]["radius"]["bands"]
    }
    # All slots before 06 local are in the low band regardless of the skipped hour.
    before_six = spring.hour < 6
    assert np.all(rates[before_six] == bands[("winter", "low")])
    assert np.all(rates[~before_six] == bands[("winter", "high")])

    # Fall back 2026-10-25: 03:00 occurs twice; both occurrences resolve to low.
    fall = pd.date_range(
        "2026-10-25 00:00", "2026-10-25 06:00", freq="15min", tz="Europe/Copenhagen"
    )
    assert len(fall) > 25  # the repeated hour makes the range longer than 6h
    rates_fall = dso_tariff_series(fall, "radius")
    assert np.all(rates_fall[fall.hour < 6] == bands[("winter", "low")])


def test_all_dsos_cover_all_hours():
    idx = pd.date_range("2026-01-01", periods=96, freq="15min", tz="Europe/Copenhagen")
    for dso in ("n1", "radius", "cerius"):
        rates = dso_tariff_series(idx, dso)
        assert np.all(rates > 0)


def test_energinet_flat_positive():
    assert energinet_flat() > 0
