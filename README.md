# OOP Energy Management System (MVP)

Python **web GUI** MVP for a time-step house energy simulation.

## Features

- Single-zone thermal house model.
- Switchable heating source (`district` / `electric`).
- Manual EV charging input.
- Time-of-use tariffs for electricity and district heat.
- Browser GUI with:
  - input controls,
  - KPI overview,
  - inline line chart,
  - hourly result table.

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

The GUI is now browser-based (served over HTTP), so it works in headless/server environments where desktop Tk windows cannot open due to missing display.
