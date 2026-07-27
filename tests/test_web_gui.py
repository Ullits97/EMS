from ems.web_gui import InputState, _normalize_heating_source, _render_page


def test_render_page_contains_summary_and_table() -> None:
    html = _render_page(InputState(hours=24, ev_charge_kwh=5.0, ev_charge_hour=21, heating_source="district_standard"))
    assert "Energy Management System" in html
    assert "Total cost" in html
    assert "<table>" in html


def test_render_page_contains_heating_source_options() -> None:
    html = _render_page(InputState())
    assert "district_high_capacity" in html
    assert "electric_panel_low_power" in html


def test_unknown_heating_source_falls_back() -> None:
    assert _normalize_heating_source("not-a-source") == "district_standard"
