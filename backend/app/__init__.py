import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app import db
from app.config import Config
from app.errors import register_error_handlers
from app.extensions import limiter
from app.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


class JSONProvider(DefaultJSONProvider):
    """Datas em ISO 8601, UUID como string e Decimal como número."""

    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def _check_config(app: Flask) -> None:
    required = ["SECRET_KEY", "DATABASE_URL", "SUPABASE_URL"]
    missing = [k for k in required if not app.config.get(k)]
    if missing:
        raise RuntimeError(f"Variáveis de ambiente obrigatórias ausentes: {', '.join(missing)}")
    if app.config["ENV"] == "production" and len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("SECRET_KEY deve ter pelo menos 32 caracteres em produção.")


def create_app(config_class: type = Config, init_db: bool = True) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json = JSONProvider(app)
    app.json.ensure_ascii = False
    setup_logging(app.config["LOG_LEVEL"])
    _check_config(app)

    # Atrás de proxy/load balancer (HTTPS terminado no proxy)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
         allow_headers=["Authorization", "Content-Type"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    limiter.init_app(app)

    if init_db:
        db.init_pool(app.config["DATABASE_URL"], app.config["DB_POOL_MAX_SIZE"])

    from app.routes import auth, health, instagram, panel, webhooks, workflows

    for module in (auth, health, instagram, panel, webhooks, workflows):
        app.register_blueprint(module.bp)

    register_error_handlers(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if app.config["ENV"] == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    if init_db and app.config["EMBEDDED_WORKER"]:
        _start_embedded_worker(app)

    logger.info("App iniciada (env=%s)", app.config["ENV"])
    return app


def _start_embedded_worker(app: Flask) -> None:
    import threading

    from app.tasks.worker import run_forever

    def target():
        with app.app_context():
            run_forever()

    threading.Thread(target=target, name="embedded-worker", daemon=True).start()
    logger.info("Worker embutido iniciado (EMBEDDED_WORKER=true).")
