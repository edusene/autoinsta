"""CRM mínimo: leitura de contatos e do histórico de eventos."""
from app import db
from app.errors import NotFoundError
from app.repositories import contact_repository


def list_contacts(user_id: str, search: str | None, limit: int, offset: int) -> dict:
    with db.connection() as conn:
        rows, total = contact_repository.list_for_user(conn, user_id, search, limit, offset)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def get_contact(user_id: str, contact_id: str) -> dict:
    with db.connection() as conn:
        contact = contact_repository.get(conn, user_id, contact_id)
        if not contact:
            raise NotFoundError("Contato não encontrado.")
        events = contact_repository.list_events(conn, user_id, contact_id)
    return {**contact, "events": events}
