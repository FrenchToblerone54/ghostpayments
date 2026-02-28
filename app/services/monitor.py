import os
import logging
from datetime import datetime, timezone
from app.extensions import scheduler
from app.db import open_db
from app.services.chains import get_token_balance, get_native_balance, get_block_number, parse_token_amount
from app.services.sweeper import sweep_token, sweep_native
from decimal import Decimal

logger = logging.getLogger(__name__)

def _now():
    return datetime.now(timezone.utc).isoformat()

def poll_invoices():
    db = open_db()
    try:
        invoices = db.execute("SELECT * FROM invoices WHERE status IN ('pending','underpaid','confirming','sweeping')").fetchall()
        for inv in invoices:
            inv = dict(inv)
            now = datetime.now(timezone.utc)
            expires = datetime.fromisoformat(inv["expires_at"].replace("Z", "+00:00"))
            if now >= expires and inv["status"] in ("pending", "underpaid"):
                db.execute("UPDATE invoices SET status='expired' WHERE id=?", (inv["id"],))
                db.commit()
                continue
            chain = inv["chain"]
            token = inv["token"]
            try:
                if token == "USDT":
                    balance = get_token_balance(chain, inv["deposit_address"], token)
                    required = parse_token_amount(chain, token, inv["amount_requested"] or inv["amount_native"])
                    if balance >= required and inv["status"] == "pending":
                        confs = int(os.getenv(f"{chain}_CONFIRMATIONS", 3 if chain == "BSC" else 1))
                        db.execute("UPDATE invoices SET status='confirming', confirmed_at=? WHERE id=?", (_now(), inv["id"]))
                        db.commit()
                        inv["status"] = "confirming"
                    if inv["status"] == "confirming":
                        db.execute("UPDATE invoices SET status='sweeping' WHERE id=?", (inv["id"],))
                        db.commit()
                        inv["status"] = "sweeping"
                    if inv["status"] == "sweeping":
                        sweep_token(inv)
                else:
                    balance_wei = get_native_balance(chain, inv["deposit_address"])
                    required_wei = int(Decimal(inv["amount_requested"] or inv["amount_native"]) * Decimal(10 ** 18))
                    if balance_wei >= required_wei and inv["status"] == "pending":
                        db.execute("UPDATE invoices SET status='confirming', confirmed_at=? WHERE id=?", (_now(), inv["id"]))
                        db.commit()
                        inv["status"] = "confirming"
                    if inv["status"] == "confirming":
                        db.execute("UPDATE invoices SET status='sweeping' WHERE id=?", (inv["id"],))
                        db.commit()
                        inv["status"] = "sweeping"
                    if inv["status"] == "sweeping":
                        sweep_native(inv)
            except Exception as e:
                logger.error("Error processing invoice %s: %s", inv["id"], e, exc_info=True)
    finally:
        db.close()

def start_monitor(app):
    interval = int(os.getenv("POLL_INTERVAL_SECONDS", 20))
    if not scheduler.running:
        scheduler.start()
    def _job():
        with app.app_context():
            poll_invoices()
    scheduler.add_job(_job, "interval", seconds=interval, id="monitor", replace_existing=True)
