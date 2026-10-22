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
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from flask import current_app

from app import db
from app.errors import AppError
from app.repositories import contact_repository, instagram_repository, message_repository, settings_repository
from app.repositories import execution_repository as exec_repo
from app.repositories import webhook_event_repository as event_repo
from app.repositories import workflow_repository
from app.services import instagram_service, messaging_service, meta_client
from app.tasks import queue
from app.workflow import engine
from app.workflow.nodes import (
    COMMENT_TRIGGER, IG_ME_LINK_TRIGGER, LIVE_COMMENT_TRIGGER, MESSAGE_REACTION_TRIGGER, MESSAGE_TRIGGER,
    NEW_CONTACT_TRIGGER, STORY_MENTION_TRIGGER, STORY_REPLY_TRIGGER,
)

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
# A rota é pública: limita as gravações por processo para que requisições falsas em massa
# não virem carga no banco (as recusas continuam respondendo 403 normalmente).
MAX_REJECTIONS_PER_MINUTE = 30
_rejection_times: deque[float] = deque()
_rejection_lock = threading.Lock()


def _rejection_allowed() -> bool:
    now = time.monotonic()
    with _rejection_lock:
        while _rejection_times and now - _rejection_times[0] > 60:
            _rejection_times.popleft()
        if len(_rejection_times) >= MAX_REJECTIONS_PER_MINUTE:
            return False
        _rejection_times.append(now)
        return True


def record_rejection(raw_body: bytes, reason: str, has_signature: bool) -> None:
    if not _rejection_allowed():
        return
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


# Campo do webhook para cada tipo de item em entry[].messaging[]
MESSAGING_FIELDS = (
    ("message", "messages"),
    ("reaction", "message_reactions"),
    ("referral", "messaging_referral"),
    ("postback", "messaging_postbacks"),
    ("read", "messaging_seen"),
)
COMMENT_FIELDS = ("comments", "live_comments")


def _messaging_field(item: dict) -> str:
    for key, field in MESSAGING_FIELDS:
        if key in item:
            return field
    return "messaging_other"


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
            field = _messaging_field(item)
            mid = (item.get("message") or {}).get("mid") if field == "messages" and isinstance(item.get("message"), dict) else None
            items.append((_dedupe_key(field, item, mid), field, account_id, item))
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            field = str(change.get("field", "unknown"))
            value = change.get("value") if isinstance(change.get("value"), dict) else {}
            comment_id = (value.get("id") or value.get("comment_id")) if field in COMMENT_FIELDS else None
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


@dataclass
class Classified:
    """Resultado da leitura de um evento: quais gatilhos disparar e o que vai para o contexto."""
    triggers: list[str]                       # em ordem; o 1º com workflows ativos é o usado
    sender_id: str
    sender_username: str | None
    summary: str
    ctx: dict = field(default_factory=dict)
    trigger_event: dict = field(default_factory=dict)
    is_dm: bool = False                       # conversa por DM: conta para "Novo contato" e vai para a caixa de entrada
    button_payload: str | None = None         # clique em botão / resposta rápida
    inbox_text: str | None = None             # texto completo para a caixa de entrada


def _classify(event: dict, account: dict) -> Classified | str:
    """Interpreta o evento. Retorna Classified ou o motivo para ignorá-lo."""
    item = event["payload"] or {}
    kind = event["field"]
    own_id = account["ig_user_id"]

    if kind in ("messages", "messaging_referral", "message_reactions", "messaging_postbacks"):
        sender_id = str((item.get("sender") or {}).get("id", ""))
        if not sender_id:
            return "Evento sem remetente."
        if sender_id == own_id:
            return "Evento gerado pela própria conta (eco)."

    if kind == "messages":
        message = item.get("message") or {}
        if message.get("is_echo"):
            return "Mensagem enviada pela própria conta (eco)."
        if message.get("is_deleted"):
            return "Mensagem apagada."
        text = message.get("text") or ""
        attachments = [a for a in message.get("attachments") or [] if isinstance(a, dict)]
        ctx = {"message": {"id": message.get("mid"), "text": text, "has_attachments": bool(attachments)}}
        mention = next((a for a in attachments if a.get("type") == "story_mention"), None)
        story = (message.get("reply_to") or {}).get("story")
        referral = message.get("referral")
        if mention:
            ctx["story"] = {"url": (mention.get("payload") or {}).get("url") or ""}
            return Classified([STORY_MENTION_TRIGGER], sender_id, None, "[menção no story]", ctx,
                              {"message_id": message.get("mid")}, is_dm=True)
        if isinstance(story, dict):
            ctx["story"] = {"id": story.get("id") or "", "url": story.get("url") or ""}
            return Classified([STORY_REPLY_TRIGGER, MESSAGE_TRIGGER], sender_id, None,
                              f"[resposta ao story] {text}"[:200], ctx, {"message_id": message.get("mid")}, is_dm=True)
        if isinstance(referral, dict):
            ctx["referral"] = {k: referral.get(k) or "" for k in ("ref", "source", "type")}
            return Classified([IG_ME_LINK_TRIGGER, MESSAGE_TRIGGER], sender_id, None,
                              f"[link ig.me {ctx['referral']['ref']}] {text}"[:200], ctx,
                              {"message_id": message.get("mid"), "ref": ctx["referral"]["ref"]}, is_dm=True)
        quick_reply = (message.get("quick_reply") or {}).get("payload")
        return Classified([MESSAGE_TRIGGER], sender_id, None, text[:200] or "[mensagem sem texto]", ctx,
                          {"message_id": message.get("mid")}, is_dm=True, button_payload=quick_reply,
                          inbox_text=text or ("[anexo]" if attachments else "[mensagem sem texto]"))

    if kind == "messaging_postbacks":
        postback = item.get("postback") or {}
        title = str(postback.get("title") or "")
        ctx = {"message": {"id": postback.get("mid"), "text": title}}
        # Sem gatilho próprio: o clique só retoma o fluxo que enviou o botão (e conta no CTR)
        return Classified([], sender_id, None, f"[clicou no botão] {title}"[:200], ctx,
                          {"message_id": postback.get("mid")}, is_dm=True, button_payload=postback.get("payload"),
                          inbox_text=f"[clicou no botão] {title}")

    if kind == "messaging_referral":
        referral = item.get("referral") or {}
        ctx = {"referral": {k: referral.get(k) or "" for k in ("ref", "source", "type")}, "message": {"text": ""}}
        return Classified([IG_ME_LINK_TRIGGER], sender_id, None, f"[link ig.me {ctx['referral']['ref']}]", ctx,
                          {"ref": ctx["referral"]["ref"]})

    if kind == "message_reactions":
        reaction = item.get("reaction") or {}
        if reaction.get("action") == "unreact":
            return "Reação removida."
        ctx = {"reaction": {"emoji": reaction.get("emoji") or "", "type": reaction.get("reaction") or "",
                            "message_id": reaction.get("mid") or ""}, "message": {"text": ""}}
        return Classified([MESSAGE_REACTION_TRIGGER], sender_id, None,
                          f"[reação {ctx['reaction']['emoji'] or ctx['reaction']['type']}]", ctx,
                          {"message_id": ctx["reaction"]["message_id"]})

    if kind in COMMENT_FIELDS:
        sender = item.get("from") or {}
        sender_id = str(sender.get("id", ""))
        if not sender_id:
            return "Comentário sem autor."
        if sender_id == own_id:
            return "Comentário feito pela própria conta."
        media = item.get("media") or {}
        ctx = {"comment": {
            "id": item.get("id") or item.get("comment_id"),
            "text": item.get("text") or "",
            "media_id": media.get("id"),
            "media_type": media.get("media_product_type"),
            "parent_id": item.get("parent_id"),
        }}
        trigger = COMMENT_TRIGGER if kind == "comments" else LIVE_COMMENT_TRIGGER
        prefix = "" if kind == "comments" else "[live] "
        return Classified([trigger], sender_id, sender.get("username"), f"{prefix}{item.get('text') or ''}"[:200],
                          ctx, {"comment_id": ctx["comment"]["id"], "media_id": ctx["comment"]["media_id"]})

    return f"Campo '{kind}' não tratado."


def _matches_trigger_config(workflow: dict, ctx: dict) -> bool:
    cfg = _trigger_config(workflow)
    if workflow["trigger_type"] == COMMENT_TRIGGER:
        wanted = (cfg.get("media_id") or "").strip()
        return not wanted or wanted == str(ctx["comment"]["media_id"] or "")
    if workflow["trigger_type"] == IG_ME_LINK_TRIGGER:
        wanted = (cfg.get("ref") or "").strip().lower()
        return not wanted or wanted == str(ctx.get("referral", {}).get("ref") or "").strip().lower()
    return True


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
    simulated = is_simulated(event)
    # Só eventos reais de contas conectadas registram "último evento" (simulações e contas antigas não)
    if not simulated:
        with db.connection() as conn:
            instagram_repository.mark_webhook_received(conn, account["id"])

    if event["field"] == "messages" and not simulated:
        _record_echo(event, account)

    classified = _classify(event, account)
    if isinstance(classified, str):
        return _ignore(event_id, classified, account)

    user_id = str(account["user_id"])
    ctx: dict = {
        "trigger": {"received_at": datetime.now(timezone.utc).isoformat(), "simulated": simulated},
        "vars": {},
        "ai": {},
        # dry_run: ações que enviariam algo ao Instagram são apenas registradas
        "_sys": {"account_id": str(account["id"]), "dry_run": simulated},
        **classified.ctx,
    }

    with db.connection() as conn:
        contact = contact_repository.upsert_from_event(conn, user_id, str(account["id"]), classified.sender_id,
                                                       classified.sender_username, event["field"])
        contact_repository.add_event(conn, user_id, contact["id"], event["field"], classified.summary,
                                     {"webhook_event_id": str(event_id)})
        if classified.is_dm and not simulated:
            mid = (classified.ctx.get("message") or {}).get("id")
            text = classified.inbox_text or classified.summary
            if message_repository.insert_inbound_if_new(conn, user_id=user_id, account_id=str(account["id"]),
                                                        contact_id=str(contact["id"]), kind=event["field"],
                                                        text=text, mid=mid):
                contact_repository.touch_inbound(conn, contact["id"], text)
        targets = _waiting_targets(conn, contact, classified, event["field"])
        settings = settings_repository.get(conn, user_id)

    if contact.get("automation_paused"):
        with db.connection() as conn:
            event_repo.set_status(conn, event_id, "processed",
                                  "Automação pausada para este contato (atendimento humano).",
                                  str(account["id"]), user_id)
        return

    # Resposta/clique de quem está num fluxo em espera: retoma esse fluxo em vez de disparar outros
    if targets:
        with db.connection() as conn:
            event_repo.set_status(conn, event_id, "processed", "Resposta usada por um fluxo em espera.",
                                  str(account["id"]), user_id)
        resumed = [engine.resume_wait(*target) for target in targets]
        if any(resumed):
            return

    with db.connection() as conn:
        # 1º gatilho da lista com workflows ativos (ex.: resposta ao story -> mensagem recebida)
        selected: list[tuple[str, dict]] = []
        for trigger in classified.triggers:
            found = workflow_repository.list_active_by_trigger(conn, user_id, trigger)
            if found:
                selected = [(trigger, w) for w in found]
                break
        if classified.is_dm and contact.get("inserted"):
            selected += [(NEW_CONTACT_TRIGGER, w)
                         for w in workflow_repository.list_active_by_trigger(conn, user_id, NEW_CONTACT_TRIGGER)]
        # Marca como processado ANTES de executar: um retry do job não duplica mensagens enviadas.
        event_repo.set_status(conn, event_id, "processed", f"{len(selected)} workflow(s) compatível(is).",
                              str(account["id"]), user_id)

    if classified.is_dm and not simulated:
        contact = _enrich_contact(account, contact)
    ctx["contact"] = {"id": str(contact["id"]), "ig_id": classified.sender_id,
                      "username": contact.get("username") or "", "name": contact.get("name") or ""}
    if settings and settings.get("ai_default_model"):
        ctx["_sys"]["ai_default_model"] = settings["ai_default_model"]

    for trigger, workflow in selected:
        if not _matches_trigger_config(workflow, ctx):
            continue
        trigger_event = {"field": event["field"], "trigger": trigger, "summary": classified.summary,
                         **classified.trigger_event}
        try:
            engine.start(workflow, json.loads(json.dumps(ctx)), trigger_event, str(contact["id"]), str(event_id))
        except Exception:  # noqa: BLE001 - um workflow com problema não bloqueia os outros
            logger.exception("Falha ao iniciar workflow %s para o evento %s", workflow["id"], event_id)


def _waiting_targets(conn, contact: dict, classified: Classified, field: str) -> list[tuple]:
    """Execuções que esta resposta deve retomar: argumentos para engine.resume_wait().

    - clique em botão/resposta rápida enviado por um fluxo -> retoma pela saída do botão (e conta no CTR);
    - DM de texto -> retoma quem está em "Aguardar resposta" pela saída "Respondeu".
    """
    parsed = messaging_service.parse_payload(classified.button_payload)
    if parsed:
        message_id, button_id = parsed
        sent = message_repository.get(conn, message_id)
        if not sent or str(sent["contact_id"]) != str(contact["id"]) or sent["direction"] != "out":
            return []
        message_repository.mark_clicked(conn, message_id)
        if not sent["execution_id"]:
            return []
        title = next((b.get("title") for b in sent["buttons"] or [] if b.get("id") == button_id), button_id)
        updates = {"button": {"id": button_id, "title": title},
                   "message": {**(classified.ctx.get("message") or {}), "text": title}}
        return [(str(sent["execution_id"]), ["button"], button_id, f'Contato clicou em "{title}".',
                 updates, sent["node_id"])]
    if field != "messages" or MESSAGE_TRIGGER not in classified.triggers:
        return []
    message = classified.ctx.get("message") or {}
    text = str(message.get("text") or "")
    return [
        (str(row["id"]), ["reply"], "replied", f"Contato respondeu: {text[:120] or '[sem texto]'}",
         {"message": message, "reply": {"text": text}}, row["current_node_id"])
        for row in exec_repo.list_waiting_for_contact(conn, contact["id"], "reply")
    ]


def _record_echo(event: dict, account: dict) -> None:
    """Mensagem enviada pela conta no app do Instagram: entra na conversa (as da plataforma já estão lá)."""
    item = event["payload"] or {}
    message = item.get("message") or {}
    if not message.get("is_echo"):
        return
    recipient = str((item.get("recipient") or {}).get("id", ""))
    with db.connection() as conn:
        contact = contact_repository.get_by_ig_id(conn, str(account["id"]), recipient)
        if not contact:
            return
        text = message.get("text") or "[anexo]"
        if message_repository.insert_echo_if_new(conn, user_id=str(account["user_id"]),
                                                 account_id=str(account["id"]), contact_id=str(contact["id"]),
                                                 text=text, mid=message.get("mid")):
            contact_repository.touch_outbound(conn, contact["id"], text)


SIMULATION_PREFIX = "sim:"
SIMULATED_SENDER_ID = "simulado"


def is_simulated(event: dict) -> bool:
    # A chave de deduplicação é gerada pelo servidor: um payload externo não consegue forjá-la.
    return str(event.get("dedupe_key", "")).startswith(SIMULATION_PREFIX)


SIMULATION_KINDS = ("message", "comment", "new_contact", "story_mention", "story_reply", "ig_me_link",
                    "reaction", "live_comment")


def simulate(user_id: str, kind: str, text: str) -> dict:
    """Cria um evento de teste para a conta do usuário e processa como se viesse da Meta (sem enviar nada)."""
    with db.connection() as conn:
        account = instagram_repository.get_connected_for_user(conn, user_id)
    if not account:
        raise AppError("INSTAGRAM_NOT_CONNECTED", "Conecte o Instagram antes de simular eventos.", 409)
    sim_id = uuid.uuid4().hex[:12]
    # "Novo contato" precisa de um remetente nunca visto; os demais reaproveitam o contato de teste
    sender_id = f"{SIMULATED_SENDER_ID}-{sim_id}" if kind == "new_contact" else SIMULATED_SENDER_ID
    base = {"sender": {"id": sender_id}, "recipient": {"id": account["ig_user_id"]},
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)}
    message = {"mid": f"sim-mid-{sim_id}", "text": text}

    if kind in ("comment", "live_comment"):
        field = "comments" if kind == "comment" else "live_comments"
        item = {"from": {"id": SIMULATED_SENDER_ID, "username": "teste_simulado"}, "id": f"sim-comment-{sim_id}",
                "text": text, "media": {"id": "simulado", "media_product_type": "FEED" if kind == "comment" else "LIVE"}}
    elif kind == "story_mention":
        field = "messages"
        item = {**base, "message": {"mid": message["mid"],
                                    "attachments": [{"type": "story_mention", "payload": {"url": "https://exemplo/story"}}]}}
    elif kind == "story_reply":
        field = "messages"
        item = {**base, "message": {**message, "reply_to": {"story": {"id": "story-simulado", "url": "https://exemplo/story"}}}}
    elif kind == "ig_me_link":
        field = "messages"
        ref = text.strip().split()[0][:100] if text.strip() else "simulado"
        item = {**base, "message": {**message, "referral": {"ref": ref, "source": "IGME_SOURCE_LINK", "type": "OPEN_THREAD"}}}
    elif kind == "reaction":
        field = "message_reactions"
        item = {**base, "reaction": {"mid": f"sim-mid-{sim_id}", "action": "react", "reaction": "love",
                                     "emoji": text.strip()[:8] or "❤️"}}
    else:  # message, new_contact
        field = "messages"
        item = {**base, "message": message}

    with db.connection() as conn:
        row = event_repo.insert_if_new(conn, f"{SIMULATION_PREFIX}{sim_id}", "instagram", field,
                                       account["ig_user_id"], item)
        queue.enqueue(conn, "process_webhook_event", {"event_id": str(row["id"])})
    logger.info("Evento simulado criado: %s (%s/%s) user=%s", row["id"], kind, field, user_id)
    return {"event_id": str(row["id"]), "field": field, "kind": kind}


def _summarize(event: dict) -> dict:
    item = event["payload"] or {}
    field = event["field"]
    sender = (item.get("sender") or {}).get("id")
    if field == "messages":
        message = item.get("message") or {}
        attachments = [a for a in message.get("attachments") or [] if isinstance(a, dict)]
        if any(a.get("type") == "story_mention" for a in attachments):
            text = "[menção no story]"
        elif isinstance((message.get("reply_to") or {}).get("story"), dict):
            text = f"[resposta ao story] {message.get('text') or ''}"
        elif isinstance(message.get("referral"), dict):
            text = f"[link ig.me {message['referral'].get('ref') or ''}] {message.get('text') or ''}"
        else:
            text = message.get("text") or ""
        return {"text": text[:300], "from": sender, "is_echo": bool(message.get("is_echo")),
                "has_attachments": bool(attachments)}
    if field == "messaging_postbacks":
        return {"text": f"[clicou no botão] {(item.get('postback') or {}).get('title') or ''}", "from": sender}
    if field == "messaging_referral":
        return {"text": f"[link ig.me {(item.get('referral') or {}).get('ref') or ''}]", "from": sender}
    if field == "message_reactions":
        reaction = item.get("reaction") or {}
        verb = "removeu reação" if reaction.get("action") == "unreact" else "reagiu"
        return {"text": f"[{verb} {reaction.get('emoji') or reaction.get('reaction') or ''}]", "from": sender}
    if field in COMMENT_FIELDS:
        author = item.get("from") or {}
        prefix = "" if field == "comments" else "[live] "
        return {"text": f"{prefix}{item.get('text') or ''}"[:300], "from": author.get("username") or author.get("id"),
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
