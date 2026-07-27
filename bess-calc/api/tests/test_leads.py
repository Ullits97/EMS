"""Lead-capture endpoint tests: creation, validation, and the X-Leads-Key
gate on the listing endpoint. DB is isolated per test via BESSCALC_LEADS_DB
pointing at a tmp_path file; SMTP_HOST is cleared so notification sending
always takes its no-op (logged) path instead of touching a real network."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.main import app  # noqa: E402

client = TestClient(app)

VALID_BODY = {
    "tenant_id": "demo",
    "request": {
        "battery": {
            "name": "Standard 10 kWh",
            "capacity_kwh": 10,
            "power_kw": 5,
            "roundtrip_efficiency": 0.92,
            "depth_of_discharge": 0.9,
            "price_dkk_installed": 52000,
        },
        "pv": {"kwp": 6, "orientation": "S"},
        "consumption": {"annual_kwh": 5500, "profile": "base_ev"},
        "site": {"price_area": "DK1", "dso": "n1"},
        "scenario": {"tax_scenario": "low_2026_27"},
    },
}

DEMO_LEADS_KEY = "demo-leads-key-change-me"  # matches api/tenants/demo.yaml


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BESSCALC_LEADS_DB", str(tmp_path / "leads.db"))
    monkeypatch.delenv("SMTP_HOST", raising=False)


def _simulate() -> dict:
    resp = client.post("/api/v1/simulate", json=VALID_BODY)
    assert resp.status_code == 200
    return resp.json()


def test_submit_lead_returns_id():
    result = _simulate()
    body = {"contact": {"email": "kunde@example.dk"}, "request": result["input_echo"], "result": result}
    resp = client.post("/api/v1/tenants/demo/leads", json=body)
    assert resp.status_code == 200
    assert isinstance(resp.json()["id"], int)


def test_submit_lead_without_contact_422():
    result = _simulate()
    body = {"contact": {}, "request": result["input_echo"], "result": result}
    resp = client.post("/api/v1/tenants/demo/leads", json=body)
    assert resp.status_code == 422


def test_submit_lead_unknown_tenant_404():
    result = _simulate()
    body = {"contact": {"phone": "12345678"}, "request": result["input_echo"], "result": result}
    resp = client.post("/api/v1/tenants/ghost/leads", json=body)
    assert resp.status_code == 404


def test_get_leads_requires_key():
    assert client.get("/api/v1/tenants/demo/leads").status_code == 403
    assert (
        client.get("/api/v1/tenants/demo/leads", headers={"X-Leads-Key": "wrong"}).status_code
        == 403
    )


def test_get_leads_unknown_tenant_404():
    resp = client.get("/api/v1/tenants/ghost/leads", headers={"X-Leads-Key": DEMO_LEADS_KEY})
    assert resp.status_code == 404


def test_get_leads_returns_created_lead_with_correct_summary():
    result = _simulate()
    body = {
        "contact": {"name": "Jens Hansen", "phone": "12345678", "email": "jens@example.dk"},
        "request": result["input_echo"],
        "result": result,
    }
    create_resp = client.post("/api/v1/tenants/demo/leads", json=body)
    lead_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/tenants/demo/leads", headers={"X-Leads-Key": DEMO_LEADS_KEY})
    assert list_resp.status_code == 200
    leads = list_resp.json()
    assert any(lead["id"] == lead_id for lead in leads)

    lead = next(lead for lead in leads if lead["id"] == lead_id)
    assert lead["name"] == "Jens Hansen"
    assert lead["phone"] == "12345678"
    assert lead["email"] == "jens@example.dk"
    assert lead["annual_kwh"] == pytest.approx(5500)
    assert lead["battery_name"] == "Standard 10 kWh"
    assert lead["pv_kwp"] == pytest.approx(6)
    strategy = result["strategies"]["price_optimized"]
    assert lead["annual_savings_dkk_low"] == pytest.approx(strategy["annual_savings_dkk_low"])
    assert lead["npv_dkk"] == pytest.approx(strategy["npv_dkk"])


def test_catalog_reports_leads_enabled_for_demo_tenant():
    resp = client.get("/api/v1/tenants/demo/catalog")
    assert resp.status_code == 200
    assert resp.json()["leads_enabled"] is True


def test_catalog_reports_leads_disabled_without_leads_block(tmp_path, monkeypatch):
    import api.main as main

    tenant_dir = tmp_path / "tenants"
    tenant_dir.mkdir()
    (tenant_dir / "no_leads.yaml").write_text(
        """
branding:
  name: "No Leads ApS"
products:
  - name: "Test 5 kWh"
    capacity_kwh: 5
    power_kw: 3
    roundtrip_efficiency: 0.9
    depth_of_discharge: 0.9
    price_dkk_installed: 30000
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "TENANTS_DIR", tenant_dir)
    main._load_tenant_raw.cache_clear()

    resp = client.get("/api/v1/tenants/no_leads/catalog")
    assert resp.status_code == 200
    assert resp.json()["leads_enabled"] is False

    main._load_tenant_raw.cache_clear()
