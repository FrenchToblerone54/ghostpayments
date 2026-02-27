from flask import Blueprint, render_template, abort, current_app
from app.db import get_db

def make_payment_bp(url_prefix):
    payment_bp = Blueprint("payment", __name__, url_prefix=url_prefix)

    @payment_bp.route("/pay/<invoice_id>")
    def pay_page(invoice_id):
        db = get_db()
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            abort(404)
        if invoice["status"] == "expired":
            return render_template("expired.html", invoice=dict(invoice))
        if invoice["status"] == "completed":
            return render_template("success.html", invoice=dict(invoice))
        return render_template("pay.html", invoice=dict(invoice))

    return payment_bp
