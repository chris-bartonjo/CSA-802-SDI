"""Unit tests for the Bookstore Integration API.  Run:  python -m pytest -v tests"""
import json
import sys
from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bookstore_api import create_app  # noqa: E402

KEY = {"X-API-Key": "test-key"}
GOOD_ORDER = {
    "customer": {"name": "Amina Wanjiru", "email": "amina@example.com"},
    "items": [{"book_id": "B001", "quantity": 2}, {"book_id": "B004", "quantity": 1}],
    "payment": {"method": "mpesa", "token": "tok_test_123"},
    "delivery_address": "12 Moi Avenue, Nairobi",
}


@pytest.fixture
def client(tmp_path):
    """A fresh app with its own copy of the seed data for every test."""
    app = create_app(data_dir=tmp_path, api_key="test-key")
    app.testing = True
    return app.test_client()


def stock(client, book_id):
    return client.get(f"/api/books/{book_id}", headers=KEY).get_json()["stock"]


# ---- Authentication ----
def test_missing_api_key_is_rejected(client):
    r = client.get("/api/books")
    assert r.status_code == 401
    assert r.get_json()["error"]["code"] == "unauthorized"


def test_wrong_api_key_is_rejected(client):
    assert client.get("/api/books", headers={"X-API-Key": "wrong"}).status_code == 401


def test_health_needs_no_key(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


# ---- Inventory ----
def test_get_book_details(client):
    r = client.get("/api/books/B001", headers=KEY)
    assert r.status_code == 200
    assert r.get_json()["title"] == "Things Fall Apart"


def test_unknown_book_returns_404(client):
    assert client.get("/api/books/B999", headers=KEY).status_code == 404


# ---- Sales: the integration flow ----
def test_place_order_updates_all_three_systems(client):
    r = client.post("/api/orders", json=GOOD_ORDER, headers=KEY)
    assert r.status_code == 201
    body = r.get_json()
    assert body["order"]["total"] == 2 * 950 + 4500          # Sales priced it from Inventory
    assert body["payment"]["status"] == "captured"             # Sales processed the payment
    assert stock(client, "B001") == 10 and stock(client, "B004") == 2   # Inventory decreased
    delivery = client.get(f"/api/deliveries/{body['delivery']['delivery_id']}", headers=KEY).get_json()
    assert delivery["order_id"] == body["order"]["order_id"]   # Delivery received the order
    assert delivery["status"] == "pending"


def test_order_can_be_read_back(client):
    order_id = client.post("/api/orders", json=GOOD_ORDER, headers=KEY).get_json()["order"]["order_id"]
    assert client.get(f"/api/orders/{order_id}", headers=KEY).get_json()["order_id"] == order_id


def test_out_of_stock_returns_409_and_changes_nothing(client):
    order = {**GOOD_ORDER, "items": [{"book_id": "B003", "quantity": 1}]}
    r = client.post("/api/orders", json=order, headers=KEY)
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "insufficient_stock"
    assert stock(client, "B003") == 0


def test_declined_payment_returns_402_and_keeps_stock(client):
    order = {**GOOD_ORDER, "payment": {"method": "card", "token": "tok_declined"}}
    r = client.post("/api/orders", json=order, headers=KEY)
    assert r.status_code == 402
    assert stock(client, "B001") == 12


@pytest.mark.parametrize("bad, field", [
    ({**GOOD_ORDER, "items": []}, "items"),
    ({**GOOD_ORDER, "items": [{"book_id": "B001", "quantity": 0}]}, "quantity"),
    ({**GOOD_ORDER, "payment": {"method": "cash", "token": "x"}}, "payment.method"),
    ({k: v for k, v in GOOD_ORDER.items() if k != "delivery_address"}, "delivery_address"),
    ({**GOOD_ORDER, "customer": {"name": "No Email"}}, "customer"),
])
def test_invalid_order_returns_400(client, bad, field):
    r = client.post("/api/orders", json=bad, headers=KEY)
    assert r.status_code == 400
    assert field in r.get_json()["error"]["message"]


def test_non_json_body_returns_400(client):
    r = client.post("/api/orders", data="not json", headers={**KEY, "Content-Type": "text/plain"})
    assert r.status_code == 400


# ---- Delivery ----
def test_update_delivery_details(client):
    delivery_id = client.post("/api/orders", json=GOOD_ORDER, headers=KEY).get_json()["delivery"]["delivery_id"]
    r = client.put(f"/api/deliveries/{delivery_id}", headers=KEY,
                   json={"status": "dispatched", "courier": "G4S Courier", "tracking_number": "G4S-778812"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "dispatched" and r.get_json()["courier"] == "G4S Courier"


def test_invalid_delivery_status_returns_400(client):
    delivery_id = client.post("/api/orders", json=GOOD_ORDER, headers=KEY).get_json()["delivery"]["delivery_id"]
    r = client.put(f"/api/deliveries/{delivery_id}", headers=KEY, json={"status": "lost"})
    assert r.status_code == 400


def test_delivered_delivery_cannot_change(client):
    delivery_id = client.post("/api/orders", json=GOOD_ORDER, headers=KEY).get_json()["delivery"]["delivery_id"]
    client.put(f"/api/deliveries/{delivery_id}", headers=KEY, json={"status": "delivered"})
    r = client.put(f"/api/deliveries/{delivery_id}", headers=KEY, json={"status": "in_transit"})
    assert r.status_code == 400


def test_unknown_delivery_returns_404(client):
    assert client.put("/api/deliveries/DEL-9999", headers=KEY, json={"status": "dispatched"}).status_code == 404


# ---- Documentation ----
def test_openapi_spec_is_valid_and_served(client):
    spec_path = Path(__file__).resolve().parent.parent / "openapi.yaml"
    validate(yaml.safe_load(spec_path.read_text()))   # raises if the spec is not valid OpenAPI 3
    assert client.get("/openapi.yaml").status_code == 200
    assert b"swagger-ui" in client.get("/docs").data
