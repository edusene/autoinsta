"""Configurações do usuário. A chave da OpenAI nunca sai do servidor (só um final mascarado)."""
from app import db
from app.errors import AppError
from app.repositories import settings_repository
from app.services import instagram_service, openai_service


def get_settings(user_id: str) -> dict:
    with db.connection() as conn:
        row = settings_repository.get(conn, user_id)
    return {
        "ai": {
            "openai_configured": openai_service.is_configured(),
            "key_hint": openai_service.key_hint(),
            "platform_default_model": openai_service.default_model(),
            "default_model": (row or {}).get("ai_default_model") or None,
        },
        "instagram": instagram_service.get_status(user_id),
    }


def update_settings(user_id: str, ai_default_model: str | None) -> dict:
    model = (ai_default_model or "").strip() or None
    if model and (len(model) > 80 or not all(c.isalnum() or c in "-._:" for c in model)):
        raise AppError("VALIDATION_ERROR", "Nome de modelo inválido.")
    with db.connection() as conn:
        settings_repository.upsert(conn, user_id, model)
    return get_settings(user_id)
