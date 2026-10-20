"""Disparos em massa.

Regra da Meta: a conta só pode mandar DM para quem enviou mensagem nas últimas 24h.
Por isso o disparo vai para todo o público escolhido, mas quem está fora da janela é
pulado (com o motivo registrado) no momento do envio.

Fluxo: send() -> job "broadcast_start" (na hora ou agendado) monta a lista de destinatários
-> jobs "broadcast_batch" enviam em lotes pequenos, com intervalo entre eles.
"""
import logging
from datetime import datetime, timedelta, timezone

from app import db
from app.errors import AppError, NotFoundError
from app.repositories import broadcast_repository as repo
from app.repositories import contact_repository, instagram_repository
from app.services import instagram_service, messaging_service, meta_client
from app.tasks import queue
from app.workflow.nodes import TAG_RE

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
BATCH_INTERVAL_SECONDS = 2
MAX_TAGS = 20


def _clean_audience(audience: dict | None) -> dict:
    tags = []
    for tag in (audience or {}).get("tags") or []:
        tag = str(tag).strip().lower()
        if TAG_RE.match(tag) and tag not in tags:
            tags.append(tag)
    return {"tags": tags[:MAX_TAGS]}


def _clean_buttons(buttons: list | None) -> list[dict]:
    # No disparo só há botões de link (não há fluxo para continuar depois de um clique)
    cleaned = []
    for i, b in enumerate(buttons or [], start=1):
        if isinstance(b, dict):
            cleaned.append({"id": str(b.get("id") or f"b{i}")[:32], "title": str(b.get("title") or "").strip(),
                            "type": "url", "url": str(b.get("url") or "").strip()})
    return cleaned


def _clean(fields: dict) -> dict:
    out = {k: v for k, v in fields.items() if k in repo.EDITABLE}
    if "audience" in out:
        out["audience"] = _clean_audience(out["audience"])
    if "buttons" in out:
        out["buttons"] = _clean_buttons(out["buttons"])
    return out


def list_broadcasts(user_id: str) -> list[dict]:
    with db.connection() as conn:
        return repo.list_for_user(conn, user_id)


def get_broadcast(user_id: str, broadcast_id: str) -> dict:
    with db.connection() as conn:
        broadcast = repo.get(conn, user_id, broadcast_id)
    if not broadcast:
        raise NotFoundError("Disparo não encontrado.")
    return broadcast


def create_broadcast(user_id: str, fields: dict) -> dict:
    with db.connection() as conn:
        return repo.create(conn, user_id, _clean(fields))


def update_broadcast(user_id: str, broadcast_id: str, fields: dict) -> dict:
    current = get_broadcast(user_id, broadcast_id)
    if current["status"] != "draft":
        raise AppError("BROADCAST_LOCKED", "Só é possível editar disparos em rascunho.", 409)
    with db.connection() as conn:
        repo.update(conn, user_id, broadcast_id, _clean(fields))
    return get_broadcast(user_id, broadcast_id)


def delete_broadcast(user_id: str, broadcast_id: str) -> None:
    current = get_broadcast(user_id, broadcast_id)
    if current["status"] == "sending":
        raise AppError("BROADCAST_SENDING", "Cancele o disparo antes de excluir.", 409)
    with db.connection() as conn:
        repo.delete(conn, user_id, broadcast_id)


def audience_preview(user_id: str, audience: dict | None) -> dict:
    with db.connection() as conn:
        account = instagram_repository.get_connected_for_user(conn, user_id)
        if not account:
            return {"total": 0, "eligible": 0}
        return contact_repository.audience_counts(conn, user_id, str(account["id"]),
                                                  _clean_audience(audience)["tags"])


def _validate_content(broadcast: dict) -> None:
    text = (broadcast["text"] or "").strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "Escreva a mensagem do disparo.")
    buttons = broadcast["buttons"] or []
    if buttons:
        problems = messaging_service.validate_buttons(buttons, "buttons")
        if problems:
            raise AppError("VALIDATION_ERROR", problems[0])
        if len(text) > messaging_service.TEMPLATE_TEXT_MAX_CHARS:
            raise AppError("VALIDATION_ERROR", "Com botões, a mensagem pode ter até 640 caracteres.")


def send(user_id: str, broadcast_id: str, scheduled_at: datetime | None) -> dict:
    broadcast = get_broadcast(user_id, broadcast_id)
    if broadcast["status"] != "draft":
        raise AppError("BROADCAST_LOCKED", "Este disparo já foi enviado ou agendado.", 409)
    _validate_content(broadcast)
    now = datetime.now(timezone.utc)
    if scheduled_at and scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    scheduled = bool(scheduled_at and scheduled_at > now)
    with db.connection() as conn:
        if not instagram_repository.get_connected_for_user(conn, user_id):
            raise AppError("INSTAGRAM_NOT_CONNECTED", "Conecte o Instagram antes de enviar disparos.", 409)
        repo.set_status(conn, broadcast_id, "scheduled" if scheduled else "sending", scheduled_at=scheduled_at)
        queue.enqueue(conn, "broadcast_start", {"broadcast_id": broadcast_id},
                      delay_seconds=(scheduled_at - now).total_seconds() if scheduled else 0, max_attempts=1)
    logger.info("Disparo %s %s (user=%s)", broadcast_id, "agendado" if scheduled else "iniciado", user_id)
    return get_broadcast(user_id, broadcast_id)


def cancel(user_id: str, broadcast_id: str) -> dict:
    broadcast = get_broadcast(user_id, broadcast_id)
    with db.connection() as conn:
        if broadcast["status"] == "scheduled":
            repo.set_status(conn, broadcast_id, "draft")  # volta a ser editável
        elif broadcast["status"] == "sending":
            repo.set_status(conn, broadcast_id, "cancelled")
            repo.skip_pending(conn, broadcast_id, "Disparo cancelado.")
        else:
            raise AppError("BROADCAST_LOCKED", "Este disparo não está em andamento.", 409)
    return get_broadcast(user_id, broadcast_id)


def list_recipients(user_id: str, broadcast_id: str, status: str | None, limit: int, offset: int) -> dict:
    with db.connection() as conn:
        rows, total = repo.list_recipients(conn, user_id, broadcast_id, status, limit, offset)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


# --- worker -------------------------------------------------------------------

def start(broadcast_id: str) -> None:
    """Monta a lista de destinatários (job agendado ou imediato) e inicia os lotes."""
    with db.connection() as conn:
        broadcast = repo.get_by_id(conn, broadcast_id)
        if not broadcast or broadcast["status"] not in ("scheduled", "sending"):
            return  # cancelado antes da hora
        early = broadcast["scheduled_at"] and broadcast["scheduled_at"] > datetime.now(timezone.utc) + timedelta(seconds=5)
        if (broadcast["status"] == "scheduled" and early) or repo.has_recipients(conn, broadcast_id):
            return  # job de um agendamento antigo (cancelado e reagendado) ou já iniciado
        user_id = str(broadcast["user_id"])
        account = instagram_repository.get_connected_for_user(conn, user_id)
        if not account:
            repo.set_status(conn, broadcast_id, "failed", error="Instagram desconectado no momento do envio.")
            return
        contact_ids = contact_repository.audience_ids(conn, user_id, str(account["id"]),
                                                      _clean_audience(broadcast["audience"])["tags"])
        added = repo.add_recipients(conn, broadcast_id, contact_ids)
        if not added:
            repo.set_status(conn, broadcast_id, "done")
            return
        repo.set_status(conn, broadcast_id, "sending")
        queue.enqueue(conn, "broadcast_batch", {"broadcast_id": broadcast_id})
    logger.info("Disparo %s: %s destinatário(s)", broadcast_id, added)


def send_batch(broadcast_id: str) -> None:
    with db.connection() as conn:
        broadcast = repo.get_by_id(conn, broadcast_id)
        if not broadcast or broadcast["status"] != "sending":
            return
        user_id = str(broadcast["user_id"])
        account = instagram_repository.get_connected_for_user(conn, user_id)
        recipients = repo.claim_pending(conn, broadcast_id, BATCH_SIZE) if account else []
    if not account:
        with db.connection() as conn:
            repo.set_status(conn, broadcast_id, "failed", error="Instagram desconectado durante o envio.")
            repo.skip_pending(conn, broadcast_id, "Instagram desconectado.")
        return

    token = None
    for r in recipients:
        status, reason, message_id = "skipped", None, None
        if r["contact_status"] != "active":
            reason = "Contato bloqueado ou arquivado."
        elif not r["can_message"]:
            reason = "Fora da janela de 24h da Meta (o contato não mandou mensagem nas últimas 24h)."
        else:
            try:
                token = token or instagram_service.get_access_token(str(account["id"]))
                sent = messaging_service.send(
                    token=token, user_id=user_id, account_id=str(account["id"]), contact_id=str(r["contact_id"]),
                    recipient_igsid=r["ig_scoped_id"], text=broadcast["text"], buttons=broadcast["buttons"],
                    style="buttons" if broadcast["buttons"] else "text", track_links=broadcast["track_links"],
                    source="broadcast", broadcast_id=broadcast_id,
                )
                status, message_id = "sent", sent["message_id"]
            except meta_client.MetaApiError as exc:
                status, reason = "failed", exc.message
                if exc.is_token_error:
                    instagram_service.mark_token_invalid(str(account["id"]), exc.message)
                    with db.connection() as conn:
                        repo.finish_recipient(conn, r["id"], status, reason)
                        repo.set_status(conn, broadcast_id, "failed", error="A conexão com o Instagram expirou.")
                        repo.skip_pending(conn, broadcast_id, "Conexão com o Instagram expirou.")
                    return
            except AppError as exc:
                status, reason = "failed", exc.message
        with db.connection() as conn:
            repo.finish_recipient(conn, r["id"], status, reason, message_id)

    with db.connection() as conn:
        if repo.get_by_id(conn, broadcast_id)["status"] != "sending":
            return
        if repo.has_pending(conn, broadcast_id):
            queue.enqueue(conn, "broadcast_batch", {"broadcast_id": broadcast_id},
                          delay_seconds=BATCH_INTERVAL_SECONDS)
        else:
            repo.set_status(conn, broadcast_id, "done")
            logger.info("Disparo %s concluído.", broadcast_id)
