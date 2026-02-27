from flask import Flask
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
    return app
