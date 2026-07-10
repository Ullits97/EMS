"""Data loader behavior, incl. the clear-error path when Parquets are missing."""

import pandas as pd
import pytest

from besscalc import data


def test_missing_reference_data_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("BESSCALC_DATA_DIR", str(tmp_path))
    with pytest.raises(data.DataError, match="fetch_spot.py"):
        data.load_spot("DK1")


def test_reference_datasets_are_aligned():
    idx = data.load_spot("DK1").index
    assert len(idx) == len(data.load_spot("DK2"))
    assert len(idx) == len(data.load_pv_profile("S"))
    assert len(idx) == len(data.load_consumption_profile("base"))
    assert str(idx.tz) == "Europe/Copenhagen"
    # Uniform 15-min grid over one full year.
    assert len(idx) in (35040, 35136)  # non-leap / leap
    assert (idx[1:] - idx[:-1]).unique().tolist() == [pd.Timedelta(minutes=15)]


def test_consumption_profiles_normalized():
    for profile in ("base", "base_ev", "base_hp", "base_ev_hp"):
        series = data.load_consumption_profile(profile)
        assert series.sum() == pytest.approx(1.0, abs=1e-9)
        assert (series >= 0).all()


def test_pv_profiles_realistic_annual_yield():
    for orientation, low, high in (("S", 800, 1300), ("SE_SW", 750, 1250), ("E_W", 650, 1150)):
        series = data.load_pv_profile(orientation)
        assert low <= series.sum() <= high, orientation
