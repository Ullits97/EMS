# SPEC.md — BESS Calculator (White-Label) — Full-Stack MVP

Spec-driven design document for implementation with Claude Code.
Language: code, comments, and identifiers in **English**; end-user UI text in Danish.
Status: v1.0 — implements Phase 1 of product spec v0.1 + widget demo.

---

## 1. Product summary

A simulation-based home battery (BESS) economics calculator for the Danish market, delivered as:

1. A **Python simulation engine** (deterministic, offline, test-covered).
2. A **FastAPI backend** exposing the engine.
3. An **embeddable React widget** (single JS bundle) that an installer can place on their website via a `<script>` tag — demo-ready.

The engine simulates a full reference year at 15-minute resolution: household consumption + optional PV + battery dispatch against real historical spot prices, Danish grid tariffs, and electricity taxes. Output is a decomposed annual saving, payback **interval**, and NPV over battery lifetime.

**This is a decision-support tool, not financial advice. Disclaimer handling is a hard requirement (see §10).**

## 2. Locked decisions

| Decision | Choice |
|---|---|
| Scope | Full stack incl. widget demo |
| Dispatch | Rule-based only (no LP in MVP) |
| Price data | Static bundled reference year (offline runtime; one-off ingestion scripts) |
| Grid tariffs | 3 hardcoded DSOs in config: **N1, Radius, Cerius** (covers majority of households) |
| Codebase | Fresh repo. Port *patterns* from prior HEMS project (component classes, dispatcher interface, energy-balance validation tests) — not code verbatim |
| Multi-tenant | Config-file based (one YAML per tenant); no auth/admin UI in MVP |
| Reserve markets (FCR/mFRR) | **Out of scope** (Phase 2) |
| Eloverblik import | **Out of scope** (Phase 2) |
| PDF report | **Out of scope** (Phase 2); widget shows on-screen results only |

## 3. Tech stack

- Python 3.11+, `pandas`, `numpy`, `pydantic` v2, `pyyaml`
- FastAPI + uvicorn; `pytest` + `pytest-cov`
- Frontend: React 18 + Vite, TypeScript, built as a single embeddable IIFE bundle (`widget.js`); charts with `recharts`
- No database in MVP (all config/data on disk: YAML + Parquet)
- Lint/format: `ruff`, `prettier`

## 4. Repository layout

```
bess-calc/
├── SPEC.md                      # this file
├── engine/
│   ├── pyproject.toml
│   ├── src/besscalc/
│   │   ├── models.py            # pydantic domain models
│   │   ├── data.py              # loaders for reference-year datasets
│   │   ├── prices.py            # total buy/sell price construction
│   │   ├── components/
│   │   │   ├── battery.py       # Battery class (SoC, power, efficiency, DoD)
│   │   │   ├── pv.py            # PV production from bundled profiles
│   │   │   └── consumption.py   # profile scaling / synthesis
│   │   ├── dispatch/
│   │   │   ├── base.py          # Strategy interface
│   │   │   ├── self_consumption.py   # Strategy A
│   │   │   └── price_optimized.py    # Strategy B
│   │   ├── simulate.py          # main loop, energy balance, yearly degradation
│   │   ├── economics.py         # savings decomposition, payback, NPV
│   │   └── config/
│   │       ├── tariffs.yaml     # N1, Radius, Cerius schedules
│   │       ├── taxes.yaml       # elafgift timeline, VAT, sell-side fees
│   │       └── defaults.yaml    # realism factor, tolerances, discount rate
│   └── tests/
├── data/
│   ├── raw/                     # downloaded by ingestion scripts (gitignored)
│   └── reference/               # committed Parquet: spot_dk1.parquet, spot_dk2.parquet,
│                                #   pv_profiles.parquet, consumption_profiles.parquet
├── ingestion/
│   ├── fetch_spot.py            # Energi Data Service → reference year Parquet
│   ├── fetch_pv.py              # PVGIS hourly TMY → per-orientation profiles
│   └── build_consumption.py     # synthetic standard profiles (see §6.3)
├── api/
│   ├── main.py                  # FastAPI app
│   ├── tenants/
│   │   └── demo.yaml            # demo tenant: branding + product catalog
│   └── tests/
└── widget/
    ├── src/                     # React app
    └── embed/demo.html          # static page demonstrating script-tag embed
```

## 5. Domain models (`models.py`)

All pydantic, all SI-ish units documented in field descriptions.

```python
class BatterySpec:
    name: str
    capacity_kwh: float            # nominal
    power_kw: float                # charge = discharge limit (MVP)
    roundtrip_efficiency: float    # 0–1, applied as sqrt() on each direction
    depth_of_discharge: float      # usable fraction, e.g. 0.90
    calendar_degradation_pct_yr: float   # e.g. 1.5
    cycle_life: int                # full equivalent cycles to 80% SoH (informative in MVP)
    lifetime_years: int            # economic horizon, e.g. 15
    price_dkk_installed: float     # incl. VAT and installation

class PVSpec:
    kwp: float
    orientation: Literal["S", "SE_SW", "E_W"]   # maps to bundled PVGIS profiles
    tilt_deg: int = 35

class ConsumptionSpec:
    annual_kwh: float
    profile: Literal["base", "base_ev", "base_hp", "base_ev_hp"]

class SiteSpec:
    price_area: Literal["DK1", "DK2"]
    dso: Literal["n1", "radius", "cerius"]
    supplier_markup_dkk_kwh: float = 0.04   # ore/kWh spot add-on, configurable
    contract: Literal["spot"] = "spot"      # fixed-price out of scope in MVP

class ScenarioConfig:
    tax_scenario: Literal["low_2026_27", "normalized_post_2027"]
    realism_factor: float = 0.90            # scales strategy-B gains vs perfect info
    discount_rate: float = 0.04

class SimulationRequest:
    battery: BatterySpec
    pv: PVSpec | None
    consumption: ConsumptionSpec
    site: SiteSpec
    scenario: ScenarioConfig
```

**Result model** (`SimulationResult`): per-strategy annual figures for year 1 and lifetime aggregate:
`savings_self_consumption_dkk`, `savings_arbitrage_dkk`, `savings_tariff_avoidance_dkk`, `baseline_cost_dkk`, `cost_with_battery_dkk`, `payback_years_low/high`, `npv_dkk`, plus `assumptions: list[str]` (machine-generated, rendered in UI — see §10) and `engine_version: str`.

## 6. Data layer

### 6.1 Spot prices
- `ingestion/fetch_spot.py`: pull one full calendar year (parameterized, default = most recent complete year) of `Elspotprices` (or the 15-min successor dataset) from `https://api.energidataservice.dk` for DK1 and DK2. Resample/interpolate to a uniform **15-min index in Europe/Copenhagen**, save Parquet with columns `[timestamp, price_dkk_per_kwh]` (convert from DKK/MWh).
- Runtime **never** calls the network. If reference Parquet is missing, engine raises a clear error pointing to the ingestion script.

### 6.2 PV profiles
- `ingestion/fetch_pv.py`: PVGIS API (hourly TMY, location = central DK, e.g. 56.0N 10.0E) for the three orientation presets; normalize to **kWh per kWp per 15-min step** (upsample hourly → 15-min by division); save Parquet.
- Engine scales by `kwp`.

### 6.3 Consumption profiles
- Synthetic but realistic normalized profiles built in `build_consumption.py` (deterministic, seeded):
  - `base`: morning/evening peaks, weekday/weekend variation, seasonal lighting/appliance factor.
  - `base_ev`: adds ~3,500 kWh/yr night-weighted charging block (23–06).
  - `base_hp`: adds heating-season load correlated with a simple degree-day curve.
  - `base_ev_hp`: both.
- Each profile normalized to sum = 1 over the year; engine scales by `annual_kwh`.
- **TODO(product):** replace with empirical category profiles in Phase 2.

### 6.4 Tariffs (`tariffs.yaml`)
Schema per DSO: time-of-use bands with season, hours, and rate (DKK/kWh ex VAT):

```yaml
radius:
  bands:
    - {season: winter, name: low,  hours: "00-06", rate_dkk_kwh: 0.0000}  # TODO verify
    - {season: winter, name: high, hours: "06-17,21-24", rate_dkk_kwh: 0.0000}
    - {season: winter, name: peak, hours: "17-21", rate_dkk_kwh: 0.0000}
    - {season: summer, ...}
```

**All rates are placeholders marked `TODO verify` — populate from each DSO's published price sheet (or DatahubPricelist export) before results are shown to anyone.** Include Energinet system + transmission tariffs as flat adders in the same file.

### 6.5 Taxes (`taxes.yaml`)
- `elafgift` per scenario: `low_2026_27` and `normalized_post_2027` — values **TODO verify** against current law; structure must make a mid-simulation-horizon change possible (year-indexed values over the battery lifetime).
- VAT = 25% applied to the full buy-side sum.
- Sell side: spot minus configurable feed-in fees; **no** elafgift or VAT on revenue for private prosumers (flag `TODO verify` current rules); note in assumptions that sales above the tax-free threshold may be taxable (informational string only — engine does not compute income tax).

### 6.6 Price construction (`prices.py`)
```
buy_price[t]  = (spot[t] + dso_tariff[t] + energinet_flat + elafgift[year(t)] + supplier_markup) * 1.25
sell_price[t] = spot[t] - feed_in_fees
```
Unit tests must pin this formula with hand-computed fixtures.

## 7. Simulation engine

### 7.1 Core loop (`simulate.py`)
- Uniform 15-min timestep over the reference year.
- Per step: `pv_gen`, `load` → strategy decides battery charge/discharge within power, SoC ∈ [ (1−DoD)·cap_effective, cap_effective ], efficiency split as √η on each direction → residual grid import/export → cash flows via §6.6.
- **Energy balance invariant** (ported HEMS pattern): `pv + import + discharge == load + export + charge + losses` within `1e-6` kWh per step; violation raises. A dedicated test asserts the invariant over the full year for random configs (property-style test with ~20 seeded configs).

### 7.2 Strategies
- **A — self_consumption:** charge from PV surplus only; discharge to cover residual load. No grid charging. (Baseline mirrors most inverters' default.)
- **B — price_optimized (rule-based):** daily horizon, assumes day-ahead prices known (they are, in reality):
  1. Rank the day's 15-min slots by `buy_price`.
  2. Charge (from PV surplus first, then grid) during the cheapest slots up to available headroom; never charge during the top-priced quartile.
  3. Discharge to cover load during the most expensive slots (captures the 17–21 peak band) subject to SoC.
  4. Grid export from battery **disallowed** in MVP (only PV surplus exports) — keeps tax treatment simple; note as assumption.
- Strategy B gains relative to A are scaled by `realism_factor` (default 0.90) — report both the scaled value (headline) and unscaled (upper bound) to produce the **interval**.

### 7.3 Lifetime & degradation
- Simulate year 1 in full detail. For years 2..N: scale battery capacity by calendar degradation (linear, `calendar_degradation_pct_yr`), re-run the year loop with degraded capacity every year (runtime target §11 allows it), keep prices/taxes per `taxes.yaml` year index.
- Economics (`economics.py`): annual savings = baseline cost (no battery, same PV) − cost with battery. Decompose:
  - *self-consumption value*: reduced import valued at buy price minus lost export revenue,
  - *arbitrage*: strategy-B grid-charged energy value delta at spot component,
  - *tariff avoidance*: delta attributable to tariff + tax components of shifted energy.
  Decomposition must sum to total within 1 DKK/yr (tested).
- Payback interval: [lifetime-average savings with realism factor, without] → two payback numbers, reported low/high. NPV at `discount_rate` over `lifetime_years`.

## 8. API (`api/main.py`)

- `POST /api/v1/simulate` → body `SimulationRequest` + `tenant_id`; returns `SimulationResult` for strategies A and B. Validation errors → 422 with field messages.
- `GET /api/v1/tenants/{tenant_id}/catalog` → tenant branding (name, logo URL, colors) + `BatterySpec[]` product list from `tenants/{id}.yaml`.
- `GET /health`.
- CORS: allow-all in demo mode (flag in config).
- Runtime target: full lifetime simulation **< 2 s** on a laptop (vectorize with pandas/numpy; the daily strategy-B ranking can be vectorized per-day).

## 9. Widget (`widget/`)

- Build output: one `widget.js`; embed contract:
  ```html
  <div id="bess-calc" data-tenant="demo" data-api="https://..."></div>
  <script src=".../widget.js"></script>
  ```
- Flow (all UI text Danish):
  1. **Input step:** postnummer → maps to DSO + price area (bundled mapping JSON, coarse is fine for demo: TODO refine); årsforbrug (or husstandstype presets); solceller ja/nej (+kWp, orientering); batterivalg from tenant catalog or "anbefal størrelse" (runs a sweep over catalog, picks best NPV).
  2. **Result step:** headline = *besparelsesinterval* kr/år and *tilbagebetalingstid* as interval (e.g. "7–9 år"); stacked bar of the three value sources (recharts); comparison A vs B ("standardstyring" vs "prisoptimeret styring"); collapsible **"Forudsætninger"** list rendered from `assumptions[]`.
- Tenant branding: primary color + logo from catalog endpoint.
- No localStorage/sessionStorage; state in React only.

## 10. Disclaimer requirements (hard requirements)

1. Fixed disclaimer text rendered on the result screen, non-dismissable, and returned by the API in every `SimulationResult` (`disclaimer: str`) so no client can omit it accidentally:
   > "Beregningen er vejledende og baseret på historiske priser og standardforudsætninger. Den udgør ikke finansiel, teknisk eller skattemæssig rådgivning. Faktiske besparelser afhænger af fremtidige elpriser, afgifter, tariffer, forbrugsmønster og batteriets faktiske ydelse og kan afvige væsentligt."
2. Results must always be shown as **intervals**, never single-point payback.
3. `assumptions[]` must include at minimum: reference year used, DSO + tariff version date, tax scenario, realism factor, profile type, degradation, and the export/tax simplifications from §6.5/§7.2.
4. `SimulationResult` includes `engine_version` and an `input_echo` so any result can be reproduced.

## 11. Testing & acceptance criteria

**Unit:** battery physics (SoC limits, efficiency, power caps), price construction (pinned fixtures), tariff band resolution (incl. DST transitions and season boundaries), degradation schedule, decomposition-sums-to-total.
**Property:** energy balance invariant across seeded random configs (§7.1).
**Golden regression:** 3 canonical cases committed with expected outputs (±0.5%): (a) no PV, 10 kWh battery, DK2/Radius; (b) 6 kWp PV + 10 kWh, DK1/N1; (c) PV only baseline sanity.
**API:** contract tests for both endpoints; 422 paths.
**Widget:** builds to single bundle; demo.html runs against local API; manual checklist for the two-step flow.

**Definition of done (MVP):**
- `pytest` green, coverage ≥ 85% on `engine/`.
- Ingestion scripts produce all reference Parquets from scratch with one command each.
- `uvicorn api.main:app` + opening `embed/demo.html` yields a working end-to-end demo with the demo tenant.
- Simulation < 2 s; energy balance invariant holds for the golden cases.
- Disclaimer + assumptions visible in the widget without user interaction.

## 12. Build order (suggested Claude Code milestones)

1. **M1 — engine core:** models, data loaders (with tiny synthetic fixtures so tests run before real data exists), battery/pv/consumption components, strategy A, energy balance tests.
2. **M2 — prices & strategy B:** tariff/tax config, price construction, strategy B, economics + decomposition, golden cases.
3. **M3 — ingestion:** real data scripts, generate reference Parquets, re-baseline goldens.
4. **M4 — API + widget:** FastAPI, demo tenant, React widget, embed demo page.

## 13. Non-goals (MVP)

Reserve markets (FCR/aFRR/mFRR), Eloverblik import, LP/MILP dispatch, fixed-price contracts, PDF reports, auth/admin panel, payments, persistence/database, battery-to-grid export, income tax computation.

## 14. Open items for the product owner

- [ ] Populate real tariff rates for N1/Radius/Cerius (`tariffs.yaml`) and verify elafgift values/timeline (`taxes.yaml`).
- [ ] Verify feed-in fee values and prosumer sell-side tax treatment.
- [ ] Choose reference year for spot data (recommend most recent complete calendar year).
- [ ] Provide demo tenant branding (name/logo/colors) and 2–3 realistic battery products with installed prices.
- [ ] Legal review of disclaimer wording before anything is shown externally.
