"""Endpoints chamados pela Meta. Sem autenticação de usuário: a segurança vem do
verify token (GET) e da assinatura HMAC (POST e signed_request)."""
import hmac
import logging

from flask import Blueprint, current_app, jsonify, request

from app.errors import AppError
from app.extensions import limiter
from app.services import instagram_service, webhook_service

logger = logging.getLogger(__name__)
bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")

MAX_BODY_BYTES = 1_000_000


@bp.get("/meta")
@limiter.exempt
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")
    expected = current_app.config["META_VERIFY_TOKEN"]
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        logger.info("Webhook da Meta verificado com sucesso.")
        return challenge, 200, {"Content-Type": "text/plain"}
    logger.warning("Verificação de webhook recusada (mode=%s).", mode)
    return "Forbidden", 403


@bp.post("/meta")
@limiter.exempt
def receive():
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return "Payload too large", 413
    raw = request.get_data(cache=True)
    problem = webhook_service.signature_problem(raw, request.headers.get("X-Hub-Signature-256"))
    if problem:
        logger.warning("Webhook recusado: %s", problem)
        webhook_service.record_rejection(raw, problem, bool(request.headers.get("X-Hub-Signature-256")))
        return "Invalid signature", 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return "Bad request", 400
    # Se o banco falhar, a exceção vira 500 e a Meta reenvia depois (comportamento desejado).
    result = webhook_service.ingest(payload)
    return jsonify({"success": True, **result}), 200


def _signed_ig_user_id() -> str:
    data = webhook_service.parse_signed_request(request.form.get("signed_request", ""))
    if not data or not data.get("user_id"):
        raise AppError("INVALID_SIGNED_REQUEST", "signed_request inválido.", 400)
    return str(data["user_id"])


@bp.post("/meta/deauthorize")
@limiter.limit("60 per minute")
def deauthorize():
    instagram_service.handle_deauthorize(_signed_ig_user_id())
    return jsonify({"success": True})


@bp.post("/meta/data-deletion")
@limiter.limit("60 per minute")
def data_deletion():
    code = instagram_service.handle_data_deletion(_signed_ig_user_id())
    status_url = f"{current_app.config['FRONTEND_URL']}/data-deletion?code={code}"
    return jsonify({"url": status_url, "confirmation_code": code})
