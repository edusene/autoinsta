from flask import Blueprint, jsonify

from app import db
from app.extensions import limiter

bp = Blueprint("health", __name__)


@bp.get("/health")
@limiter.exempt
def health():
    try:
        with db.connection() as conn:
            conn.execute("select 1")
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "error"
    status = 200 if database == "ok" else 503
    return jsonify({"status": "ok" if status == 200 else "degraded", "database": database}), status
