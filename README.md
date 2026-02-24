# OOP Energy Management System (MVP)

Python command-line MVP for a **time-step based** house energy simulation.

## Implemented now

- Single-zone house model with simple heat-loss approximation (extensible later).
- Switchable heating source via OOP composition:
  - district heating
  - electric resistance heater
- EV with manual charging requests.
- Time-of-use tariffs with separate carrier pricing (`electricity`, `district_heat`).
- Console mini-figures (sparklines) and temporary CSV report overwritten every run.

## Why this architecture

Chosen patterns:

- **Composition + explicit domain entities** (`House`, `HeatingSource`, `ElectricVehicle`, `TariffBook`) to keep responsibilities isolated.
- **Protocol-based polymorphism** for heating (`HeatingSource`) so source switching is runtime-configurable and new sources can be added without simulator rewrites.
- **Use-case orchestrator** (`EnergyManagementSimulator`) as application layer that coordinates entities but does not contain device-specific physics.

Why this is a good MVP trade-off:

- Keeps model simple today (single zone, manual charging, no optimizer).
- Avoids premature optimization logic while exposing stable extension points for smart charging, MPC/LP optimizers, PV/battery, and multi-zone thermal models.

## Run

```bash
python3 main.py
```

Switch heating source:

```bash
python3 main.py --heating-source electric
```

Custom run:

```bash
python3 main.py --hours 72 --ev-charge-kwh 10 --ev-charge-hour 1 --heating-source district
```

## Output

- In-app summary and sparklines.
- Temporary CSV report in system temp dir (typically `/tmp/ems_report_latest.csv`).
