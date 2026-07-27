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
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from besscalc import ENGINE_VERSION
from besscalc.data import DataError
from besscalc.economics import run_simulation
from besscalc.models import BatterySpec, SimulationRequest, SimulationResult

from .leads import LeadCreate, LeadSummary, create_lead, list_leads
from .notifications import send_lead_notification

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
    contact_phone: str | None = None
    contact_email: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None


class PVProduct(BaseModel):
    name: str
    kwp: float
    price_dkk_installed: float


class TenantCatalog(BaseModel):
    tenant_id: str
    branding: Branding
    products: list[BatterySpec]
    pv_products: list[PVProduct] = []
    leads_enabled: bool = False


class ApiSimulationRequest(BaseModel):
    tenant_id: str = Field(default="demo", min_length=1, max_length=64)
    request: SimulationRequest


@lru_cache(maxsize=32)
def _load_tenant_raw(tenant_id: str) -> dict:
    """Full parsed tenant YAML, incl. the internal `leads` block — never
    returned directly to clients (see load_tenant/TenantCatalog, which is
    the public-safe projection)."""
    safe = "".join(c for c in tenant_id if c.isalnum() or c in "-_")
    path = TENANTS_DIR / f"{safe}.yaml"
    if safe != tenant_id or not path.exists():
        raise HTTPException(status_code=404, detail=f"Ukendt tenant: {tenant_id}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_tenant(tenant_id: str) -> TenantCatalog:
    raw = _load_tenant_raw(tenant_id)
    leads_cfg = raw.get("leads") or {}
    return TenantCatalog(
        tenant_id=tenant_id,
        branding=Branding(**raw["branding"]),
        products=[BatterySpec(**p) for p in raw["products"]],
        pv_products=[PVProduct(**p) for p in raw.get("pv_products", [])],
        leads_enabled=bool(leads_cfg.get("notify_email") or leads_cfg.get("api_key")),
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


@app.post("/api/v1/tenants/{tenant_id}/leads")
def submit_lead(tenant_id: str, lead: LeadCreate) -> dict:
    load_tenant(tenant_id)  # 404 on unknown tenant
    try:
        lead_id, summary = create_lead(tenant_id, lead)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    leads_cfg = _load_tenant_raw(tenant_id).get("leads") or {}
    notify_email = leads_cfg.get("notify_email")
    if notify_email:
        send_lead_notification(notify_email, lead_id, lead.contact, summary)

    return {"id": lead_id}


@app.get("/api/v1/tenants/{tenant_id}/leads", response_model=list[LeadSummary])
def get_leads(tenant_id: str, x_leads_key: str | None = Header(default=None)) -> list[LeadSummary]:
    load_tenant(tenant_id)  # 404 on unknown tenant
    leads_cfg = _load_tenant_raw(tenant_id).get("leads") or {}
    expected_key = leads_cfg.get("api_key")
    if not expected_key or x_leads_key != expected_key:
        raise HTTPException(status_code=403, detail="Manglende eller forkert X-Leads-Key")
    return list_leads(tenant_id)


# --- demo conveniences -------------------------------------------------------

if DEMO_MODE:

    NO_CACHE_HEADERS = {"Cache-Control": "no-store"}

    @app.get("/demo", include_in_schema=False)
    def demo_page() -> FileResponse:
        if not DEMO_HTML.exists():
            raise HTTPException(status_code=404, detail="demo.html not built")
        return FileResponse(DEMO_HTML, headers=NO_CACHE_HEADERS)

    @app.get("/widget.js", include_in_schema=False)
    def widget_bundle() -> FileResponse:
        bundle = WIDGET_DIST / "widget.js"
        if not bundle.exists():
            raise HTTPException(
                status_code=404, detail="widget not built — run `npm run build` in widget/"
            )
        return FileResponse(bundle, media_type="application/javascript", headers=NO_CACHE_HEADERS)
