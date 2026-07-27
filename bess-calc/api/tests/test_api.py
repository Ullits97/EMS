"""API contract tests: both endpoints, 422 validation paths (SPEC §11)."""

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


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_catalog_contract():
    resp = client.get("/api/v1/tenants/demo/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "demo"
    assert body["branding"]["name"]
    assert body["branding"]["primary_color"].startswith("#")
    assert len(body["products"]) >= 2
    for product in body["products"]:
        assert product["capacity_kwh"] > 0
        assert product["price_dkk_installed"] > 0
    assert len(body["pv_products"]) >= 2
    for pv_product in body["pv_products"]:
        assert pv_product["kwp"] > 0
        assert pv_product["price_dkk_installed"] > 0


def test_catalog_unknown_tenant_404():
    assert client.get("/api/v1/tenants/nope/catalog").status_code == 404


def test_catalog_pv_products_defaults_to_empty(tmp_path, monkeypatch):
    import api.main as main

    tenant_dir = tmp_path / "tenants"
    tenant_dir.mkdir()
    (tenant_dir / "no_pv_catalog.yaml").write_text(
        """
branding:
  name: "No PV Catalog ApS"
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

    resp = client.get("/api/v1/tenants/no_pv_catalog/catalog")
    assert resp.status_code == 200
    assert resp.json()["pv_products"] == []

    main._load_tenant_raw.cache_clear()


def test_simulate_contract():
    resp = client.post("/api/v1/simulate", json=VALID_BODY)
    assert resp.status_code == 200
    body = resp.json()
    # SPEC §10: disclaimer in every result; intervals; reproducibility fields.
    assert "vejledende" in body["disclaimer"]
    assert body["engine_version"]
    assert body["input_echo"]["battery"]["capacity_kwh"] == 10
    assert body["assumptions"]
    for strategy in ("self_consumption", "price_optimized"):
        s = body["strategies"][strategy]
        assert s["annual_savings_dkk_low"] <= s["annual_savings_dkk_high"] + 1e-9
        y1 = s["year1"]
        total = (
            y1["savings_self_consumption_dkk"]
            + y1["savings_arbitrage_dkk"]
            + y1["savings_tariff_avoidance_dkk"]
        )
        assert total == pytest.approx(y1["savings_total_dkk"], abs=1.0)


def test_simulate_unknown_tenant_404():
    body = {**VALID_BODY, "tenant_id": "ghost"}
    assert client.post("/api/v1/simulate", json=body).status_code == 404


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["request"]["battery"].update(capacity_kwh=-5),
        lambda b: b["request"]["battery"].update(roundtrip_efficiency=1.5),
        lambda b: b["request"]["site"].update(dso="unknown_dso"),
        lambda b: b["request"]["site"].update(price_area="SE3"),
        lambda b: b["request"]["consumption"].update(profile="party"),
        lambda b: b["request"].pop("battery"),
        lambda b: b["request"]["scenario"].update(tax_scenario="fantasy"),
    ],
)
def test_simulate_validation_422(mutate):
    import copy

    body = copy.deepcopy(VALID_BODY)
    mutate(body)
    resp = client.post("/api/v1/simulate", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail and "loc" in detail[0]  # field-level messages


def test_simulate_no_pv():
    import copy

    body = copy.deepcopy(VALID_BODY)
    body["request"]["pv"] = None
    resp = client.post("/api/v1/simulate", json=body)
    assert resp.status_code == 200
    a = resp.json()["strategies"]["self_consumption"]
    assert a["year1"]["savings_total_dkk"] == pytest.approx(0.0, abs=1.0)
