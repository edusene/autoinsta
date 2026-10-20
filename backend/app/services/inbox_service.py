"""Caixa de entrada: conversas por DM, envio manual e atendimento humano."""
import logging

from app import db
from app.errors import AppError, NotFoundError
from app.repositories import contact_repository, instagram_repository, message_repository
from app.services import instagram_service, messaging_service, meta_client

logger = logging.getLogger(__name__)


def list_conversations(user_id: str, search: str | None, unread_only: bool, limit: int, offset: int) -> dict:
    with db.connection() as conn:
        rows, total = contact_repository.list_conversations(conn, user_id, search, unread_only, limit, offset)
        unread = contact_repository.unread_total(conn, user_id)
    return {"items": rows, "total": total, "limit": limit, "offset": offset, "unread_conversations": unread}


def unread_count(user_id: str) -> int:
    with db.connection() as conn:
        return contact_repository.unread_total(conn, user_id)


def get_conversation(user_id: str, contact_id: str) -> dict:
    with db.connection() as conn:
        contact = contact_repository.get(conn, user_id, contact_id)
        if not contact:
            raise NotFoundError("Conversa não encontrada.")
        messages = message_repository.list_for_contact(conn, user_id, contact_id)
    return {"contact": contact, "messages": messages}


def mark_read(user_id: str, contact_id: str) -> None:
    with db.connection() as conn:
        contact_repository.mark_read(conn, user_id, contact_id)


def send_message(user_id: str, contact_id: str, text: str) -> dict:
    text = text.strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "Escreva a mensagem.")
    with db.connection() as conn:
        contact = contact_repository.get(conn, user_id, contact_id)
        account = instagram_repository.get_connected_for_user(conn, user_id)
    if not contact:
        raise NotFoundError("Conversa não encontrada.")
    if not account or str(account["id"]) != str(contact["instagram_account_id"]):
        raise AppError("INSTAGRAM_NOT_CONNECTED", "Conecte a conta do Instagram desta conversa para responder.", 409)
    if not contact["can_message"]:
        raise AppError("OUTSIDE_WINDOW", "A Meta só permite responder até 24h depois da última mensagem do "
                                         "contato. Aguarde ele escrever de novo.", 409)
    token = instagram_service.get_access_token(str(account["id"]))
    try:
        messaging_service.send(token=token, user_id=user_id, account_id=str(account["id"]),
                               contact_id=contact_id, recipient_igsid=contact["ig_scoped_id"], text=text,
                               source="inbox")
    except meta_client.MetaApiError as exc:
        if exc.is_token_error:
            instagram_service.mark_token_invalid(str(account["id"]), exc.message)
            raise AppError("INSTAGRAM_TOKEN_EXPIRED", "A conexão com o Instagram expirou. Reconecte a conta.", 409)
        raise AppError("META_ERROR", f"A Meta recusou a mensagem: {exc.message}", 502)
    mark_read(user_id, contact_id)
    return get_conversation(user_id, contact_id)
