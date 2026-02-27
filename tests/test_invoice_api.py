import os
import hashlib
import json
import pytest
import tempfile
from datetime import datetime, timezone

os.environ.setdefault("DB_PATH", "/tmp/test-ghost.db")
os.environ.setdefault("MAIN_MNEMONIC", "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
os.environ.setdefault("ADMIN_PATH", "testadmin")
os.environ.setdefault("PAYMENT_PATH", "testpay")
os.environ.setdefault("MAIN_WALLET_ADDRESS", "0x0000000000000000000000000000000000000001")

from app.db import init_db, open_db
init_db()

from app import create_app

@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    return application

@pytest.fixture(scope="module")
def client(app):
    return app.test_client()

@pytest.fixture(scope="module")
def api_key(app):
    with app.app_context():
        db = open_db()
        plaintext = "gp_testkey12345678901234567890123456"
        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        db.execute("INSERT OR REPLACE INTO api_keys (id, label, key_hash, key_prefix, is_active, created_at) VALUES ('testid','test',?,?,1,?)",
            (key_hash, plaintext[:8], datetime.now(timezone.utc).isoformat()))
        db.commit()
        db.close()
    return plaintext

def test_create_invoice(client, api_key):
    resp = client.post("/api/invoice", json={"chain": "BSC", "token": "USDT", "amount_native": "10.00"}, headers={"X-GhostPay-Key": api_key})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "invoice_id" in data
    assert data["status"] == "pending"
    assert data["chain"] == "BSC"
    assert data["token"] == "USDT"
    assert data["deposit_address"].startswith("0x")
    return data["invoice_id"]

def test_get_invoice(client, api_key):
    resp = client.post("/api/invoice", json={"chain": "POLYGON", "token": "USDT", "amount_native": "5.00"}, headers={"X-GhostPay-Key": api_key})
    invoice_id = resp.get_json()["invoice_id"]
    resp2 = client.get(f"/api/invoice/{invoice_id}")
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data["id"] == invoice_id
    assert data["status"] == "pending"

def test_get_invoice_not_found(client):
    resp = client.get("/api/invoice/nonexistent123456789")
    assert resp.status_code == 404

def test_cancel_invoice(client, api_key):
    resp = client.post("/api/invoice", json={"chain": "BSC", "token": "BNB", "amount_native": "0.01"}, headers={"X-GhostPay-Key": api_key})
    invoice_id = resp.get_json()["invoice_id"]
    cancel_resp = client.post(f"/api/invoice/{invoice_id}/cancel", headers={"X-GhostPay-Key": api_key})
    assert cancel_resp.status_code == 200
    status_resp = client.get(f"/api/invoice/{invoice_id}")
    assert status_resp.get_json()["status"] == "expired"

def test_list_invoices(client, api_key):
    resp = client.get("/api/invoices", headers={"X-GhostPay-Key": api_key})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "invoices" in data
    assert isinstance(data["invoices"], list)

def test_invalid_chain_rejected(client, api_key):
    resp = client.post("/api/invoice", json={"chain": "ETHEREUM", "token": "USDT", "amount_native": "1.00"}, headers={"X-GhostPay-Key": api_key})
    assert resp.status_code == 400

def test_missing_api_key_rejected(client):
    resp = client.post("/api/invoice", json={"chain": "BSC", "token": "USDT", "amount_native": "1.00"})
    assert resp.status_code == 401

def test_invalid_api_key_rejected(client):
    resp = client.post("/api/invoice", json={"chain": "BSC", "token": "USDT", "amount_native": "1.00"}, headers={"X-GhostPay-Key": "gp_invalid"})
    assert resp.status_code == 401
