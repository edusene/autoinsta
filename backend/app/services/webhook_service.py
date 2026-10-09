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
import uuid
from datetime import datetime, timezone

from flask import current_app

from app import db
from app.errors import AppError
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


def signature_problem(raw_body: bytes, header_value: str | None) -> str | None:
    """Valida X-Hub-Signature-256 (HMAC-SHA256 do corpo bruto). Retorna o motivo da recusa ou None."""
    if not _secrets():
        logger.error("Webhook recusado: nenhum segredo configurado (defina META_APP_SECRET).")
        return "Nenhuma chave secreta configurada no servidor (META_APP_SECRET)."
    if not header_value or not header_value.startswith("sha256="):
        return "Requisição sem assinatura X-Hub-Signature-256."
    received = header_value.removeprefix("sha256=").strip()
    for secret in _secrets():
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, received):
            return None
    return "Assinatura não confere com nenhuma chave secreta configurada."


def verify_signature(raw_body: bytes, header_value: str | None) -> bool:
    return signature_problem(raw_body, header_value) is None


# Tentativas recusadas: gravamos só metadados (nunca o corpo), para diagnóstico.
# Sobrevivem a reinícios do servidor; a tabela guarda apenas as mais recentes.
MAX_STORED_REJECTIONS = 500


def record_rejection(raw_body: bytes, reason: str, has_signature: bool) -> None:
    accounts, fields = set(), set()
    try:
        payload = json.loads(raw_body)
        for entry in payload.get("entry") or []:
            if isinstance(entry, dict):
                accounts.add(str(entry.get("id", "")))
                if entry.get("messaging"):
                    fields.add("messages")
                for change in entry.get("changes") or []:
                    if isinstance(change, dict):
                        fields.add(str(change.get("field", ""))[:40])
    except (ValueError, AttributeError, TypeError):
        pass
    try:
        with db.connection() as conn:
            event_repo.add_rejection(
                conn, reason, sorted(a[:40] for a in accounts if a)[:5], sorted(f for f in fields if f)[:5],
                has_signature, hashlib.sha256(raw_body).hexdigest(), MAX_STORED_REJECTIONS,
            )
    except Exception:  # noqa: BLE001 - diagnóstico nunca pode derrubar a resposta à Meta
        logger.exception("Não foi possível registrar a recusa do webhook.")


def recent_rejections(ig_user_id: str, other_ig_ids: set[str]) -> list[dict]:
    """Recusas dos últimos 7 dias desta conta ou sem conta reconhecida (ex.: eventos de teste da Meta)."""
    with db.connection() as conn:
        rows = event_repo.recent_rejections(conn, days=7, limit=50)
    return [
        {"received_at": r["received_at"], "reason": r["reason"], "fields": r["fields"],
         "has_signature": r["has_signature"]}
        for r in rows
        if ig_user_id in r["ig_account_ids"] or not (set(r["ig_account_ids"]) & other_ig_ids)
    ]


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
    if not account:
        return _ignore(event_id, "Conta do Instagram não cadastrada na plataforma.")
    if account["status"] != "connected":
        return _ignore(event_id, f"Conta com status '{account['status']}'.", account)
    # Só eventos reais de contas conectadas registram "último evento" (simulações e contas antigas não)
    if not is_simulated(event):
        with db.connection() as conn:
            instagram_repository.mark_webhook_received(conn, account["id"])

    item = event["payload"]
    user_id = str(account["user_id"])
    simulated = is_simulated(event)
    ctx: dict = {
        "trigger": {"received_at": datetime.now(timezone.utc).isoformat(), "simulated": simulated},
        "vars": {},
        "ai": {},
        # dry_run: ações que enviariam algo ao Instagram são apenas registradas
        "_sys": {"account_id": str(account["id"]), "dry_run": simulated},
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

    if trigger_type == MESSAGE_TRIGGER and not simulated:
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


SIMULATION_PREFIX = "sim:"
SIMULATED_SENDER_ID = "simulado"


def is_simulated(event: dict) -> bool:
    # A chave de deduplicação é gerada pelo servidor: um payload externo não consegue forjá-la.
    return str(event.get("dedupe_key", "")).startswith(SIMULATION_PREFIX)


def simulate(user_id: str, kind: str, text: str) -> dict:
    """Cria um evento de teste para a conta do usuário e processa como se viesse da Meta (sem enviar nada)."""
    with db.connection() as conn:
        account = instagram_repository.get_connected_for_user(conn, user_id)
    if not account:
        raise AppError("INSTAGRAM_NOT_CONNECTED", "Conecte o Instagram antes de simular eventos.", 409)
    sim_id = uuid.uuid4().hex[:12]
    if kind == "comment":
        field = "comments"
        item = {"from": {"id": SIMULATED_SENDER_ID, "username": "teste_simulado"}, "id": f"sim-comment-{sim_id}",
                "text": text, "media": {"id": "simulado", "media_product_type": "FEED"}}
    else:
        field = "messages"
        item = {"sender": {"id": SIMULATED_SENDER_ID}, "recipient": {"id": account["ig_user_id"]},
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "message": {"mid": f"sim-mid-{sim_id}", "text": text}}
    with db.connection() as conn:
        row = event_repo.insert_if_new(conn, f"{SIMULATION_PREFIX}{sim_id}", "instagram", field,
                                       account["ig_user_id"], item)
        queue.enqueue(conn, "process_webhook_event", {"event_id": str(row["id"])})
    logger.info("Evento simulado criado: %s (%s) user=%s", row["id"], field, user_id)
    return {"event_id": str(row["id"]), "field": field}


def _summarize(event: dict) -> dict:
    item = event["payload"] or {}
    if event["field"] == "messages":
        message = item.get("message") or {}
        return {"text": (message.get("text") or "")[:300], "from": (item.get("sender") or {}).get("id"),
                "is_echo": bool(message.get("is_echo")), "has_attachments": bool(message.get("attachments"))}
    if event["field"] == "comments":
        sender = item.get("from") or {}
        return {"text": (item.get("text") or "")[:300], "from": sender.get("username") or sender.get("id"),
                "media_id": (item.get("media") or {}).get("id")}
    return {}


def list_events(user_id: str, limit: int) -> dict:
    """Eventos recebidos para a conta do usuário + tentativas recusadas (diagnóstico)."""
    with db.connection() as conn:
        account = instagram_repository.get_for_user(conn, user_id)
        if not account:
            return {"account": None, "events": [], "rejections": []}
        rows = event_repo.list_for_account(conn, str(account["id"]), account["ig_user_id"], limit)
        others = instagram_repository.other_ig_user_ids(conn, account["ig_user_id"])
    events = [{
        "id": str(r["id"]), "field": r["field"], "status": r["status"], "status_reason": r["status_reason"],
        "received_at": r["received_at"], "processed_at": r["processed_at"], "executions": r["executions"],
        "simulated": is_simulated(r), **_summarize(r),
    } for r in rows]
    return {
        "account": {"username": account["username"], "last_webhook_at": account["last_webhook_at"]},
        "events": events,
        "rejections": recent_rejections(account["ig_user_id"], others),
    }


def _trigger_config(workflow: dict) -> dict:
    for node in workflow["graph"].get("nodes", []):
        if node["type"] == workflow["trigger_type"]:
            return node.get("data", {}).get("config", {})
    return {}
