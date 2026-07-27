# OOP Energy Management System (MVP)

Python **web GUI** MVP for a time-step house energy simulation.

## Features

- Single-zone thermal house model.
- **Heating source library** with reusable source specs and factory construction.
- Manual EV charging input.
- Time-of-use tariffs for electricity and district heat.
- Browser GUI with:
  - input controls,
  - KPI overview,
  - inline line chart,
  - hourly result table.

## Heating source library

Heating source definitions live in `ems/heating_library.py` and include metadata + defaults.

Current catalog:
- `district_standard`
- `district_high_capacity`
- `electric_resistance`
- `electric_panel_low_power`

List them from CLI:

```bash
python3 main.py --list-heating-sources
```

## Run

```bash
python3 main.py
```

Then open `http://127.0.0.1:8000` (opened automatically unless `--no-browser`).

Optional:

```bash
python3 main.py --host 0.0.0.0 --port 8000 --no-browser
```

## Why this opens reliably

The GUI is browser-based (served over HTTP), so it works in headless/server environments where desktop Tk windows cannot open due to missing display.
