from __future__ import annotations

from dataclasses import dataclass

from ems.models import DistrictHeatingSource, ElectricResistanceHeater, HeatingSource


@dataclass(frozen=True)
class HeatingSourceSpec:
    key: str
    display_name: str
    source_type: str
    max_heat_output_kw: float
    efficiency: float
    description: str


HEATING_SOURCE_LIBRARY: dict[str, HeatingSourceSpec] = {
    "district_standard": HeatingSourceSpec(
        key="district_standard",
        display_name="District heating (standard)",
        source_type="district",
        max_heat_output_kw=12.0,
        efficiency=0.95,
        description="Typical district heating connection for a detached house.",
    ),
    "district_high_capacity": HeatingSourceSpec(
        key="district_high_capacity",
        display_name="District heating (high capacity)",
        source_type="district",
        max_heat_output_kw=20.0,
        efficiency=0.95,
        description="Higher-capacity district heating for large loads.",
    ),
    "electric_resistance": HeatingSourceSpec(
        key="electric_resistance",
        display_name="Electric resistance heater",
        source_type="electric",
        max_heat_output_kw=9.0,
        efficiency=1.0,
        description="Direct electric heating (COP=1).",
    ),
    "electric_panel_low_power": HeatingSourceSpec(
        key="electric_panel_low_power",
        display_name="Electric panel heater (low power)",
        source_type="electric",
        max_heat_output_kw=6.0,
        efficiency=1.0,
        description="Lower-power electric panel heating setup.",
    ),
}


def list_heating_sources() -> list[HeatingSourceSpec]:
    return [HEATING_SOURCE_LIBRARY[k] for k in sorted(HEATING_SOURCE_LIBRARY)]


def get_heating_source_spec(key: str) -> HeatingSourceSpec:
    spec = HEATING_SOURCE_LIBRARY.get(key)
    if spec is None:
        available = ", ".join(sorted(HEATING_SOURCE_LIBRARY))
        raise ValueError(f"Unknown heating source '{key}'. Available: {available}")
    return spec


def create_heating_source(key: str) -> HeatingSource:
    spec = get_heating_source_spec(key)
    if spec.source_type == "district":
        return DistrictHeatingSource(
            name=spec.display_name,
            max_heat_output_kw=spec.max_heat_output_kw,
            network_efficiency=spec.efficiency,
        )
    if spec.source_type == "electric":
        return ElectricResistanceHeater(
            name=spec.display_name,
            max_heat_output_kw=spec.max_heat_output_kw,
            cop=spec.efficiency,
        )
    raise ValueError(f"Unsupported source type: {spec.source_type}")
