from __future__ import annotations

import tempfile
from pathlib import Path

from ems.models import SimulationReport


def _sparkline(values: list[float], min_width: int = 30) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if hi == lo:
        return blocks[0] * max(len(values), min_width)
    line = "".join(blocks[int((v - lo) / (hi - lo) * (len(blocks) - 1))] for v in values)
    return line.ljust(min_width)


def build_console_summary(report: SimulationReport) -> str:
    indoor = [s.indoor_temperature_c for s in report.steps]
    elec = [s.electricity_import_kwh for s in report.steps]
    heat = [s.district_heat_import_kwh for s in report.steps]

    lines = [
        "=== EMS Simulation Summary ===",
        f"Hours simulated         : {len(report.steps)}",
        f"Electricity import      : {report.total_electricity_import_kwh:.2f} kWh",
        f"District heat import    : {report.total_district_heat_import_kwh:.2f} kWh",
        f"Total cost              : {report.total_cost:.2f}",
        "",
        "Indoor temperature (sparkline):",
        _sparkline(indoor),
        "Electricity import/hour (sparkline):",
        _sparkline(elec),
        "District heat import/hour (sparkline):",
        _sparkline(heat),
    ]
    return "\n".join(lines)


def write_temp_report(report: SimulationReport) -> Path:
    path = Path(tempfile.gettempdir()) / "ems_report_latest.csv"
    with path.open("w", encoding="utf-8") as f:
        f.write(
            "hour,outdoor_temp_c,indoor_temp_c,target_temp_c,heat_requested_kwh,heat_delivered_kwh,"
            "heating_input_carrier,heating_input_energy_kwh,ev_requested_kwh,ev_delivered_kwh,"
            "electricity_import_kwh,district_heat_import_kwh,step_cost\n"
        )
        for s in report.steps:
            f.write(
                f"{s.hour_index},{s.outdoor_temperature_c:.2f},{s.indoor_temperature_c:.2f},{s.target_temperature_c:.2f},"
                f"{s.heating_requested_kwh:.2f},{s.heating_delivered_kwh:.2f},{s.heating_input_carrier.value},"
                f"{s.heating_input_energy_kwh:.2f},{s.ev_requested_kwh:.2f},{s.ev_delivered_kwh:.2f},"
                f"{s.electricity_import_kwh:.2f},{s.district_heat_import_kwh:.2f},{s.step_cost:.4f}\n"
            )
    return path
