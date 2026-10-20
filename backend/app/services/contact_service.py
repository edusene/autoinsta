"""CRM: contatos, tags, notas, histórico e atendimento humano (pausa da automação)."""
from app import db
from app.errors import AppError, NotFoundError
from app.repositories import contact_repository
from app.workflow.nodes import TAG_RE

MAX_TAGS_PER_CONTACT = 30


def list_contacts(user_id: str, search: str | None, limit: int, offset: int, tag: str | None = None) -> dict:
    with db.connection() as conn:
        rows, total = contact_repository.list_for_user(conn, user_id, search, limit, offset, tag)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def get_contact(user_id: str, contact_id: str) -> dict:
    with db.connection() as conn:
        contact = contact_repository.get(conn, user_id, contact_id)
        if not contact:
            raise NotFoundError("Contato não encontrado.")
        events = contact_repository.list_events(conn, user_id, contact_id)
    return {**contact, "events": events}


def normalize_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        tag = str(tag).strip().lower()
        if not TAG_RE.match(tag):
            raise AppError("VALIDATION_ERROR", f"Tag inválida: '{tag[:40]}'. Use letras, números, espaço, - ou _.")
        if tag not in cleaned:
            cleaned.append(tag)
    if len(cleaned) > MAX_TAGS_PER_CONTACT:
        raise AppError("VALIDATION_ERROR", f"Use no máximo {MAX_TAGS_PER_CONTACT} tags por contato.")
    return cleaned


def update_contact(user_id: str, contact_id: str, fields: dict) -> dict:
    if "tags" in fields:
        fields["tags"] = normalize_tags(fields["tags"] or [])
    if "name" in fields and fields["name"] is not None:
        fields["name"] = fields["name"].strip() or None
    with db.connection() as conn:
        if not contact_repository.update_fields(conn, user_id, contact_id, fields):
            raise NotFoundError("Contato não encontrado.")
    return get_contact(user_id, contact_id)


def list_tags(user_id: str) -> list[dict]:
    with db.connection() as conn:
        return contact_repository.tag_counts(conn, user_id)
