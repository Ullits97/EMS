from __future__ import annotations

import html
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ems.heating_library import create_heating_source, get_heating_source_spec, list_heating_sources
from ems.models import ElectricVehicle, EnergyCarrier, House, TariffBook, TimeOfUseTariff
from ems.simulation import EnergyManagementSimulator, HourInput


@dataclass
class InputState:
    hours: int = 48
    ev_charge_kwh: float = 7.0
    ev_charge_hour: int = 22
    heating_source: str = "district_standard"


def default_tariff_book() -> TariffBook:
    electricity_tou = TimeOfUseTariff(
        hourly_prices=[
            0.12,
            0.12,
            0.11,
            0.11,
            0.11,
            0.13,
            0.17,
            0.20,
            0.22,
            0.23,
            0.21,
            0.19,
            0.18,
            0.18,
            0.19,
            0.23,
            0.27,
            0.31,
            0.29,
            0.24,
            0.20,
            0.17,
            0.15,
            0.13,
        ]
    )
    district_heat_tou = TimeOfUseTariff(hourly_prices=[0.09] * 24)
    return TariffBook(
        tariffs={
            EnergyCarrier.ELECTRICITY: electricity_tou,
            EnergyCarrier.DISTRICT_HEAT: district_heat_tou,
        }
    )


def build_hourly_inputs(hours: int, manual_ev_charge_kwh: float, charge_start_hour: int) -> list[HourInput]:
    inputs: list[HourInput] = []
    for h in range(hours):
        hod = h % 24
        outdoor = 1.0 if 8 <= hod <= 18 else -4.0
        ev_request = manual_ev_charge_kwh if hod == charge_start_hour else 0.0
        setpoint = 21.0 if 6 <= hod <= 22 else 19.0
        inputs.append(
            HourInput(
                outdoor_temperature_c=outdoor,
                ev_charge_request_kwh=ev_request,
                temperature_setpoint_c=setpoint,
            )
        )
    return inputs


def _normalize_heating_source(raw_key: str) -> str:
    try:
        get_heating_source_spec(raw_key)
        return raw_key
    except ValueError:
        return "district_standard"


def _simulate(state: InputState):
    house = House(140.0, 0.18, 18.0, 20.0, 21.0)
    heating_source = create_heating_source(state.heating_source)
    ev = ElectricVehicle(70.0, 20.0, 11.0)
    sim = EnergyManagementSimulator(house, heating_source, ev, default_tariff_book())
    report = sim.run(build_hourly_inputs(state.hours, state.ev_charge_kwh, state.ev_charge_hour))
    return report, ev, heating_source


def _svg_polyline(values: list[float], color: str, width: int = 820, height: int = 220) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) if hi != lo else 1.0
    points: list[str] = []
    for i, val in enumerate(values):
        x = int((i / max(len(values) - 1, 1)) * width)
        y = int(height - ((val - lo) / rng) * height)
        points.append(f"{x},{y}")
    return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2" />'


def _render_page(state: InputState) -> str:
    report, ev, source = _simulate(state)
    indoor = [s.indoor_temperature_c for s in report.steps]
    elec = [s.electricity_import_kwh for s in report.steps]
    dist = [s.district_heat_import_kwh for s in report.steps]

    option_html = "".join(
        (
            f"<option value='{spec.key}' {'selected' if state.heating_source == spec.key else ''}>"
            f"{html.escape(spec.display_name)}</option>"
        )
        for spec in list_heating_sources()
    )

    rows = "".join(
        f"<tr><td>{s.hour_index}</td><td>{s.indoor_temperature_c:.2f}</td><td>{s.electricity_import_kwh:.2f}</td>"
        f"<td>{s.district_heat_import_kwh:.2f}</td><td>{s.step_cost:.2f}</td></tr>"
        for s in report.steps[:72]
    )

    return f"""
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>EMS Web GUI</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    .controls {{ display:flex; gap:10px; flex-wrap:wrap; align-items:end; }}
    .card {{ border:1px solid #ddd; padding:12px; border-radius:8px; margin-top:12px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border:1px solid #ddd; padding: 6px; text-align:center; }}
    th {{ background:#f8f8f8; }}
  </style>
</head>
<body>
  <h1>Energy Management System</h1>
  <form method='get' class='controls'>
    <label>Hours<br><input name='hours' type='number' min='1' value='{state.hours}'></label>
    <label>EV charge kWh<br><input name='ev_charge_kwh' type='number' step='0.1' min='0' value='{state.ev_charge_kwh}'></label>
    <label>EV charge hour<br><input name='ev_charge_hour' type='number' min='0' max='23' value='{state.ev_charge_hour}'></label>
    <label>Heating source<br>
      <select name='heating_source'>
        {option_html}
      </select>
    </label>
    <button type='submit'>Run simulation</button>
  </form>

  <div class='card'>
    <b>Source:</b> {html.escape(source.name)} |
    <b>Electricity:</b> {report.total_electricity_import_kwh:.2f} kWh |
    <b>District heat:</b> {report.total_district_heat_import_kwh:.2f} kWh |
    <b>Total cost:</b> {report.total_cost:.2f} |
    <b>EV SoC end:</b> {ev.soc_percent:.1f}%
  </div>

  <div class='card'>
    <svg width='820' height='220' viewBox='0 0 820 220' style='background:#fff;border:1px solid #ddd'>
      {_svg_polyline(indoor, '#007acc')}
      {_svg_polyline(elec, '#e67e22')}
      {_svg_polyline(dist, '#27ae60')}
    </svg>
    <div>Blue: Indoor °C, Orange: Electricity kWh, Green: District heat kWh</div>
  </div>

  <div class='card'>
    <table>
      <thead><tr><th>Hour</th><th>Indoor °C</th><th>Electricity kWh</th><th>District heat kWh</th><th>Step cost</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</body>
</html>
"""


def run_web_gui(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = parse_qs(urlparse(self.path).query)
            state = InputState(
                hours=max(1, int(query.get("hours", [48])[0])),
                ev_charge_kwh=max(0.0, float(query.get("ev_charge_kwh", [7.0])[0])),
                ev_charge_hour=int(query.get("ev_charge_hour", [22])[0]) % 24,
                heating_source=_normalize_heating_source(query.get("heating_source", ["district_standard"])[0]),
            )
            content = _render_page(state).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"EMS Web GUI running at http://{host}:{port}")
    server.serve_forever()
