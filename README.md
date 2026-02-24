# OOP Energy Management System (MVP)

Python GUI MVP for a **time-step based** house energy simulation.

## Implemented now

- Single-zone house model with simple heat-loss approximation (extensible later).
- Switchable heating source:
  - district heating
  - electric resistance heater
- EV with manual charging requests.
- Time-of-use tariffs with separate carrier pricing (`electricity`, `district_heat`).
- Desktop GUI to run simulations and inspect results (summary, chart, hourly table).

## Why this architecture

Chosen patterns:

- **Composition + explicit domain entities** (`House`, `HeatingSource`, `ElectricVehicle`, `TariffBook`) to keep responsibilities isolated.
- **Protocol-based polymorphism** for heating (`HeatingSource`) so source switching is runtime-configurable and new sources can be added without simulator rewrites.
- **Use-case orchestrator** (`EnergyManagementSimulator`) as application layer that coordinates entities but does not contain device-specific physics.

This keeps the MVP simple now while exposing stable extension points for smart charging, optimization, PV/battery, and multi-zone thermal models.

## Run

```bash
python3 main.py
```

In the GUI:

- choose hours, EV manual charging amount and hour
- choose heating source (district/electric)
- click **Run simulation** to refresh overview

## Notes

The previous temp-file CSV report path has been replaced by an interactive GUI overview, per request.
