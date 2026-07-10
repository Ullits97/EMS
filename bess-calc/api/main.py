"""FastAPI backend for the BESS calculator (SPEC §8).

Run from the bess-calc directory:
    uvicorn api.main:app --reload

Endpoints:
    POST /api/v1/simulate
    GET  /api/v1/tenants/{tenant_id}/catalog
    GET  /health
Plus a convenience static mount of the built widget + demo page when
widget/dist exists (demo mode only).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from besscalc import ENGINE_VERSION
from besscalc.data import DataError
from besscalc.economics import run_simulation
from besscalc.models import BatterySpec, SimulationRequest, SimulationResult

TENANTS_DIR = Path(__file__).parent / "tenants"
WIDGET_DIST = Path(__file__).parent.parent / "widget" / "dist"
DEMO_HTML = Path(__file__).parent.parent / "widget" / "embed" / "demo.html"

DEMO_MODE = True  # allow-all CORS; flip off (and restrict origins) outside demos

app = FastAPI(title="BESS Calculator API", version=ENGINE_VERSION)

if DEMO_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


class Branding(BaseModel):
    name: str
    logo_url: str = ""
    primary_color: str = "#1d7a5f"
    secondary_color: str = "#123f31"


class TenantCatalog(BaseModel):
    tenant_id: str
    branding: Branding
    products: list[BatterySpec]


class ApiSimulationRequest(BaseModel):
    tenant_id: str = Field(default="demo", min_length=1, max_length=64)
    request: SimulationRequest


@lru_cache(maxsize=32)
def load_tenant(tenant_id: str) -> TenantCatalog:
    safe = "".join(c for c in tenant_id if c.isalnum() or c in "-_")
    path = TENANTS_DIR / f"{safe}.yaml"
    if safe != tenant_id or not path.exists():
        raise HTTPException(status_code=404, detail=f"Ukendt tenant: {tenant_id}")
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return TenantCatalog(
        tenant_id=tenant_id,
        branding=Branding(**raw["branding"]),
        products=[BatterySpec(**p) for p in raw["products"]],
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@app.get("/api/v1/tenants/{tenant_id}/catalog", response_model=TenantCatalog)
def get_catalog(tenant_id: str) -> TenantCatalog:
    return load_tenant(tenant_id)


@app.post("/api/v1/simulate", response_model=SimulationResult)
def simulate(body: ApiSimulationRequest) -> SimulationResult:
    load_tenant(body.tenant_id)  # 404 on unknown tenant
    try:
        return run_simulation(body.request)
    except DataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# --- demo conveniences -------------------------------------------------------

if DEMO_MODE:

    @app.get("/demo", include_in_schema=False)
    def demo_page() -> FileResponse:
        if not DEMO_HTML.exists():
            raise HTTPException(status_code=404, detail="demo.html not built")
        return FileResponse(DEMO_HTML)

    @app.get("/widget.js", include_in_schema=False)
    def widget_bundle() -> FileResponse:
        bundle = WIDGET_DIST / "widget.js"
        if not bundle.exists():
            raise HTTPException(
                status_code=404, detail="widget not built — run `npm run build` in widget/"
            )
        return FileResponse(bundle, media_type="application/javascript")
