"""Consulta de execuções e logs."""
from app import db
from app.errors import NotFoundError
from app.repositories import execution_repository, workflow_repository


def _public_context(context: dict) -> dict:
    """Remove dados internos (_sys) antes de enviar ao frontend."""
    return {k: v for k, v in (context or {}).items() if not k.startswith("_")}


def list_executions(user_id: str, workflow_id: str | None, status: str | None, limit: int, offset: int) -> dict:
    with db.connection() as conn:
        if workflow_id and not workflow_repository.get(conn, user_id, workflow_id):
            raise NotFoundError("Workflow não encontrado.")
        rows, total = execution_repository.list_for_user(conn, user_id, workflow_id, status, limit, offset)
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def get_execution(user_id: str, execution_id: str) -> dict:
    with db.connection() as conn:
        execution = execution_repository.get_for_user(conn, user_id, execution_id)
        if not execution:
            raise NotFoundError("Execução não encontrada.")
        logs = execution_repository.list_logs(conn, user_id, execution_id)
    return {**execution, "context": _public_context(execution["context"]), "logs": logs}
