from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ems.models import (
    DistrictHeatingSource,
    ElectricResistanceHeater,
    ElectricVehicle,
    EnergyCarrier,
    House,
    TariffBook,
    TimeOfUseTariff,
)
from ems.simulation import EnergyManagementSimulator, HourInput


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
    result: list[HourInput] = []
    for h in range(hours):
        hod = h % 24
        outdoor = 1.0 if 8 <= hod <= 18 else -4.0
        ev_request = manual_ev_charge_kwh if hod == charge_start_hour else 0.0
        setpoint = 21.0 if 6 <= hod <= 22 else 19.0
        result.append(
            HourInput(
                outdoor_temperature_c=outdoor,
                ev_charge_request_kwh=ev_request,
                temperature_setpoint_c=setpoint,
            )
        )
    return result


class ResultPlot(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, width=900, height=300, bg="white", highlightthickness=1)
        self.canvas.pack(fill="both", expand=True)

    def _polyline(self, values: list[float], color: str, x0: int, y0: int, w: int, h: int) -> None:
        if not values:
            return
        lo, hi = min(values), max(values)
        rng = (hi - lo) if hi != lo else 1.0
        points: list[float] = []
        for i, value in enumerate(values):
            x = x0 + (i / max(len(values) - 1, 1)) * w
            y = y0 + h - ((value - lo) / rng) * h
            points.extend([x, y])
        if len(points) >= 4:
            self.canvas.create_line(*points, fill=color, width=2, smooth=True)

    def draw(self, indoor_t: list[float], elec: list[float], district: list[float]) -> None:
        self.canvas.delete("all")
        pad = 20
        chart_w = 860
        chart_h = 220
        self.canvas.create_rectangle(pad, pad, pad + chart_w, pad + chart_h, outline="#cccccc")
        self._polyline(indoor_t, "#007acc", pad, pad, chart_w, chart_h)
        self._polyline(elec, "#e67e22", pad, pad, chart_w, chart_h)
        self._polyline(district, "#27ae60", pad, pad, chart_w, chart_h)
        self.canvas.create_text(30, 265, text="Blue: Indoor °C", anchor="w", fill="#007acc")
        self.canvas.create_text(180, 265, text="Orange: Electricity kWh", anchor="w", fill="#e67e22")
        self.canvas.create_text(410, 265, text="Green: District heat kWh", anchor="w", fill="#27ae60")


class EMSApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.pack(fill="both", expand=True)

        master.title("Energy Management System")
        master.geometry("960x700")

        controls = ttk.LabelFrame(self, text="Simulation Settings", padding=10)
        controls.pack(fill="x", padx=4, pady=4)

        self.hours_var = tk.IntVar(value=48)
        self.ev_kwh_var = tk.DoubleVar(value=7.0)
        self.ev_hour_var = tk.IntVar(value=22)
        self.source_var = tk.StringVar(value="district")

        ttk.Label(controls, text="Hours").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.hours_var, width=8).grid(row=0, column=1, padx=4)
        ttk.Label(controls, text="EV charge request (kWh)").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.ev_kwh_var, width=8).grid(row=0, column=3, padx=4)
        ttk.Label(controls, text="EV charge hour").grid(row=0, column=4, sticky="w")
        ttk.Entry(controls, textvariable=self.ev_hour_var, width=8).grid(row=0, column=5, padx=4)
        ttk.Label(controls, text="Heating source").grid(row=0, column=6, sticky="w")
        ttk.Combobox(controls, textvariable=self.source_var, values=["district", "electric"], width=10, state="readonly").grid(row=0, column=7, padx=4)
        ttk.Button(controls, text="Run simulation", command=self.run_simulation).grid(row=0, column=8, padx=8)

        self.summary_label = ttk.Label(self, text="Run a simulation to see results.", justify="left")
        self.summary_label.pack(fill="x", padx=4, pady=8)

        self.plot = ResultPlot(self)
        self.plot.pack(fill="both", expand=True, padx=4, pady=6)

        cols = ("hour", "temp", "elec", "district", "cost")
        self.table = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for col, title in [
            ("hour", "Hour"),
            ("temp", "Indoor °C"),
            ("elec", "Electricity kWh"),
            ("district", "District heat kWh"),
            ("cost", "Step cost"),
        ]:
            self.table.heading(col, text=title)
            self.table.column(col, width=120, anchor="center")
        self.table.pack(fill="x", padx=4, pady=4)

    def run_simulation(self) -> None:
        hours = max(1, int(self.hours_var.get()))
        ev_kwh = max(0.0, float(self.ev_kwh_var.get()))
        ev_hour = int(self.ev_hour_var.get()) % 24
        source = self.source_var.get()

        house = House(
            floor_area_m2=140.0,
            ua_kw_per_k=0.18,
            thermal_mass_kwh_per_k=18.0,
            indoor_temperature_c=20.0,
            target_temperature_c=21.0,
        )
        heating_source = DistrictHeatingSource(max_heat_output_kw=12.0) if source == "district" else ElectricResistanceHeater(max_heat_output_kw=9.0, cop=1.0)
        ev = ElectricVehicle(battery_capacity_kwh=70.0, soc_kwh=20.0, max_charging_power_kw=11.0)

        simulator = EnergyManagementSimulator(house, heating_source, ev, default_tariff_book())
        report = simulator.run(build_hourly_inputs(hours, ev_kwh, ev_hour))

        self.summary_label.configure(
            text=(
                f"Heating source: {heating_source.name} | Hours: {hours} | "
                f"Electricity: {report.total_electricity_import_kwh:.2f} kWh | "
                f"District heat: {report.total_district_heat_import_kwh:.2f} kWh | "
                f"Total cost: {report.total_cost:.2f} | "
                f"EV SoC end: {ev.soc_percent:.1f}%"
            )
        )

        indoor = [s.indoor_temperature_c for s in report.steps]
        elec = [s.electricity_import_kwh for s in report.steps]
        district = [s.district_heat_import_kwh for s in report.steps]
        self.plot.draw(indoor, elec, district)

        for row in self.table.get_children():
            self.table.delete(row)
        for s in report.steps[:48]:
            self.table.insert(
                "",
                "end",
                values=(
                    s.hour_index,
                    f"{s.indoor_temperature_c:.2f}",
                    f"{s.electricity_import_kwh:.2f}",
                    f"{s.district_heat_import_kwh:.2f}",
                    f"{s.step_cost:.2f}",
                ),
            )


def run_gui() -> None:
    root = tk.Tk()
    EMSApp(root)
    root.mainloop()
