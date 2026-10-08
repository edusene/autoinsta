from flask import Blueprint, request
from pydantic import BaseModel, Field

from app.errors import ok
from app.services import execution_service, workflow_service
from app.utils.auth import current_user_id, require_auth
from app.utils.http import pagination, parse_body
from app.workflow import nodes
from app.workflow.validator import normalize_graph, validate_graph

bp = Blueprint("workflows", __name__, url_prefix="/api/workflows")


class CreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    graph: dict | None = None


class UpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    graph: dict | None = None


class ValidateBody(BaseModel):
    graph: dict


@bp.get("/node-types")
@require_auth
def node_types():
    return ok(nodes.catalog())


@bp.get("")
@require_auth
def list_workflows():
    return ok(workflow_service.list_workflows(current_user_id()))


@bp.post("")
@require_auth
def create_workflow():
    body = parse_body(CreateBody)
    return ok(workflow_service.create_workflow(current_user_id(), body.name.strip(), body.description, body.graph), 201)


@bp.post("/validate")
@require_auth
def validate_draft():
    """Valida um grafo ainda não salvo (usado pelo editor)."""
    body = parse_body(ValidateBody)
    return ok(validate_graph(normalize_graph(body.graph)))


@bp.get("/<uuid:workflow_id>")
@require_auth
def get_workflow(workflow_id):
    return ok(workflow_service.get_workflow(current_user_id(), str(workflow_id)))


@bp.put("/<uuid:workflow_id>")
@require_auth
def update_workflow(workflow_id):
    body = parse_body(UpdateBody)
    fields = body.model_dump(exclude_unset=True)
    return ok(workflow_service.update_workflow(current_user_id(), str(workflow_id), fields))


@bp.delete("/<uuid:workflow_id>")
@require_auth
def delete_workflow(workflow_id):
    workflow_service.delete_workflow(current_user_id(), str(workflow_id))
    return ok({"deleted": True})


@bp.post("/<uuid:workflow_id>/duplicate")
@require_auth
def duplicate_workflow(workflow_id):
    return ok(workflow_service.duplicate_workflow(current_user_id(), str(workflow_id)), 201)


@bp.post("/<uuid:workflow_id>/validate")
@require_auth
def validate_workflow(workflow_id):
    return ok(workflow_service.validate_workflow(current_user_id(), str(workflow_id)))


@bp.post("/<uuid:workflow_id>/activate")
@require_auth
def activate(workflow_id):
    return ok(workflow_service.activate_workflow(current_user_id(), str(workflow_id)))


@bp.post("/<uuid:workflow_id>/deactivate")
@require_auth
def deactivate(workflow_id):
    return ok(workflow_service.deactivate_workflow(current_user_id(), str(workflow_id)))


@bp.get("/<uuid:workflow_id>/executions")
@require_auth
def executions(workflow_id):
    limit, offset = pagination()
    status = request.args.get("status") or None
    return ok(execution_service.list_executions(current_user_id(), str(workflow_id), status, limit, offset))
