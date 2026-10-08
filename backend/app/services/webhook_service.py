"""Webhooks da Meta: validação, ingestão rápida e processamento em background.

Fluxo:
  rota POST /webhooks/meta -> verify_signature() -> ingest()  (grava evento + job, responde 200)
  worker -> process_event() -> contato -> workflows ativos -> engine.start()
"""
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from flask import current_app

from app import db
from app.repositories import contact_repository, instagram_repository, settings_repository
from app.repositories import webhook_event_repository as event_repo
from app.repositories import workflow_repository
from app.services import instagram_service, meta_client
from app.tasks import queue
from app.workflow import engine
from app.workflow.nodes import COMMENT_TRIGGER, MESSAGE_TRIGGER

logger = logging.getLogger(__name__)


# --- assinatura ---------------------------------------------------------------

def _secrets() -> list[str]:
    cfg = current_app.config
    return [s for s in [cfg.get("META_APP_SECRET"), *cfg.get("META_WEBHOOK_EXTRA_SECRETS", [])] if s]


def verify_signature(raw_body: bytes, header_value: str | None) -> bool:
    """Valida X-Hub-Signature-256 (HMAC-SHA256 do corpo bruto com o app secret)."""
    if not header_value or not header_value.startswith("sha256="):
        return False
    received = header_value.removeprefix("sha256=").strip()
    for secret in _secrets():
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, received):
            return True
    return False


def parse_signed_request(signed_request: str) -> dict | None:
    """Valida o signed_request dos callbacks de desautorização/exclusão de dados."""
    try:
        encoded_sig, payload = signed_request.split(".", 1)
        sig = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if str(data.get("algorithm", "")).upper() != "HMAC-SHA256":
        return None
    for secret in _secrets():
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
        if hmac.compare_digest(expected, sig):
            return data
    return None


# --- ingestão (dentro do request — precisa ser rápida) ------------------------

def _dedupe_key(field: str, item: dict, fallback_id: str | None) -> str:
    if fallback_id:
        return f"{field}:{fallback_id}"
    digest = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
    return f"{field}:sha256:{digest}"


def _split(payload: dict) -> list[tuple[str, str, str, dict]]:
    """Quebra o payload em itens (dedupe_key, field, ig_account_id, item)."""
    items = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        account_id = str(entry.get("id", ""))
        for item in entry.get("messaging") or []:
            if not isinstance(item, dict):
                continue
            mid = (item.get("message") or {}).get("mid") if isinstance(item.get("message"), dict) else None
            field = "messages" if "message" in item else "messaging_other"
            items.append((_dedupe_key(field, item, mid), field, account_id, item))
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            field = str(change.get("field", "unknown"))
            value = change.get("value") if isinstance(change.get("value"), dict) else {}
            comment_id = (value.get("id") or value.get("comment_id")) if field == "comments" else None
            items.append((_dedupe_key(field, value, comment_id), field, account_id, value))
    return items


def ingest(payload: dict) -> dict:
    if payload.get("object") != "instagram":
        logger.info("Webhook ignorado: object=%s", payload.get("object"))
        return {"received": 0, "duplicates": 0}
    received = duplicates = 0
    with db.connection() as conn:
        for dedupe_key, field, account_id, item in _split(payload):
            row = event_repo.insert_if_new(conn, dedupe_key, "instagram", field, account_id, item)
            if row is None:
                duplicates += 1
                continue
            queue.enqueue(conn, "process_webhook_event", {"event_id": str(row["id"])})
            received += 1
    logger.info("Webhook recebido: %s novo(s), %s duplicado(s)", received, duplicates)
    return {"received": received, "duplicates": duplicates}


# --- processamento (worker) ---------------------------------------------------

def _ignore(event_id: str, reason: str, account: dict | None = None) -> None:
    with db.connection() as conn:
        event_repo.set_status(conn, event_id, "ignored", reason,
                              account and str(account["id"]), account and str(account["user_id"]))
    logger.info("Evento %s ignorado: %s", event_id, reason)


def _enrich_contact(account: dict, contact: dict) -> dict:
    """Busca nome/username do contato (permitido após ele enviar mensagem)."""
    if contact.get("name") and contact.get("username"):
        return contact
    try:
        token = instagram_service.get_access_token(str(account["id"]))
        profile = meta_client.get_user_profile(token, contact["ig_scoped_id"])
    except Exception as exc:  # noqa: BLE001 - enriquecimento é opcional
        logger.info("Perfil do contato %s indisponível: %s", contact["id"], exc)
        return contact
    with db.connection() as conn:
        contact_repository.update_profile(conn, contact["id"], profile.get("username"), profile.get("name"), {})
    return {**contact, "username": profile.get("username") or contact.get("username"),
            "name": profile.get("name") or contact.get("name")}


def process_event(event_id: str) -> None:
    with db.connection() as conn:
        event = event_repo.get(conn, event_id)
    if not event or event["status"] != "received":
        return  # já processado (idempotência)

    with db.connection() as conn:
        account = instagram_repository.get_by_ig_user_id(conn, event["ig_account_id"])
        if account:
            instagram_repository.mark_webhook_received(conn, account["id"])
    if not account:
        return _ignore(event_id, "Conta do Instagram não cadastrada na plataforma.")
    if account["status"] != "connected":
        return _ignore(event_id, f"Conta com status '{account['status']}'.", account)

    item = event["payload"]
    user_id = str(account["user_id"])
    ctx: dict = {
        "trigger": {"received_at": datetime.now(timezone.utc).isoformat()},
        "vars": {},
        "ai": {},
        "_sys": {"account_id": str(account["id"])},
    }

    if event["field"] == "messages":
        message = item.get("message") or {}
        sender_id = str((item.get("sender") or {}).get("id", ""))
        if message.get("is_echo") or sender_id == account["ig_user_id"]:
            return _ignore(event_id, "Mensagem enviada pela própria conta (eco).", account)
        if message.get("is_deleted"):
            return _ignore(event_id, "Mensagem apagada.", account)
        if not sender_id:
            return _ignore(event_id, "Mensagem sem remetente.", account)
        trigger_type = MESSAGE_TRIGGER
        text = message.get("text") or ""
        ctx["message"] = {"id": message.get("mid"), "text": text,
                          "has_attachments": bool(message.get("attachments"))}
        contact_igsid, contact_username = sender_id, None
        summary = text[:200] or "[mensagem sem texto]"
    elif event["field"] == "comments":
        sender = item.get("from") or {}
        sender_id = str(sender.get("id", ""))
        if sender_id == account["ig_user_id"]:
            return _ignore(event_id, "Comentário feito pela própria conta.", account)
        if not sender_id:
            return _ignore(event_id, "Comentário sem autor.", account)
        trigger_type = COMMENT_TRIGGER
        media = item.get("media") or {}
        ctx["comment"] = {
            "id": item.get("id") or item.get("comment_id"),
            "text": item.get("text") or "",
            "media_id": media.get("id"),
            "media_type": media.get("media_product_type"),
            "parent_id": item.get("parent_id"),
        }
        contact_igsid, contact_username = sender_id, sender.get("username")
        summary = (item.get("text") or "")[:200]
    else:
        return _ignore(event_id, f"Campo '{event['field']}' não tratado pelo MVP.", account)

    with db.connection() as conn:
        contact = contact_repository.upsert_from_event(conn, user_id, str(account["id"]), contact_igsid,
                                                       contact_username, event["field"])
        contact_repository.add_event(conn, user_id, contact["id"], event["field"], summary,
                                     {"webhook_event_id": str(event_id)})
        workflows = workflow_repository.list_active_by_trigger(conn, user_id, trigger_type)
        settings = settings_repository.get(conn, user_id)
        # Marca como processado ANTES de executar: um retry do job não duplica mensagens enviadas.
        event_repo.set_status(conn, event_id, "processed", f"{len(workflows)} workflow(s) compatível(is).",
                              str(account["id"]), user_id)

    if trigger_type == MESSAGE_TRIGGER:
        contact = _enrich_contact(account, contact)
    ctx["contact"] = {"id": str(contact["id"]), "ig_id": contact_igsid,
                      "username": contact.get("username") or "", "name": contact.get("name") or ""}
    if settings and settings.get("ai_default_model"):
        ctx["_sys"]["ai_default_model"] = settings["ai_default_model"]

    trigger_event = {"field": event["field"], "summary": summary,
                     **({"comment_id": ctx["comment"]["id"], "media_id": ctx["comment"]["media_id"]}
                        if trigger_type == COMMENT_TRIGGER else {"message_id": ctx["message"]["id"]})}

    for workflow in workflows:
        if trigger_type == COMMENT_TRIGGER:
            trigger_cfg = _trigger_config(workflow)
            wanted_media = (trigger_cfg.get("media_id") or "").strip()
            if wanted_media and wanted_media != str(ctx["comment"]["media_id"] or ""):
                continue
        try:
            engine.start(workflow, json.loads(json.dumps(ctx)), trigger_event, str(contact["id"]), str(event_id))
        except Exception:  # noqa: BLE001 - um workflow com problema não bloqueia os outros
            logger.exception("Falha ao iniciar workflow %s para o evento %s", workflow["id"], event_id)


def _trigger_config(workflow: dict) -> dict:
    for node in workflow["graph"].get("nodes", []):
        if node["type"] == workflow["trigger_type"]:
            return node.get("data", {}).get("config", {})
    return {}
