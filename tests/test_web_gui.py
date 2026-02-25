from ems.web_gui import InputState, _normalize_heating_source, _render_page, _simulate


def test_render_page_contains_summary_and_table() -> None:
    html = _render_page(
        InputState(
            hours=24,
            ev_charge_kwh=5.0,
            ev_charge_hour=21,
            heating_source="district_standard",
            target_temperature_c=21.0,
            heat_loss_factor=0.18,
        )
    )
    assert "Energy Management System" in html
    assert "Total cost" in html
    assert "<table>" in html


def test_render_page_contains_heating_source_options() -> None:
    html = _render_page(InputState())
    assert "district_high_capacity" in html
    assert "electric_panel_low_power" in html


def test_render_page_contains_house_controls() -> None:
    html = _render_page(InputState())
    assert "target_temperature_c" in html
    assert "heat_loss_factor" in html


def test_unknown_heating_source_falls_back() -> None:
    assert _normalize_heating_source("not-a-source") == "district_standard"


def test_higher_heat_loss_factor_increases_energy_import() -> None:
    low_report, _, _ = _simulate(InputState(hours=24, heat_loss_factor=0.12, target_temperature_c=21.0))
    high_report, _, _ = _simulate(InputState(hours=24, heat_loss_factor=0.30, target_temperature_c=21.0))
    assert high_report.total_district_heat_import_kwh > low_report.total_district_heat_import_kwh


def test_higher_target_temperature_increases_energy_import() -> None:
    low_report, _, _ = _simulate(InputState(hours=24, heat_loss_factor=0.18, target_temperature_c=19.0))
    high_report, _, _ = _simulate(InputState(hours=24, heat_loss_factor=0.18, target_temperature_c=23.0))
    assert high_report.total_district_heat_import_kwh > low_report.total_district_heat_import_kwh
