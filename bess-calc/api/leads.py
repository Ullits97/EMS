"""Lead capture: SQLite persistence for opt-in customer contact requests.

First persistence layer in the project (deliberate PoC-stage exception to
SPEC.md §13's "no database" MVP non-goal) — a lead is only ever created when
a customer explicitly submits contact info from the widget's result screen,
never as a side effect of `/simulate`.

DB path is overridable via BESSCALC_LEADS_DB (mirrors the existing
BESSCALC_DATA_DIR convention in besscalc/data.py), read at call time (not
import time) so tests can isolate a temp DB per run.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from besscalc.models import SimulationRequest, SimulationResult
from pydantic import BaseModel

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "leads.db"


def _db_path() -> Path:
    override = os.environ.get("BESSCALC_LEADS_DB")
    return Path(override) if override else _DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            name TEXT,
            phone TEXT,
            email TEXT,
            request_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    return conn


class LeadContact(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None

    def has_any(self) -> bool:
        return bool(self.name or self.phone or self.email)


class LeadCreate(BaseModel):
    contact: LeadContact
    request: SimulationRequest
    result: SimulationResult


class LeadSummary(BaseModel):
    id: int
    created_at: str
    name: str | None
    phone: str | None
    email: str | None
    annual_kwh: float
    battery_name: str
    pv_kwp: float | None
    annual_savings_dkk_low: float
    annual_savings_dkk_high: float
    npv_dkk: float
    payback_years_low: float | None
    payback_years_high: float | None


def _summarize(
    lead_id: int, created_at: str, contact: LeadContact, request: SimulationRequest, result: SimulationResult
) -> LeadSummary:
    strategy = result.strategies["price_optimized"]
    return LeadSummary(
        id=lead_id,
        created_at=created_at,
        name=contact.name,
        phone=contact.phone,
        email=contact.email,
        annual_kwh=request.consumption.annual_kwh,
        battery_name=request.battery.name,
        pv_kwp=request.pv.kwp if request.pv else None,
        annual_savings_dkk_low=strategy.annual_savings_dkk_low,
        annual_savings_dkk_high=strategy.annual_savings_dkk_high,
        npv_dkk=strategy.npv_dkk,
        payback_years_low=strategy.payback_years_low,
        payback_years_high=strategy.payback_years_high,
    )


def create_lead(tenant_id: str, payload: LeadCreate) -> tuple[int, LeadSummary]:
    """Insert a lead row. Raises ValueError if no contact info was provided."""
    if not payload.contact.has_any():
        raise ValueError("At least one of name/phone/email is required")

    created_at = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO leads (tenant_id, created_at, name, phone, email, request_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                created_at,
                payload.contact.name,
                payload.contact.phone,
                payload.contact.email,
                payload.request.model_dump_json(),
                payload.result.model_dump_json(),
            ),
        )
        conn.commit()
        lead_id = cur.lastrowid
    finally:
        conn.close()

    summary = _summarize(lead_id, created_at, payload.contact, payload.request, payload.result)
    return lead_id, summary


def list_leads(tenant_id: str) -> list[LeadSummary]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, created_at, name, phone, email, request_json, result_json
            FROM leads WHERE tenant_id = ? ORDER BY created_at DESC
            """,
            (tenant_id,),
        ).fetchall()
    finally:
        conn.close()

    summaries = []
    for row in rows:
        lead_id, created_at, name, phone, email, request_json, result_json = row
        contact = LeadContact(name=name, phone=phone, email=email)
        request = SimulationRequest.model_validate_json(request_json)
        result = SimulationResult.model_validate_json(result_json)
        summaries.append(_summarize(lead_id, created_at, contact, request, result))
    return summaries
