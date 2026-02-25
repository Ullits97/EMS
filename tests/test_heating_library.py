from ems.heating_library import create_heating_source, get_heating_source_spec, list_heating_sources
from ems.models import EnergyCarrier


def test_library_has_multiple_sources() -> None:
    keys = [spec.key for spec in list_heating_sources()]
    assert "district_standard" in keys
    assert "electric_resistance" in keys


def test_create_source_from_spec() -> None:
    src = create_heating_source("district_high_capacity")
    assert src.input_carrier == EnergyCarrier.DISTRICT_HEAT


def test_unknown_source_raises() -> None:
    try:
        get_heating_source_spec("nope")
    except ValueError:
        return
    raise AssertionError("Expected ValueError for unknown source")
