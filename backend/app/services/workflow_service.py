"""CRUD e ciclo de vida dos workflows (sempre restrito ao dono)."""
import json
import logging
import uuid

from app import db
from app.errors import AppError, NotFoundError
from app.repositories import instagram_repository
from app.repositories import workflow_repository as repo
from app.workflow.nodes import MESSAGE_TRIGGER
from app.workflow.validator import normalize_graph, trigger_type_of, validate_graph

logger = logging.getLogger(__name__)

MAX_GRAPH_BYTES = 256_000


def default_graph() -> dict:
    return {
        "nodes": [{"id": f"trigger-{uuid.uuid4().hex[:8]}", "type": MESSAGE_TRIGGER,
                   "position": {"x": 80, "y": 120}, "data": {"config": {}}}],
        "edges": [],
    }


def _prepare_graph(graph: dict | None) -> dict:
    normalized = normalize_graph(graph)
    if len(json.dumps(normalized)) > MAX_GRAPH_BYTES:
        raise AppError("WORKFLOW_TOO_LARGE", "O workflow é grande demais.")
    return normalized


def list_workflows(user_id: str) -> list[dict]:
    with db.connection() as conn:
        return repo.list_for_user(conn, user_id)


def get_workflow(user_id: str, workflow_id: str) -> dict:
    with db.connection() as conn:
        workflow = repo.get(conn, user_id, workflow_id)
    if not workflow:
        raise NotFoundError("Workflow não encontrado.")
    return workflow


def create_workflow(user_id: str, name: str, description: str | None, graph: dict | None) -> dict:
    graph = _prepare_graph(graph) if graph and graph.get("nodes") else default_graph()
    with db.connection() as conn:
        workflow = repo.create(conn, user_id, name, description, graph, trigger_type_of(graph))
    logger.info("Workflow criado: %s (user=%s)", workflow["id"], user_id)
    return workflow


def update_workflow(user_id: str, workflow_id: str, fields: dict) -> dict:
    current = get_workflow(user_id, workflow_id)
    changes = {k: v for k, v in fields.items() if k in ("name", "description") and v is not None}
    if "description" in fields:
        changes["description"] = fields["description"]
    if fields.get("graph") is not None:
        graph = _prepare_graph(fields["graph"])
        changes["graph"] = graph
        changes["trigger_type"] = trigger_type_of(graph)
        # Um workflow ativo não pode ficar inválido: valida antes de salvar.
        if current["status"] == "active":
            result = validate_graph(graph)
            if not result["valid"]:
                raise AppError("WORKFLOW_INVALID",
                               "Workflow ativo não pode ser salvo com erros. Corrija ou desative antes.",
                               details=result)
    with db.connection() as conn:
        return repo.update(conn, user_id, workflow_id, changes)


def delete_workflow(user_id: str, workflow_id: str) -> None:
    with db.connection() as conn:
        if not repo.delete(conn, user_id, workflow_id):
            raise NotFoundError("Workflow não encontrado.")
    logger.info("Workflow excluído: %s (user=%s)", workflow_id, user_id)


def duplicate_workflow(user_id: str, workflow_id: str) -> dict:
    source = get_workflow(user_id, workflow_id)
    name = f"{source['name']} (cópia)"[:120]
    with db.connection() as conn:
        return repo.create(conn, user_id, name, source["description"], source["graph"], source["trigger_type"])


def validate_workflow(user_id: str, workflow_id: str) -> dict:
    return validate_graph(get_workflow(user_id, workflow_id)["graph"])


def activate_workflow(user_id: str, workflow_id: str) -> dict:
    workflow = get_workflow(user_id, workflow_id)
    result = validate_graph(workflow["graph"])
    if not result["valid"]:
        raise AppError("WORKFLOW_INVALID", "Corrija os erros do workflow antes de ativar.", details=result)
    with db.connection() as conn:
        if not instagram_repository.get_connected_for_user(conn, user_id):
            raise AppError("INSTAGRAM_NOT_CONNECTED", "Conecte o Instagram antes de ativar workflows.", 409)
        updated = repo.update(conn, user_id, workflow_id,
                              {"status": "active", "trigger_type": result["trigger_type"]})
    logger.info("Workflow ativado: %s (user=%s)", workflow_id, user_id)
    return updated


def deactivate_workflow(user_id: str, workflow_id: str) -> dict:
    get_workflow(user_id, workflow_id)
    with db.connection() as conn:
        updated = repo.update(conn, user_id, workflow_id, {"status": "inactive"})
    logger.info("Workflow desativado: %s (user=%s)", workflow_id, user_id)
    return updated
