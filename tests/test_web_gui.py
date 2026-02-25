from ems.web_gui import InputState, _render_page


def test_render_page_contains_summary_and_table() -> None:
    html = _render_page(InputState(hours=24, ev_charge_kwh=5.0, ev_charge_hour=21, heating_source="district"))
    assert "Energy Management System" in html
    assert "Total cost" in html
    assert "<table>" in html
