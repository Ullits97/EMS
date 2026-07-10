# BESS Calculator (white-label)

Simulation-based home battery (BESS) economics calculator for the Danish
market: a deterministic Python engine, a FastAPI backend, and an embeddable
React widget. See `SPEC.md` for the full spec; code and comments are English,
end-user UI text is Danish.

> **Data status:** the committed reference datasets under `data/reference/`
> are **synthetic placeholders** (flagged in `meta.json` and warned about in
> every result). Run the ingestion scripts below on a machine with network
> access, and populate the `TODO verify` tariff/tax rates in
> `engine/src/besscalc/config/`, before showing results to anyone.

## Quickstart

```bash
# 1. Engine (Python 3.11+)
pip install -e engine[dev]

# 2. Reference data (offline synthetic fallback; see "Real data" below)
python ingestion/build_synthetic_reference.py
python ingestion/build_consumption.py

# 3. Tests
python -m pytest engine/tests api/tests

# 4. API + demo
pip install fastapi uvicorn
uvicorn api.main:app --port 8000
# open http://localhost:8000/demo  (uses the committed widget bundle)
```

The `/demo` page serves `widget/embed/demo.html`, a fake installer site that
embeds the widget via the script-tag contract:

```html
<div id="bess-calc" data-tenant="demo" data-api="http://localhost:8000"></div>
<script src="http://localhost:8000/widget.js"></script>
```

## Real data (one command each)

```bash
python ingestion/fetch_spot.py --year 2025   # Energi Data Service -> spot_dk1/dk2.parquet
python ingestion/fetch_pv.py                 # PVGIS -> pv_profiles.parquet
python ingestion/build_consumption.py        # synthetic standard profiles (offline)
```

After replacing reference data, re-baseline the golden regression tests:
`python engine/tests/update_goldens.py` and review the diff.

## Widget development

```bash
cd widget
npm install
npm run build     # -> dist/widget.js (single IIFE bundle, committed)
```

## Layout

```
engine/      Python simulation engine (besscalc package + tests)
data/        reference-year Parquets (committed) + raw downloads (ignored)
ingestion/   one-off data-fetch/build scripts (runtime never calls the network)
api/         FastAPI app + per-tenant YAML config (api/tenants/<id>.yaml)
widget/      React 18 + Vite embeddable widget + embed/demo.html
```

## Multi-tenant

One YAML per tenant in `api/tenants/` (branding + battery product catalog).
No auth/admin UI in the MVP; copy `demo.yaml` to onboard a tenant.

## Open items for the product owner (SPEC §14)

- Populate real tariff rates (`tariffs.yaml`) and elafgift values (`taxes.yaml`) — all marked `TODO verify`.
- Verify feed-in fees and prosumer sell-side tax treatment.
- Replace synthetic reference data with a real reference year.
- Provide real tenant branding and priced battery products.
- Legal review of the disclaimer wording before external use.
