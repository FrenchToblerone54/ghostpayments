import hashlib
import os
import re
from datetime import datetime, timezone
from flask import Blueprint, render_template, abort, request, redirect, flash, jsonify, current_app
from nanoid import generate
from app.db import get_db
from app.services.env_writer import write_env

def _now():
    return datetime.now(timezone.utc).isoformat()

def _hash_key(key):
    return hashlib.sha256(key.encode()).hexdigest()

def make_admin_bp(url_prefix):
    admin_bp = Blueprint("admin", __name__, url_prefix=url_prefix)

    @admin_bp.route("/")
    @admin_bp.route("/dashboard")
    def dashboard():
        db = get_db()
        stats = {
            "total": db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
            "completed": db.execute("SELECT COUNT(*) FROM invoices WHERE status='completed'").fetchone()[0],
            "pending": db.execute("SELECT COUNT(*) FROM invoices WHERE status='pending'").fetchone()[0],
            "expired": db.execute("SELECT COUNT(*) FROM invoices WHERE status='expired'").fetchone()[0],
        }
        invoices = db.execute("SELECT * FROM invoices ORDER BY created_at DESC LIMIT 50").fetchall()
        fee_balances = {}
        try:
            from app.services.chains import get_native_balance
            from app.services.wallet import get_fee_address
            fee_mnemonic = current_app.config["FEE_MNEMONIC"]
            fee_privkey = current_app.config["FEE_PRIVATE_KEY"]
            for chain in ("BSC", "POLYGON"):
                addr, _ = get_fee_address(fee_mnemonic or None)
                bal_wei = get_native_balance(chain, addr)
                fee_balances[chain] = {"address": addr, "balance_wei": bal_wei, "balance": bal_wei / 10**18}
        except Exception:
            pass
        return render_template("admin/dashboard.html", stats=stats, invoices=[dict(i) for i in invoices], fee_balances=fee_balances)

    @admin_bp.route("/keys", methods=["GET", "POST"])
    def keys():
        db = get_db()
        if request.method == "POST":
            label = request.form.get("label", "").strip()
            if not label:
                flash("Label is required.", "error")
                return redirect(request.referrer or url_prefix + "/keys")
            plaintext = "gp_" + generate(size=32)
            key_hash = _hash_key(plaintext)
            key_prefix = plaintext[:8]
            key_id = generate(size=20)
            db.execute("INSERT INTO api_keys (id, label, key_hash, key_prefix, is_active, created_at) VALUES (?,?,?,?,1,?)",
                (key_id, label, key_hash, key_prefix, _now()))
            db.commit()
            flash(f"API Key created: {plaintext}", "key")
            return redirect(url_prefix + "/keys")
        page = max(1, int(request.args.get("page", 1)))
        total = db.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
        pages = max(1, (total + 9) // 10)
        api_keys = db.execute("SELECT * FROM api_keys ORDER BY created_at DESC LIMIT 10 OFFSET ?", ((page - 1) * 10,)).fetchall()
        return render_template("admin/keys.html", api_keys=[dict(k) for k in api_keys], page=page, pages=pages)

    @admin_bp.route("/keys/<key_id>/revoke", methods=["POST"])
    def revoke_key(key_id):
        db = get_db()
        db.execute("UPDATE api_keys SET is_active=0 WHERE id=?", (key_id,))
        db.commit()
        flash("Key revoked.", "success")
        return redirect(url_prefix + "/keys")

    @admin_bp.route("/keys/<key_id>/delete", methods=["POST"])
    def delete_key(key_id):
        db = get_db()
        db.execute("DELETE FROM api_keys WHERE id=? AND is_active=0", (key_id,))
        db.commit()
        flash("Key deleted.", "success")
        return redirect(url_prefix + "/keys")

    @admin_bp.route("/invoice/<invoice_id>")
    def invoice_detail(invoice_id):
        db = get_db()
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            abort(404)
        return render_template("admin/detail.html", invoice=dict(invoice))

    @admin_bp.route("/settings")
    def settings():
        cfg = current_app.config
        return render_template("admin/settings.html",
            admin_path_val=cfg["ADMIN_PATH"], payment_path_val=cfg["PAYMENT_PATH"],
            main_wallet=cfg["MAIN_WALLET_ADDRESS"], bsc_rpc=cfg["BSC_RPC_URL"],
            pol_rpc=cfg["POLYGON_RPC_URL"], invoice_ttl=cfg["INVOICE_TTL_MINUTES"],
            bsc_confs=cfg["BSC_CONFIRMATIONS"], pol_confs=cfg["POLYGON_CONFIRMATIONS"],
            gas_buffer=cfg["GAS_BUFFER_PERCENT"], poll_interval=cfg["POLL_INTERVAL_SECONDS"],
            auto_update=cfg["AUTO_UPDATE"], update_interval=cfg["UPDATE_CHECK_INTERVAL"],
            waitress_threads=cfg["WAITRESS_THREADS"],
            update_on_startup=cfg["UPDATE_CHECK_ON_STARTUP"],
            http_proxy=cfg["UPDATE_HTTP_PROXY"], https_proxy=cfg["UPDATE_HTTPS_PROXY"])

    @admin_bp.route("/settings/paths", methods=["POST"])
    def save_paths():
        new_admin = request.form.get("admin_path", "").strip()
        new_payment = request.form.get("payment_path", "").strip()
        valid = re.compile(r"^[a-zA-Z0-9\-]{10,40}$")
        if new_admin and not valid.match(new_admin):
            flash("Admin path must be 10-40 chars, alphanumeric + hyphens only (or empty to disable).", "error")
            return redirect(url_prefix + "/settings")
        if new_payment and not valid.match(new_payment):
            flash("Payment path must be 10-40 chars, alphanumeric + hyphens only (or empty to disable).", "error")
            return redirect(url_prefix + "/settings")
        if new_admin and new_payment and new_admin == new_payment:
            flash("Admin and payment paths must differ.", "error")
            return redirect(url_prefix + "/settings")
        write_env({"ADMIN_PATH": new_admin, "PAYMENT_PATH": new_payment})
        flash("Paths saved. Restart required.", "restart")
        return redirect(url_prefix + "/settings")

    @admin_bp.route("/settings/wallets", methods=["POST"])
    def save_wallets():
        updates = {}
        for field in ("MAIN_MNEMONIC", "FEE_MNEMONIC"):
            val = request.form.get(field, "").strip()
            if val:
                updates[field] = val
        fee_key = request.form.get("FEE_PRIVATE_KEY", "").strip()
        if fee_key:
            updates["FEE_PRIVATE_KEY"] = fee_key
        addr = request.form.get("MAIN_WALLET_ADDRESS", "").strip()
        if addr:
            if not re.match(r"^0x[0-9a-fA-F]{40}$", addr):
                flash("Invalid wallet address.", "error")
                return redirect(url_prefix + "/settings")
            updates["MAIN_WALLET_ADDRESS"] = addr
        for field in ("BSC_RPC_URL", "POLYGON_RPC_URL"):
            val = request.form.get(field, "").strip()
            if val:
                updates[field] = val
        if updates:
            write_env(updates)
            flash("Wallet settings saved. Restart required.", "restart")
        return redirect(url_prefix + "/settings")

    @admin_bp.route("/settings/tuning", methods=["POST"])
    def save_tuning():
        updates = {}
        int_fields = {"INVOICE_TTL_MINUTES": (1, 1440), "BSC_CONFIRMATIONS": (1, 100),
            "POLYGON_CONFIRMATIONS": (1, 100), "GAS_BUFFER_PERCENT": (0, 100),
            "POLL_INTERVAL_SECONDS": (5, 3600), "UPDATE_CHECK_INTERVAL": (60, 86400),
            "WAITRESS_THREADS": (2, 256)}
        for key, (mn, mx) in int_fields.items():
            val = request.form.get(key, "").strip()
            if val:
                try:
                    v = int(val)
                    if mn <= v <= mx:
                        updates[key] = str(v)
                except ValueError:
                    pass
        auto_update = request.form.get("AUTO_UPDATE", "false")
        updates["AUTO_UPDATE"] = "true" if auto_update == "true" else "false"
        update_on_startup = request.form.get("UPDATE_CHECK_ON_STARTUP", "false")
        updates["UPDATE_CHECK_ON_STARTUP"] = "true" if update_on_startup == "true" else "false"
        for field in ("UPDATE_HTTP_PROXY", "UPDATE_HTTPS_PROXY"):
            updates[field] = request.form.get(field, "").strip()
        if updates:
            write_env(updates)
            flash("Tuning saved. Restart required for thread count changes.", "success")
        return redirect(url_prefix + "/settings")

    @admin_bp.route("/settings/test-rpc", methods=["POST"])
    def test_rpc():
        chain = request.form.get("chain", "").upper()
        url = request.form.get("url", "").strip()
        if chain not in ("BSC", "POLYGON") or not url:
            return jsonify({"ok": False, "error": "invalid params"})
        try:
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider(url))
            block = w3.eth.block_number
            return jsonify({"ok": True, "block": block})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @admin_bp.route("/system/update-check")
    def system_update_check():
        import asyncio
        from updater import Updater
        updater = Updater()
        loop = asyncio.new_event_loop()
        try:
            latest = loop.run_until_complete(updater.check_for_update())
        finally:
            loop.close()
        return jsonify({"current": updater.current_version, "latest": latest, "update_available": bool(latest)})

    @admin_bp.route("/system/update-apply", methods=["POST"])
    def system_update_apply():
        import asyncio, threading
        from updater import Updater
        updater = Updater(
            http_proxy=current_app.config["UPDATE_HTTP_PROXY"],
            https_proxy=current_app.config["UPDATE_HTTPS_PROXY"],
        )
        def _do():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            latest = loop.run_until_complete(updater.check_for_update())
            if latest:
                loop.run_until_complete(updater.download_update(latest))
        threading.Thread(target=_do, daemon=True).start()
        return jsonify({"ok": True, "message": "Update downloading, service will restart automatically."})

    @admin_bp.route("/system/restart", methods=["POST"])
    def system_restart():
        import os, signal, threading
        def _do():
            import time
            time.sleep(0.3)
            os.kill(os.getpid(), signal.SIGTERM)
        threading.Thread(target=_do, daemon=True).start()
        return jsonify({"ok": True})

    return admin_bp
