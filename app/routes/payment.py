import time
from flask import Blueprint, render_template, abort, current_app, Response, stream_with_context
from app.db import get_db, open_db

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

    @payment_bp.route("/pay/<invoice_id>/stream")
    def pay_stream(invoice_id):
        db_path = current_app.config["DB_PATH"]
        def generate():
            db = open_db(db_path)
            row = db.execute("SELECT status FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            db.close()
            if not row:
                yield "event: status\ndata: {\"status\": \"not_found\"}\n\n"
                return
            last = row["status"]
            yield f"event: status\ndata: {{\"status\": \"{last}\"}}\n\n"
            terminal = {"completed", "expired", "failed"}
            if last in terminal:
                return
            while True:
                time.sleep(10)
                yield ": ping\n\n"
                db = open_db(db_path)
                row = db.execute("SELECT status FROM invoices WHERE id=?", (invoice_id,)).fetchone()
                db.close()
                if not row:
                    return
                if row["status"] != last:
                    last = row["status"]
                    yield f"event: status\ndata: {{\"status\": \"{last}\"}}\n\n"
                if last in terminal:
                    return
        return Response(stream_with_context(generate()), content_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return payment_bp
