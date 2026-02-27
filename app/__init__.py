from flask import Flask, render_template, request
from app.config import Config
from app.db import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    init_db()
    admin_prefix = f"/{app.config['ADMIN_PATH']}" if app.config["ADMIN_PATH"] else ""
    payment_prefix = f"/{app.config['PAYMENT_PATH']}" if app.config["PAYMENT_PATH"] else ""
    from app.routes.api import api_bp
    from app.routes.payment import make_payment_bp
    from app.routes.admin import make_admin_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(make_payment_bp(payment_prefix))
    app.register_blueprint(make_admin_bp(admin_prefix))
    from app.services.monitor import start_monitor
    start_monitor(app)
    @app.context_processor
    def inject_prefixes():
        return {"ap": admin_prefix, "pp": payment_prefix}
    @app.teardown_appcontext
    def close_db(e=None):
        from flask import g
        db = g.pop("db", None)
        if db is not None:
            db.close()
    _errors = {
        400: ("Bad Request", "The server could not understand your request."),
        404: ("Not Found", "This page doesn't exist or has moved."),
        405: ("Method Not Allowed", "That HTTP method isn't allowed here."),
        500: ("Server Error", "Something went wrong on our end."),
    }
    def _on_known_path():
        path = request.path
        if not admin_prefix and not payment_prefix:
            return True
        if admin_prefix and path.startswith(admin_prefix):
            return True
        if payment_prefix and path.startswith(payment_prefix):
            return True
        return False
    def _err(code):
        if not _on_known_path():
            return ("", 404)
        title, desc = _errors[code]
        return render_template("error.html", code=code, title=title, desc=desc), code
    app.register_error_handler(400, lambda e: _err(400))
    app.register_error_handler(404, lambda e: _err(404))
    app.register_error_handler(405, lambda e: _err(405))
    app.register_error_handler(500, lambda e: _err(500))
    return app
