import hashlib
import os
import json
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from nanoid import generate
from app.db import get_db
from app.services.wallet import derive_address

api_bp = Blueprint("api", __name__)

def _now():
    return datetime.now(timezone.utc).isoformat()

def _hash_key(key):
    return hashlib.sha256(key.encode()).hexdigest()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-GhostPay-Key", "")
        if not key:
            return jsonify({"error": "missing api key"}), 401
        key_hash = _hash_key(key)
        db = get_db()
        row = db.execute("SELECT * FROM api_keys WHERE key_hash=? AND is_active=1", (key_hash,)).fetchone()
        if not row:
            return jsonify({"error": "invalid or revoked api key"}), 401
        db.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (_now(), row["id"]))
        db.commit()
        return f(*args, **kwargs)
    return decorated

@api_bp.route("/api/invoice", methods=["POST"])
@require_api_key
def create_invoice():
    data = request.get_json(force=True)
    chain = data.get("chain", "").upper()
    token = data.get("token", "").upper()
    amount_native = str(data.get("amount_native", ""))
    amount_usd = data.get("amount_usd")
    webhook_url = data.get("webhook_url", "")
    metadata = json.dumps(data.get("metadata")) if data.get("metadata") else None
    if chain not in ("BSC", "POLYGON"):
        return jsonify({"error": "invalid chain"}), 400
    if token not in ("USDT", "BNB", "POL"):
        return jsonify({"error": "invalid token"}), 400
    if not amount_native:
        return jsonify({"error": "amount_native required"}), 400
    db = get_db()
    max_idx = db.execute("SELECT MAX(hd_index) FROM invoices").fetchone()[0]
    hd_index = (max_idx or 0) + 1
    mnemonic = current_app.config["MAIN_MNEMONIC"]
    deposit_address, _ = derive_address(mnemonic, hd_index)
    invoice_id = generate(size=20)
    ttl = current_app.config["INVOICE_TTL_MINUTES"]
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=ttl)).isoformat()
    db.execute("""INSERT INTO invoices
        (id, chain, token, amount_native, amount_usd, deposit_address, hd_index, status, webhook_url, metadata, created_at, expires_at)
        VALUES (?,?,?,?,?,?,?,'pending',?,?,?,?)""",
        (invoice_id, chain, token, amount_native, amount_usd, deposit_address, hd_index, webhook_url, metadata, now.isoformat(), expires_at))
    db.commit()
    payment_path = current_app.config["PAYMENT_PATH"]
    host = request.host_url.rstrip("/")
    return jsonify({
        "invoice_id": invoice_id,
        "deposit_address": deposit_address,
        "chain": chain,
        "token": token,
        "amount_native": amount_native,
        "payment_url": f"{host}/{payment_path}/pay/{invoice_id}",
        "expires_at": expires_at,
        "status": "pending"
    }), 201

@api_bp.route("/api/invoice/<invoice_id>", methods=["GET"])
def get_invoice(invoice_id):
    db = get_db()
    row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))

@api_bp.route("/api/invoice/<invoice_id>/cancel", methods=["POST"])
@require_api_key
def cancel_invoice(invoice_id):
    db = get_db()
    row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    if row["status"] not in ("pending", "underpaid"):
        return jsonify({"error": "cannot cancel invoice in current state"}), 400
    db.execute("UPDATE invoices SET status='expired' WHERE id=?", (invoice_id,))
    db.commit()
    return jsonify({"ok": True})

@api_bp.route("/api/invoices", methods=["GET"])
@require_api_key
def list_invoices():
    db = get_db()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    offset = (page - 1) * limit
    status = request.args.get("status")
    chain = request.args.get("chain")
    query = "SELECT * FROM invoices WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if chain:
        query += " AND chain=?"
        params.append(chain.upper())
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = db.execute(query, params).fetchall()
    total = db.execute("SELECT COUNT(*) FROM invoices WHERE 1=1" + (" AND status=?" if status else "") + (" AND chain=?" if chain else ""), [p for p in params if p not in (limit, offset)]).fetchone()[0]
    return jsonify({"invoices": [dict(r) for r in rows], "total": total, "page": page, "limit": limit})

@api_bp.route("/api/wallets", methods=["GET"])
@require_api_key
def get_wallets():
    from app.services.chains import get_native_balance
    from app.services.wallet import get_fee_address
    fee_mnemonic = current_app.config["FEE_MNEMONIC"]
    results = {}
    for chain in ("BSC", "POLYGON"):
        try:
            addr, _ = get_fee_address(fee_mnemonic, chain)
            bal = get_native_balance(chain, addr)
            results[chain] = {"address": addr, "native_balance_wei": bal}
        except Exception as e:
            results[chain] = {"error": str(e)}
    return jsonify(results)
