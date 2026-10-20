from app import db
from app.repositories import contact_repository, execution_repository, message_repository, workflow_repository
from app.services import instagram_service, openai_service


def summary(user_id: str) -> dict:
    with db.connection() as conn:
        workflows = workflow_repository.counts_for_user(conn, user_id)
        stats = execution_repository.stats_for_user(conn, user_id, 24)
        recent, _ = execution_repository.list_for_user(conn, user_id, None, None, 8, 0)
        errors, _ = execution_repository.list_for_user(conn, user_id, None, "error", 5, 0)
        contacts = contact_repository.count_for_user(conn, user_id)
        ctr = message_repository.ctr_for_user(conn, user_id, 7)
        links = message_repository.top_links(conn, user_id, 7)
        unread = contact_repository.unread_total(conn, user_id)
    return {
        "instagram": instagram_service.get_status(user_id),
        "workflows": workflows,
        "executions_24h": stats,
        "contacts_count": contacts,
        "ctr_7d": ctr,
        "top_links": links,
        "unread_conversations": unread,
        "recent_executions": recent,
        "recent_errors": errors,
        "openai_configured": openai_service.is_configured(),
    }
